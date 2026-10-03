"""Лабораторная №1: python classification.py."""

import json
import platform

import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    ConfusionMatrixDisplay, RocCurveDisplay, classification_report,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier, plot_tree

from preprocessing import ROOT, FEATURES, TARGET, plt, save_figure, sns


def make_pipeline(model, categories):
    # Pipeline обучает преобразования заново внутри каждого фолда CV.
    transform = ColumnTransformer([
        ("numeric", StandardScaler(), FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categories),
    ])
    return Pipeline([("preprocess", transform), ("model", model)])


def main():
    sns.set_theme(style="whitegrid")
    output = ROOT / "reports/lab1"
    output.mkdir(parents=True, exist_ok=True)
    # Используем исходные единицы, а не CSV, масштабированный на всей таблице.
    data = pd.read_csv(ROOT / "data/raw/credit_risk_dataset.csv").dropna().drop_duplicates()
    x, y = data.drop(columns=TARGET), data[TARGET]
    categories = [column for column in x.columns if column not in FEATURES]
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=42
    )
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    experiments = {
        "KNN": (KNeighborsClassifier(), {
            "model__n_neighbors": [5, 15, 31], "model__weights": ["uniform", "distance"]}),
        "SVM": (SVC(), [
            {"model__kernel": ["linear"], "model__C": [0.1, 1]},
            {"model__kernel": ["rbf"], "model__C": [1, 10], "model__gamma": ["scale", 0.01]},
        ]),
        "DecisionTree": (DecisionTreeClassifier(random_state=42), {
            "model__max_depth": [4, 8, 12, None],
            "model__min_samples_leaf": [5, 20],
            "model__class_weight": [None, "balanced"]}),
    }
    metrics, details = [], {}
    predictions = pd.DataFrame({"source_row": x_test.index, "actual": y_test.to_numpy()})
    fig_cm, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig_roc, ax_roc = plt.subplots(figsize=(8, 6))
    tree_pipeline = None
    for ax, (name, (model, grid)) in zip(axes, experiments.items()):
        print(f"Training {name}...", flush=True)
        search = GridSearchCV(make_pipeline(model, categories), grid,
                              scoring="f1", cv=cv, n_jobs=2, error_score="raise")
        search.fit(x_train, y_train)
        best = search.best_estimator_
        predicted = best.predict(x_test)
        # SVM даёт расстояние до разделяющей границы; ROC-AUC не требует вероятностей.
        score = (best.decision_function(x_test) if name == "SVM"
                 else best.predict_proba(x_test)[:, 1])
        metrics.append({
            "model": name, "cv_f1": search.best_score_,
            "precision": precision_score(y_test, predicted, zero_division=0),
            "recall": recall_score(y_test, predicted, zero_division=0),
            "f1": f1_score(y_test, predicted, zero_division=0),
            "roc_auc": roc_auc_score(y_test, score),
        })
        details[name] = {"best_parameters": search.best_params_,
                         "classification_report": classification_report(
                             y_test, predicted, output_dict=True, zero_division=0)}
        pd.DataFrame(search.cv_results_).to_csv(output / f"{name}_cv.csv", index=False)
        predictions[f"{name}_predicted"] = predicted
        predictions[f"{name}_score"] = score
        ConfusionMatrixDisplay.from_predictions(y_test, predicted, ax=ax,
                                                colorbar=False, cmap="Blues")
        ax.set_title(name)
        ax.grid(False)
        RocCurveDisplay.from_predictions(y_test, score, name=name, ax=ax_roc)
        if name == "DecisionTree":
            tree_pipeline = best
        print(metrics[-1], flush=True)
    plt.figure(fig_cm.number)
    save_figure(output / "confusion_matrices.png")
    ax_roc.plot([0, 1], [0, 1], "k--", label="Random classifier")
    ax_roc.legend()
    plt.figure(fig_roc.number)
    save_figure(output / "roc_curves.png")

    plt.figure(figsize=(24, 12))
    plot_tree(tree_pipeline.named_steps["model"],
              feature_names=tree_pipeline.named_steps["preprocess"].get_feature_names_out(),
              class_names=["No default", "Default"], filled=True,
              max_depth=3, fontsize=8)
    plt.title("Decision tree: first 4 levels (thresholds after StandardScaler)")
    save_figure(output / "decision_tree.png")

    result = pd.DataFrame(metrics)
    result.to_csv(output / "metrics.csv", index=False)
    predictions.to_csv(output / "predictions.csv", index=False)
    # Победителя определяем по CV на тренировочной выборке, не по тесту.
    winner = result.loc[result.cv_f1.idxmax(), "model"]
    details["experiment"] = {
        "python": platform.python_version(), "sklearn": sklearn.__version__,
        "train_rows": len(x_train), "test_rows": len(x_test),
        "train_class_counts": y_train.value_counts().to_dict(),
        "test_class_counts": y_test.value_counts().to_dict(),
        "selected_by_cv_f1": winner, "random_state": 42,
        "tree_depth": tree_pipeline.named_steps["model"].get_depth(),
    }
    (output / "results.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result.to_string(index=False))
    print(f"Selected by CV F1: {winner}")


if __name__ == "__main__":
    main()
