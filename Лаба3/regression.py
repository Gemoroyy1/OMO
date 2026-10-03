"""Лабораторная №3: прогноз процентной ставки. python Лаба3/regression.py."""

import os
from pathlib import Path
import json
import platform

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("OMP_NUM_THREADS", "2")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression, Lasso, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET = "loan_int_rate"
NUMERIC = ["person_age", "person_income", "person_emp_length", "loan_amnt",
           "loan_percent_income", "cb_person_cred_hist_length"]
OUTPUT = ROOT / "reports"


def save(name):
    plt.tight_layout()
    plt.savefig(OUTPUT / name, dpi=150, bbox_inches="tight")
    plt.close()


def make_pipeline(model, categories):
    transform = ColumnTransformer([
        ("numeric", StandardScaler(), NUMERIC),
        # Базовая категория исключена: устраняем зависимость dummy-столбцов.
        ("category", OneHotEncoder(drop="first", handle_unknown="ignore",
                                   sparse_output=False), categories),
    ])
    return Pipeline([("preprocess", transform), ("model", model)])


def visualize(data, stage):
    selected = NUMERIC + [TARGET]
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    for ax, feature in zip(axes.flat, selected):
        sns.histplot(data=data, x=feature, bins=40, ax=ax)
    for ax in list(axes.flat)[len(selected):]:
        ax.set_visible(False)
    save(f"{stage}_histograms.png")
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    for ax, feature in zip(axes, ["loan_amnt", "person_income", "person_age"]):
        sns.scatterplot(data=data, x=feature, y=TARGET, alpha=0.15, s=10, ax=ax)
    save(f"{stage}_scatterplots.png")
    plt.figure(figsize=(11, 6))
    sns.boxplot(data=data, x="loan_grade", y=TARGET, order=list("ABCDEFG"))
    save(f"{stage}_boxplots.png")


