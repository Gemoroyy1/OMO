"""Учебная предварительная обработка Credit Risk Dataset.

Запуск: python preprocessing.py
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
import matplotlib

matplotlib.use("Agg")  # Сохраняем графики в файлы без открытия окон.
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


FEATURES = [
    "person_age", "person_income", "person_emp_length", "loan_amnt",
    "loan_int_rate", "loan_percent_income", "cb_person_cred_hist_length",
]
TARGET = "loan_status"


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


def visualize(data: pd.DataFrame, directory: Path) -> None:
    """Распределения и связь признаков с дефолтом до/после очистки."""
    directory.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    for ax, feature in zip(axes.flat, FEATURES):
        sns.histplot(data=data, x=feature, bins=40, ax=ax)
    for ax in list(axes.flat)[len(FEATURES):]:
        ax.set_visible(False)
    save_figure(directory / "histograms.png")

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    for ax, feature in zip(axes.flat, FEATURES):
        sns.boxplot(data=data, x=TARGET, y=feature, ax=ax)
    for ax in list(axes.flat)[len(FEATURES):]:
        ax.set_visible(False)
    save_figure(directory / "boxplots.png")

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    pairs = [("person_income", "loan_amnt"),
             ("person_age", "person_emp_length"),
             ("loan_int_rate", "loan_percent_income")]
    for ax, (x, y) in zip(axes, pairs):
        sns.scatterplot(data=data, x=x, y=y, hue=TARGET,
                        palette={0: "steelblue", 1: "darkorange"},
                        alpha=0.25, s=12, ax=ax)
    save_figure(directory / "scatterplots.png")


def main() -> None:
    sns.set_theme(style="whitegrid")
    raw = pd.read_csv(ROOT / "data/raw/credit_risk_dataset.csv")
    output = ROOT / "data/processed"
    figures = ROOT / "reports/figures"
    output.mkdir(parents=True, exist_ok=True)
    visualize(raw, figures / "raw")

    complete = raw.dropna().copy()
    clean = complete.drop_duplicates().copy()
    clean.to_csv(output / "credit_risk_clean.csv", index=False)
    visualize(clean, figures / "clean")

    minimum = clean[FEATURES].min()
    maximum = clean[FEATURES].max()
    span = (maximum - minimum).replace(0, 1)
    normalized = clean.copy()
    normalized[FEATURES] = (clean[FEATURES] - minimum) / span
    normalized.to_csv(output / "credit_risk_normalized.csv", index=False)

    correlation = clean[FEATURES + [TARGET]].corr(method="pearson")
    correlation.to_csv(output / "correlation.csv")
    plt.figure(figsize=(11, 9))
    sns.heatmap(correlation, annot=True, fmt=".2f", cmap="coolwarm",
                vmin=-1, vmax=1, center=0, square=True)
    save_figure(figures / "correlation_matrix.png")

    report = {
        "original_rows": len(raw),
        "missing_by_column": raw.isna().sum().to_dict(),
        "removed_missing_rows": len(raw) - len(complete),
        "removed_duplicate_rows": len(complete) - len(clean),
        "clean_rows": len(clean),
        "normalization_min": minimum.to_dict(),
        "normalization_max": maximum.to_dict(),
        "employment_exceeds_age_rows": int(
            (clean.person_emp_length > clean.person_age).sum()
        ),
    }
    (output / "preprocessing_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
