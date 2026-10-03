"""Лабораторная №2. Запуск: python Лаба2/clustering.py."""

import os
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("OMP_NUM_THREADS", "2")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.metrics import (silhouette_score, adjusted_rand_score,
                             adjusted_mutual_info_score, homogeneity_score,
                             completeness_score)
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = ["person_age", "person_income", "person_emp_length", "loan_amnt",
           "loan_int_rate", "loan_percent_income", "cb_person_cred_hist_length"]
TARGET = "loan_status"
OUTPUT = ROOT / "reports"


def save(name):
    plt.tight_layout()
    plt.savefig(OUTPUT / name, dpi=150, bbox_inches="tight")
    plt.close()


def internal_score(x, labels):
    """Шум исключён из silhouette; coverage учитывает его долю отдельно."""
    mask = labels != -1
    count = len(np.unique(labels[mask]))
    coverage = float(mask.mean())
    if count < 2 or count >= mask.sum():
        return count, coverage, None
    # Фиксированная подвыборка ограничивает стоимость попарных расстояний.
    try:
        score = float(silhouette_score(x[mask], labels[mask],
                                      sample_size=min(1500, int(mask.sum())), random_state=42))
    except ValueError:
        score = None
    return count, coverage, score


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    source = ROOT.parent / "data/raw/credit_risk_dataset.csv"
    raw = pd.read_csv(source)
    complete = raw.dropna()
    clean = complete.drop_duplicates()
    # Одинаковая случайная выборка для всех методов; цель не участвует в отборе.
    data = clean.sample(n=min(4000, len(clean)), random_state=42).copy()
    features = data.drop(columns=TARGET)
    categories = [name for name in features if name not in NUMERIC]
    encoder = ColumnTransformer([
        ("numeric", StandardScaler(), NUMERIC),
        ("category", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categories),
    ])
    x = encoder.fit_transform(features)
    candidates, selected = [], {}
    for method in ["KMeans", "DBSCAN", "Hierarchical"]:
        print(f"Selecting {method}...", flush=True)
        best_value = -np.inf
        configs = ([{"n_clusters": k} for k in range(2, 9)] if method == "KMeans"
                   else [{"eps": eps, "min_samples": n}
                         for eps in [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0] for n in [3, 5, 10, 25]]
                   if method == "DBSCAN" else
                   [{"n_clusters": k, "linkage": how} for k in range(2, 9)
                    for how in ["ward", "average"]])
        for config in configs:
            model = (KMeans(**config, random_state=42, n_init=10) if method == "KMeans"
                     else DBSCAN(**config, n_jobs=2) if method == "DBSCAN"
                     else AgglomerativeClustering(**config))
            labels = model.fit_predict(x)
            count, coverage, silhouette = internal_score(x, labels)
            # DBSCAN: не допускаем выбора малого островка с высоким silhouette.
            valid = silhouette is not None and coverage >= 0.5
            value = silhouette - (1 - coverage) if valid else None
            candidates.append({"method": method, "parameters": json.dumps(config),
                               "clusters": count, "coverage": coverage,
                               "silhouette": silhouette, "selection_score": value})
            if value is not None and value > best_value:
                best_value = value
                selected[method] = (labels.copy(), config)
        if method not in selected:
            pd.DataFrame(candidates).to_csv(OUTPUT / "parameter_search.csv", index=False)
            raise RuntimeError(f"No valid {method} partition: inspect grid and representation")
        print(method, selected[method][1], flush=True)
    pd.DataFrame(candidates).to_csv(OUTPUT / "parameter_search.csv", index=False)
    pca = PCA(n_components=2, random_state=42)
    points = pca.fit_transform(x)
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    sns.scatterplot(x=points[:, 0], y=points[:, 1], hue=data[TARGET].to_numpy(),
                    palette="Set1", s=14, alpha=0.5, ax=axes[0, 0])
    axes[0, 0].set_title("Real classes: loan_status")
    metrics, profiles, comparisons = [], [], []
    predictions = pd.DataFrame({"source_row": data.index, "actual": data[TARGET].to_numpy(),
                                "PCA1": points[:, 0], "PCA2": points[:, 1]})
    for ax, (method, (labels, config)) in zip(list(axes.flat)[1:], selected.items()):
        count, coverage, silhouette = internal_score(x, labels)
        y = data[TARGET].to_numpy()
        metrics.append({"method": method, "clusters": count, "coverage": coverage,
                        "noise_rows": int((labels == -1).sum()), "silhouette": silhouette,
                        "ARI": adjusted_rand_score(y, labels),
                        "AMI": adjusted_mutual_info_score(y, labels),
                        "homogeneity": homogeneity_score(y, labels),
                        "completeness": completeness_score(y, labels)})
        predictions[method] = labels
        sns.scatterplot(x=points[:, 0], y=points[:, 1], hue=labels.astype(str),
                        palette="tab10", alpha=0.5, s=14, ax=ax)
        ax.set_title(method + " (-1 = noise)")
        grouped = data.assign(cluster=labels).groupby("cluster")
        summary = grouped[NUMERIC].mean()
        summary["rows"] = grouped.size()
        summary["default_rate"] = grouped[TARGET].mean()
        for category in categories:
            summary[category + "_mode"] = grouped[category].agg(lambda s: s.mode().iloc[0])
        summary.insert(0, "method", method)
        profiles.append(summary.reset_index())
        cross = pd.crosstab(labels, y).reindex(columns=[0, 1], fill_value=0)
        cross.index.name = "cluster"
        cross.insert(0, "method", method)
        comparisons.append(cross.reset_index())
    for ax in axes.flat:
        ax.set_xlabel("PCA1")
        ax.set_ylabel("PCA2")
    save("partitions_pca.png")
    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    for ax, (method, (labels, _)) in zip(axes, selected.items()):
        table = pd.crosstab(labels, data[TARGET].to_numpy()).reindex(columns=[0, 1], fill_value=0)
        sns.heatmap(table, annot=True, fmt="d", cmap="Blues", ax=ax, cbar=False)
        ax.set_title(method)
        ax.set_xlabel("Real class")
        ax.set_ylabel("Cluster (-1 = noise)")
    save("classes_comparison.png")
    # Отдельная иллюстративная дендрограмма: 150 объектов из той же выборки.
    plt.figure(figsize=(16, 7))
    tree = linkage(x[:150], method=selected["Hierarchical"][1]["linkage"])
    dendrogram(tree, truncate_mode="lastp", p=25)
    plt.title("Hierarchical dendrogram: 150 objects, 25 terminal groups")
    plt.xlabel("Group / object (parentheses = group size)")
    plt.ylabel("Merge distance")
    save("dendrogram.png")
    pd.DataFrame(metrics).to_csv(OUTPUT / "metrics.csv", index=False)
    pd.concat(profiles, ignore_index=True).to_csv(OUTPUT / "cluster_profiles.csv", index=False)
    pd.concat(comparisons, ignore_index=True).to_csv(OUTPUT / "class_counts.csv", index=False)
    predictions.to_csv(OUTPUT / "predictions.csv", index=False)
    details = {"source": "data/raw/credit_risk_dataset.csv", "original_rows": len(raw),
               "removed_missing": len(raw) - len(complete), "removed_duplicates": len(complete)-len(clean),
               "clean_rows": len(clean), "sample_rows": len(data), "random_state": 42,
               "encoded_features": list(encoder.get_feature_names_out()),
               "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
               "selected_parameters": {method: config for method, (_, config) in selected.items()}}
    (OUTPUT / "results.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(pd.DataFrame(metrics).to_string(index=False))


if __name__ == "__main__":
    main()
