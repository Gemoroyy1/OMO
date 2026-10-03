"""Открыть результаты регрессии; --rebuild повторяет обработку и обучение."""
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
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    output = ROOT / "reports"
    images = [("Истинные и предсказанные ставки", "actual_predicted.png"),
              ("Остатки относительно прогноза", "residuals.png"),
              ("Распределения остатков", "residual_histograms.png"),
              ("Коэффициенты моделей", "coefficients.png")]
    for stage, label in [("raw", "исходные данные"), ("train_clean", "очищенная тренировочная выборка")]:
        for kind, title in [("histograms", "Гистограммы"), ("scatterplots", "Диаграммы рассеяния"),
                            ("boxplots", "Ящики с усами: ставка по категории кредита")]:
            images.append((f"{title} — {label}", f"{stage}_{kind}.png"))
    required = [output / filename for _, filename in images]
    required += [output / "metrics.csv", output / "results.json"]
    if args.rebuild or not all(path.exists() for path in required):
        subprocess.run([sys.executable, str(ROOT / "regression.py")], check=True)
    with (output / "metrics.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    details = json.loads((output / "results.json").read_text(encoding="utf-8"))
    experiment = details["experiment"]
    columns = ["model", "CV_RMSE", "MAE", "RMSE", "R2", "train_RMSE"]
    formatted = [[row["model"]] + [f'{float(row[key]):.6f}' for key in columns[1:]] for row in rows]
    md_table = '| ' + ' | '.join(columns) + ' |\n| ' + ' | '.join(['---'] * len(columns)) + ' |\n'
    md_table += '\n'.join('| ' + ' | '.join(row) + ' |' for row in formatted)
    summary = (f"Цель — процентная ставка loan_int_rate. После удаления "
               f"{experiment['removed_missing']} строк с пропусками и {experiment['removed_duplicates']} "
               f"дубликатов осталось {experiment['clean_rows']} строк. "
               f"Обучение: {experiment['train_rows']}, тест: {experiment['test_rows']}, seed=42.")
    method = ("Числовые признаки стандартизированы, категории кодируются OneHotEncoder с исключением "
              "базовой категории. loan_int_rate и loan_status исключены из признаков. Pipeline обучает "
              "преобразования внутри каждого из 5 фолдов KFold. Параметры выбираются по минимальной "
              "CV RMSE; тест используется только для итоговых метрик. LASSO перебирает alpha "
              "0.0001/0.001/0.01/0.1/1/10, Ridge — 0.01/0.1/1/10/100/1000. "
              "У обычной линейной регрессии подбираемого штрафа нет.")
    explanation = ("MAE — средняя абсолютная ошибка; RMSE сильнее штрафует большие ошибки. "
                   "Обе ошибки измеряются в процентных пунктах ставки: например, прогноз 11% вместо "
                   "10% даёт ошибку 1 п.п. R² сравнивает квадратичную ошибку модели с прогнозом "
                   "среднего значения; 0.904 означает около 90.4% объяснённой тестовой вариации, "
                   "а не долю точных ответов. Остаток = истинное значение − прогноз.")
    best = next(row for row in rows if row["model"] == experiment["selected_by_cv_rmse"])
    conclusion = (f"По CV RMSE выбрана {experiment['selected_by_cv_rmse']}. На тесте: "
                  f"MAE={float(best['MAE']):.4f} п.п., RMSE={float(best['RMSE']):.4f} п.п., "
                  f"R²={float(best['R2']):.4f}. Различия трёх моделей очень малы; заметного "
                  "преимущества регуляризации в этом запуске нет. "
                  f"LASSO обнулила {experiment['lasso_zero_coefficients']} коэффициентов. "
                  f"Базовый прогноз среднего тренировочной ставки: RMSE="
                  f"{experiment['baseline']['RMSE']:.4f} п.п., MAE={experiment['baseline']['MAE']:.4f} п.п., "
                  f"R²={experiment['baseline']['R2']:.4f}.")
    limitations = ("Сильный вклад имеют категории loan_grade: они отражают категорию кредита и "
                   "тесно связаны со ставкой. Результат описывает прогноз при уже известной категории; "
                   "порядок назначения категории и ставки в данных не установлен, поэтому это не "
                   "доказательство возможности предсказать ставку до кредитного решения. "
                   "Коэффициенты категорий сравниваются с базовой категорией, числовые — на одно "
                   "стандартное отклонение. Коэффициенты не доказывают причинность. Аномальные "
                   "возраст и стаж сохранены; удаление пропусков может менять состав выборки. "
                   "Оценка основана на одном случайном разбиении, без проверки переноса на другой период. "
                   "Полосы на графике прогнозов отражают сильное влияние loan_grade.")
    report = '# Лабораторная работа №3. Регрессия\n\n## Данные\n\n' + summary
    report += '\n\n## Методика\n\n' + method + '\n\n## Метрики на тесте\n\n' + md_table
    report += '\n\n' + explanation + '\n\n## Подобранные параметры\n\n'
    body = '<h1>Лабораторная №3. Регрессия</h1>'
    for title, paragraph in [("Данные", summary), ("Методика", method)]:
        body += f'<h2>{title}</h2><p>{html.escape(paragraph)}</p>'
    body += '<h2>Метрики</h2><div class="table"><table><tr>'
    body += ''.join(f'<th>{key}</th>' for key in columns) + '</tr>'
    body += ''.join('<tr>' + ''.join(f'<td>{value}</td>' for value in row) + '</tr>' for row in formatted)
    body += '</table></div><p>' + html.escape(explanation) + '</p>'
    for name in ["LinearRegression", "LASSO", "Ridge"]:
        parameters = json.dumps(details[name], ensure_ascii=False, indent=2)
        report += f'### {name}\n\n```json\n{parameters}\n```\n\n'
        body += f'<details><summary>{name}: параметры</summary><pre>{html.escape(parameters)}</pre></details>'
    report += '## Вывод\n\n' + conclusion + '\n\n## Ограничения и интерпретация\n\n' + limitations + '\n\n'
    body += '<h2>Вывод</h2><p>' + html.escape(conclusion) + '</p><h2>Интерпретация и ограничения</h2><p>' + html.escape(limitations) + '</p>'
    for title, filename in images:
        body += f'<h2>{html.escape(title)}</h2><a href="{filename}"><img src="{filename}" alt="{html.escape(title)}"></a>'
        report += f'## {title}\n\n![{title}]({filename})\n\n'
    report += ('## Воспроизводимость\n\nКод: Лаба3/regression.py. Просмотр: Лаба3/view_results.py. '
               'CSV: metrics.csv, predictions.csv, coefficients.csv, *_cv.csv. '
               'Параметры стандартизации сохранены в results.json, преобразованные train/test '
               'в Лаба3/processed/. Общие данные в data/ не перезаписываются. '
               f"Python {experiment['python']}, scikit-learn {experiment['sklearn']}; "
               'точные версии в Лаба3/requirements-lock.txt.\n')
    (output / "report.md").write_text(report, encoding="utf-8")
    body += '<p><a href="report.md">Отчёт</a> · <a href="predictions.csv">Предсказания CSV</a> · <a href="coefficients.csv">Коэффициенты CSV</a></p>'
    page = output / "results.html"
    page.write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Лаба3</title>'
                    '<style>body{font:17px Arial;max-width:1200px;margin:40px auto;padding:0 20px}'
                    'img{width:100%}.table{overflow:auto}table{border-collapse:collapse}'
                    'td,th{border:1px solid #ccc;padding:10px}pre{overflow:auto;background:#f4f6f8;padding:16px}'
                    'details{margin:16px 0}</style>' + body + '</html>', encoding="utf-8")
    print(page)
    if not args.no_open:
        webbrowser.open(page.as_uri())


if __name__ == "__main__":
    main()
