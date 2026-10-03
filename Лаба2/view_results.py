"""Открыть результаты лабораторной №2; --rebuild повторяет кластеризацию."""
import argparse
import csv
import html
import json
from pathlib import Path
import subprocess
import sys
import webbrowser

ROOT = Path(__file__).resolve().parent


def table(path):
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    return '<div class="table"><table>' + ''.join(
        '<tr>' + ''.join(f'<{"th" if i == 0 else "td"}>{html.escape(value)}</{"th" if i == 0 else "td"}>'
                        for value in row) + '</tr>' for i, row in enumerate(rows)) + '</table></div>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    output = ROOT / "reports"
    images = [("Разбиения и реальные классы в PCA", "partitions_pca.png"),
              ("Сравнение кластеров с реальными классами", "classes_comparison.png"),
              ("Иллюстративная дендрограмма", "dendrogram.png")]
    required = [output / name for _, name in images]
    required += [output / name for name in ["metrics.csv", "cluster_profiles.csv", "results.json"]]
    if args.rebuild or not all(path.exists() for path in required):
        subprocess.run([sys.executable, str(ROOT / "clustering.py")], check=True)
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    body = '<h1>Лабораторная №2. Кластеризация</h1>'
    body += (f'<p>После очистки: {results["clean_rows"]} строк. Все методы сравниваются на '
             f'одинаковой случайной выборке из {results["sample_rows"]} строк. '
             'loan_status исключён из признаков и использован только для оценки.</p>')
    body += '<h2>Метрики</h2>' + table(output / "metrics.csv")
    body += ('<p>Silhouette оценивает разделённость групп; шум DBSCAN исключён из него. '
             'Coverage — доля объектов без шума. ARI и AMI сравнивают разбиения независимо '
             'от номеров кластеров: близость к нулю означает слабое соответствие реальным классам. '
             'В сравнении классов шум −1 учитывается как отдельная группа.</p>')
    body += '<h2>Подобранные параметры</h2><pre>' + html.escape(
        json.dumps(results["selected_parameters"], ensure_ascii=False, indent=2)) + '</pre>'
    body += ('<h2>Экспертная оценка</h2><p>K-средних выделяет более старших заёмщиков '
             'с длинной кредитной историей и более молодых. Доля дефолтов в группах: 17,8% и 23,5%. '
             'DBSCAN помещает 3978 объектов в основную группу, 4 — в малую, 18 считает шумом. '
             'Иерархический метод выделяет основную группу из 3970 объектов, группу из 29 '
             'и отдельную аномальную запись с возрастом 144 года и доходом 6 млн. '
             'Высокий silhouette последних двух методов отражает отделение малых необычных групп. '
             'Все методы имеют ARI около нуля и не воспроизводят классы дефолта.</p>')
    body += ('<p>Вывод относится к сохранённому запуску (seed=42). При пересчёте с изменёнными '
             'данными ориентируйтесь на обновлённые таблицы. PCA сохраняет около 40% дисперсии; '
             'на графиках показана проекция, а модели обучались на всех 26 преобразованных признаках. '
             'Дендрограмма иллюстрирует отдельную подвыборку из 150 объектов.</p>')
    for title, name in images:
        body += f'<h2>{title}</h2><a href="{name}"><img src="{name}" alt="{title}"></a>'
    body += '<h2>Профили кластеров в исходных единицах</h2>' + table(output / "cluster_profiles.csv")
    body += '<p><a href="report.md">Отчёт</a> · <a href="predictions.csv">Разбиения CSV</a> · <a href="parameter_search.csv">Подбор параметров CSV</a></p>'
    page = output / "results.html"
    page.write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Лаба2</title>'
                    '<style>body{font:17px Arial;max-width:1200px;margin:40px auto;padding:0 20px}'
                    'img{width:100%}.table{overflow:auto}table{border-collapse:collapse}'
                    'td,th{border:1px solid #ccc;padding:10px}pre{background:#f4f6f8;padding:20px}</style>'
                    + body + '</html>', encoding="utf-8")
    print(page)
    if not args.no_open:
        webbrowser.open(page.as_uri())


if __name__ == "__main__":
    main()
