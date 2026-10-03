"""Все результаты в браузере. --rebuild пересчитывает лабораторную."""

import argparse
import csv
import html
import json
from pathlib import Path
import subprocess
import sys
import webbrowser


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="Повторить обработку и обучение")
    parser.add_argument("--no-open", action="store_true", help="Создать страницу без открытия браузера")
    args = parser.parse_args()
    images = [("Матрицы ошибок", "lab1/confusion_matrices.png"),
              ("ROC-кривые", "lab1/roc_curves.png"),
              ("Дерево решений: первые четыре уровня", "lab1/decision_tree.png"),
              ("Матрица корреляций", "figures/correlation_matrix.png")]
    for state, label in [("raw", "до очистки"), ("clean", "после очистки")]:
        for filename, title in [("histograms", "Гистограммы"),
                                ("boxplots", "Ящики с усами"),
                                ("scatterplots", "Диаграммы рассеяния")]:
            images.append((f"{title} {label}", f"figures/{state}/{filename}.png"))
    required = [ROOT / "reports" / path for _, path in images]
    required += [ROOT / "reports/lab1/metrics.csv", ROOT / "reports/lab1/results.json",
                 ROOT.parent / "data/processed/preprocessing_report.json"]
    if args.rebuild or not all(path.exists() for path in required):
        for script in ["preprocessing.py", "classification.py"]:
            subprocess.run([sys.executable, str(ROOT / script)], check=True)
    with (ROOT / "reports/lab1/metrics.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    details = json.loads((ROOT / "reports/lab1/results.json").read_text(encoding="utf-8"))
    clean = json.loads((ROOT.parent / "data/processed/preprocessing_report.json").read_text(encoding="utf-8"))
    escape = html.escape
    body = "<h1>Лабораторная №1. Классификация</h1>"
    body += (f"<p>Исходных строк: {clean['original_rows']}; удалено с пропусками: "
             f"{clean['removed_missing_rows']}; дубликатов: {clean['removed_duplicate_rows']}; "
             f"осталось: {clean['clean_rows']}.</p>")
    experiment = details["experiment"]
    body += (f"<p>Обучение: {experiment['train_rows']} строк; тест: {experiment['test_rows']}. "
             "Подбор параметров: 3 фолда CV, критерий F1 класса «дефолт».</p>")
    body += "<h2>Метрики</h2><p>Precision, recall и F1 относятся к классу 1 — дефолту.</p>"
    keys = ["model", "cv_f1", "precision", "recall", "f1", "roc_auc"]
    body += "<table><tr>" + "".join(f"<th>{escape(key)}</th>" for key in keys) + "</tr>"
    for row in rows:
        body += "<tr>" + "".join(f"<td>{escape(row[key]) if key == 'model' else format(float(row[key]), '.4f')}</td>" for key in keys) + "</tr>"
    body += "</table><p>Выбрана по CV F1: " + escape(experiment["selected_by_cv_f1"]) + ".</p>"
    body += "<p>Дерево нашло 849 из 1238 дефолтов и пропустило 389. Выбросы пока сохранены.</p>"
    for name in ["KNN", "SVM", "DecisionTree"]:
        body += f"<details><summary>{name}: параметры и метрики обоих классов</summary><pre>"
        body += escape(json.dumps(details[name], ensure_ascii=False, indent=2)) + "</pre></details>"
    for title, path in images:
        body += f'<h2>{escape(title)}</h2><a href="{path}"><img src="{path}" alt="{escape(title)}"></a>'
    body += '<p><a href="lab1/report.md">Подробный отчёт</a> · <a href="lab1/predictions.csv">Предсказания CSV</a></p>'
    page = ROOT / "reports/Все_результаты.html"
    page.write_text('<!doctype html><html lang="ru"><meta charset="utf-8">'
                    '<title>Лабораторная №1</title><style>'
                    'body{font:17px Arial;max-width:1200px;margin:40px auto;padding:0 20px;color:#172334}'
                    'img{width:100%;height:auto}table{border-collapse:collapse}td,th{padding:12px;border:1px solid #ccc}'
                    'details{margin:16px 0}pre{overflow:auto;background:#f4f6f8;padding:16px}'
                    '</style>' + body + '</html>', encoding="utf-8")
    print(page)
    if not args.no_open:
        webbrowser.open(page.as_uri())


if __name__ == "__main__":
    main()