def evaluate(actual, predicted):
    return {"MAE": float(mean_absolute_error(actual, predicted)),
            "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
            "R2": float(r2_score(actual, predicted))}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    processed = ROOT / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    raw = pd.read_csv(ROOT.parent / "data/raw/credit_risk_dataset.csv")
    complete = raw.dropna()
    clean = complete.drop_duplicates()
    # loan_status — исход кредита, его нельзя использовать для прогноза ставки.
    x = clean.drop(columns=[TARGET, "loan_status"])
    y = clean[TARGET]
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)
    # Исследуем признаки только тренировочной части: тест остаётся для итоговой оценки.
    visualize(clean.loc[x_train.index], "train_clean")
    # Для иллюстрации очистки до обучения — весь исходный набор отдельно.
    # Эти графики не используются для подбора параметров.
    visualize(raw, "raw")
    categories = [name for name in x if name not in NUMERIC]
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    models = {
        "LinearRegression": (LinearRegression(), {}),
        "LASSO": (Lasso(max_iter=50000), {"model__alpha": [0.0001, 0.001, 0.01, 0.1, 1, 10]}),
        "Ridge": (Ridge(), {"model__alpha": [0.01, 0.1, 1, 10, 100, 1000]}),
    }
    rows, details, coefficients = [], {}, []
    predictions = pd.DataFrame({"source_row": x_test.index, "actual": y_test.to_numpy()})
    fig_predictions, axes_predictions = plt.subplots(1, 3, figsize=(17, 5))
    fig_residuals, axes_residuals = plt.subplots(1, 3, figsize=(17, 5))
    fig_hist, axes_hist = plt.subplots(1, 3, figsize=(17, 5))
    baseline = DummyRegressor(strategy="mean").fit(x_train, y_train)
    baseline_metrics = evaluate(y_test, baseline.predict(x_test))
    final_pipeline = None
    for ax_p, ax_r, ax_h, (name, (model, grid)) in zip(
            axes_predictions, axes_residuals, axes_hist, models.items()):
        print(f"Training {name}...", flush=True)
        search = GridSearchCV(make_pipeline(model, categories), grid, cv=cv,
                              scoring="neg_root_mean_squared_error", n_jobs=2, error_score="raise")
        search.fit(x_train, y_train)
        best = search.best_estimator_
        predicted = best.predict(x_test)
        residual = y_test.to_numpy() - predicted
        row = {"model": name, "CV_RMSE": float(-search.best_score_), **evaluate(y_test, predicted)}
        row["train_RMSE"] = evaluate(y_train, best.predict(x_train))["RMSE"]
        rows.append(row)
        predictions[name] = predicted
        details[name] = {"best_parameters": search.best_params_,
                         "intercept": float(best.named_steps["model"].intercept_),
                         "iterations": int(best.named_steps["model"].n_iter_) if name == "LASSO" else None}
        pd.DataFrame(search.cv_results_).to_csv(OUTPUT / f"{name}_cv.csv", index=False)
        coefficients.append(pd.DataFrame({"model": name,
            "feature": best.named_steps["preprocess"].get_feature_names_out(),
            "coefficient": best.named_steps["model"].coef_}))
        ax_p.scatter(y_test, predicted, alpha=0.15, s=10)
        bounds = [min(y_test.min(), predicted.min()), max(y_test.max(), predicted.max())]
        ax_p.plot(bounds, bounds, "r--")
        ax_p.set(xlabel="Actual interest rate (%)", ylabel="Predicted interest rate (%)", title=name)
        ax_r.scatter(predicted, residual, alpha=0.15, s=10)
        ax_r.axhline(0, color="red", linestyle="--")
        ax_r.set(xlabel="Predicted interest rate (%)", ylabel="Actual - predicted (pp)", title=name)
        sns.histplot(residual, bins=40, ax=ax_h)
        ax_h.set(xlabel="Residual (percentage points)", title=name)
        final_pipeline = best
        print(row, flush=True)
    for fig, name in [(fig_predictions, "actual_predicted.png"),
                      (fig_residuals, "residuals.png"), (fig_hist, "residual_histograms.png")]:
        plt.figure(fig.number)
        save(name)
    coef = pd.concat(coefficients, ignore_index=True)
    coef.to_csv(OUTPUT / "coefficients.csv", index=False)
    top = coef.groupby("feature").coefficient.apply(lambda s: s.abs().max()).nlargest(12).index
    plt.figure(figsize=(13, 9))
    sns.barplot(data=coef[coef.feature.isin(top)], x="coefficient", y="feature", hue="model")
    save("coefficients.png")
    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUTPUT / "metrics.csv", index=False)
    predictions.to_csv(OUTPUT / "predictions.csv", index=False)
    # Экспорт стандартизированных признаков с параметрами только тренировочной выборки.
    prep = final_pipeline.named_steps["preprocess"]
    for name, subset, target in [("train", x_train, y_train), ("test", x_test, y_test)]:
        transformed = pd.DataFrame(prep.transform(subset), columns=prep.get_feature_names_out())
        transformed.insert(0, "source_row", subset.index)
        transformed[TARGET] = target.to_numpy()
        transformed.to_csv(processed / f"{name}_transformed.csv", index=False)
    scaler = prep.named_transformers_["numeric"]
    winner = metrics.loc[metrics.CV_RMSE.idxmin(), "model"]
    details["experiment"] = {
        "target": TARGET, "excluded": ["loan_status"], "original_rows": len(raw),
        "removed_missing": len(raw)-len(complete), "removed_duplicates": len(complete)-len(clean),
        "clean_rows": len(clean), "train_rows": len(x_train), "test_rows": len(x_test),
        "random_state": 42, "selected_by_cv_rmse": winner, "baseline": baseline_metrics,
        "numeric_mean": dict(zip(NUMERIC, scaler.mean_.tolist())),
        "numeric_scale": dict(zip(NUMERIC, scaler.scale_.tolist())),
        "python": platform.python_version(), "sklearn": sklearn.__version__,
        "lasso_zero_coefficients": int((coef.loc[coef.model == "LASSO", "coefficient"] == 0).sum()),
    }
    (OUTPUT / "results.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(metrics.to_string(index=False))
    print("Selected by CV RMSE:", winner)


if __name__ == "__main__":
    main()
