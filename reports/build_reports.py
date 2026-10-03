"""Сборка трёх PDF отчётов. Зависимости: reportlab, Pillow.

Титульные данные редактируются в reports/title_data.json.
Снимки фактических страниц: reports/capture_results.cjs.
"""
import csv
import json
import re
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                               Spacer, PageBreak, Image, Table, TableStyle, KeepTogether)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
WIDTH = A4[0] - 45 * mm
FONTDIR = Path('C:/Windows/Fonts')
pdfmetrics.registerFont(TTFont('TimesRU', str(FONTDIR / 'times.ttf')))
pdfmetrics.registerFont(TTFont('MonoRU', str(FONTDIR / 'cour.ttf')))
pdfmetrics.registerFontFamily('TimesRU', normal='TimesRU', bold='TimesRU', italic='TimesRU', boldItalic='TimesRU')
STYLES = {
    'body': ParagraphStyle('Body', fontName='TimesRU', fontSize=14, leading=21,
                           alignment=TA_JUSTIFY, firstLineIndent=12.5*mm, spaceAfter=6),
    'heading': ParagraphStyle('Heading', fontName='TimesRU', fontSize=14, leading=21,
                              firstLineIndent=12.5*mm, spaceBefore=12, spaceAfter=12, keepWithNext=True),
    'center': ParagraphStyle('Center', fontName='TimesRU', fontSize=14, leading=21,
                             alignment=TA_CENTER, spaceAfter=12),
    'caption': ParagraphStyle('Caption', fontName='TimesRU', fontSize=12, leading=18,
                              alignment=TA_CENTER, spaceAfter=12),
    'cell': ParagraphStyle('Cell', fontName='TimesRU', fontSize=12, leading=18,
                           alignment=TA_CENTER),
    'code': ParagraphStyle('Code', fontName='MonoRU', fontSize=12, leading=15,
                           alignment=TA_LEFT, spaceAfter=0),
}


class Report(BaseDocTemplate):
    def __init__(self, path, **kwargs):
        super().__init__(str(path), pagesize=A4, leftMargin=30*mm, rightMargin=15*mm,
                         topMargin=20*mm, bottomMargin=20*mm, **kwargs)
        frame = Frame(30*mm, 20*mm, WIDTH, A4[1]-40*mm,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='all', frames=frame, onPage=self.footer))
        self.page_map = []

    def beforeDocument(self):
        self.page_map = []

    def footer(self, canvas, doc):
        if doc.page > 1:
            canvas.setFont('TimesRU', 12)
            canvas.drawCentredString(A4[0]/2, 10*mm, str(doc.page))

    def afterFlowable(self, flowable):
        if hasattr(flowable, 'toc_title'):
            key = flowable.toc_key
            self.canv.bookmarkPage(key)
            self.notify('TOCEntry', (flowable.toc_level, flowable.toc_title, self.page, key))
            self.page_map.append({'heading': flowable.toc_title, 'page': self.page})


def clean_markup(text):
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    return text.replace('**', '').replace('`', '')


def paragraph(text, style='body'):
    return Paragraph(escape(clean_markup(text)), STYLES[style])


class Builder:
    def __init__(self, number, title):
        self.number, self.title = number, title
        self.items = []
        self.section = self.figure = self.table = self.heading_count = 0

    def text(self, text):
        self.items.append(paragraph(text))

    def heading(self, text, new_page=False, structural=False):
        if new_page:
            self.items.append(PageBreak())
        if not structural:
            self.section += 1
            text = f'{self.section} {text}'
        self.heading_count += 1
        p = paragraph(text, 'center' if structural else 'heading')
        p.toc_title = text
        p.toc_level = 0
        p.toc_key = f'h{self.heading_count}'
        p.keepWithNext = True
        self.items.append(p)

    def image(self, path, caption):
        self.figure += 1
        self.text(f'На рисунке {self.figure} представлен результат этапа: {caption.lower()}.')
        with PILImage.open(path) as im:
            w, h = im.size
        width = WIDTH
        height = width * h / w
        if height > 160*mm:
            width *= 160*mm/height
            height = 160*mm
        visual = Image(str(path), width=width, height=height)
        visual.hAlign = 'CENTER'
        label = paragraph(f'Рисунок {self.figure} - {caption}', 'caption')
        self.items.append(KeepTogether([visual, Spacer(1, 4*mm), label]))

    def add_table(self, rows, caption):
        self.table += 1
        self.text(f'В таблице {self.table} приведены {caption.lower()}.')
        title = paragraph(f'Таблица {self.table} - {caption}', 'caption')
        title.style = ParagraphStyle('TableTitle', parent=STYLES['caption'], alignment=TA_LEFT)
        title.keepWithNext = True
        self.items.append(title)
        cells = [[paragraph(clean_markup(value), 'cell') for value in row] for row in rows]
        widths = [WIDTH/len(rows[0])] * len(rows[0])
        if len(rows[0]) >= 5:
            widths = [WIDTH*.25] + [WIDTH*.75/(len(rows[0])-1)]*(len(rows[0])-1)
        table = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), .5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        self.items += [table, Spacer(1, 4*mm)]

    def code(self, letter, filename):
        self.heading(f'ПРИЛОЖЕНИЕ {letter}', new_page=True, structural=True)
        self.items.append(paragraph('(обязательное)', 'center'))
        self.items.append(paragraph(f'Программный код {filename.name}', 'center'))
        self.text(f'Приведён полный исходный текст файла {filename.relative_to(ROOT).as_posix()}. '
                  'Длинные строки перенесены только для печати; исходный файл в репозитории '
                  'сохраняет исходные переносы и отступы. Код выполнялся в среде Python проекта.')
        for line in filename.read_text(encoding='utf-8-sig').splitlines():
            # Печатный перенос без изменения исходного файла.
            width = int(WIDTH / pdfmetrics.stringWidth('0', 'MonoRU', 12))
            parts = textwrap.wrap(line.expandtabs(4), width=width,
                                  drop_whitespace=False, replace_whitespace=False,
                                  subsequent_indent='    ', break_long_words=True,
                                  break_on_hyphens=False) or [' ']
            for part in parts:
                self.items.append(Paragraph(escape(part).replace(' ', '&#160;'), STYLES['code']))


THEORY = {
    1: [
        'Классификация относится к обучению с учителем: по вектору признаков x модель определяет '
        'дискретную метку y. В данной работе положительный класс означает дефолт по кредиту. '
        'Обучение выполняется на размеченных наблюдениях, качество проверяется на данных, '
        'которые не использовались при выборе параметров.',
        'KNN определяет класс по ближайшим объектам обучающей выборки. Число соседей k '
        'задаёт степень сглаживания границы; веса по расстоянию усиливают вклад близких объектов. '
        'SVM строит разделяющую поверхность с большим зазором между классами. Параметр C '
        'задаёт штраф за ошибки, а ядро RBF позволяет моделировать нелинейную границу. '
        'Дерево решений последовательно проверяет условия на признаки. Ограничение глубины '
        'и минимального размера листа уменьшает сложность модели [3].',
        'Для матрицы ошибок TP - найденные дефолты, FP - ложные предсказания дефолта, '
        'FN - пропущенные дефолты, TN - верные ответы класса без дефолта. '
        'Precision = TP / (TP + FP); recall = TP / (TP + FN); '
        'F1 = 2 · precision · recall / (precision + recall). '
        'ROC-кривая показывает соотношение доли найденных положительных объектов '
        'и доли ложных срабатываний при изменении порога. ROC-AUC оценивает ранжирование '
        'объектов и не требует, чтобы оценка SVM была вероятностью.',
        'Масштабы числовых признаков влияют на расстояния KNN и SVM. '
        'Стандартизация вычисляет z = (x - μ) / σ. Параметры μ и σ определяются '
        'только по тренировочным объектам. OneHot-кодирование представляет категории '
        'индикаторными столбцами. Кросс-валидация многократно разделяет тренировочную '
        'выборку на обучающую и проверочную части; тест сохраняется для окончательной оценки.',
    ],
    2: [
        'Кластеризация - обучение без учителя: объекты объединяются по сходству признаков '
        'без использования известных меток. Кластер не обязан совпадать с классом дефолта, '
        'а номер кластера не имеет самостоятельного экономического значения.',
        'KMeans минимизирует сумму квадратов евклидовых расстояний объектов до центров '
        'их групп. Число групп задаётся заранее; несколько инициализаций уменьшают зависимость '
        'от начальных центров. DBSCAN находит плотные области по радиусу eps и минимальному '
        'числу соседей min_samples. Объекты, не присоединённые к плотным группам, считаются шумом '
        'и получают метку -1. Иерархическая агломеративная кластеризация начинает с отдельных '
        'объектов и последовательно объединяет группы; правило linkage определяет расстояние '
        'между ними. Ward ориентируется на прирост внутригрупповой суммы квадратов, '
        'average - на среднее межгрупповое расстояние [3].',
        'Silhouette для объекта определяется как s = (b - a) / max(a, b), '
        'где a - среднее расстояние внутри своей группы, b - минимальное среднее расстояние '
        'до другой группы. Большая оценка означает хорошее геометрическое разделение, '
        'но не доказывает содержательную полезность кластеров. ARI и AMI сравнивают '
        'разбиение с известными классами с поправкой на случайные совпадения. '
        'Номера групп при таком сравнении можно переставлять без изменения метрики.',
        'PCA строит ортогональные направления большой дисперсии. Проекция на две компоненты '
        'используется для визуализации, но может терять существенную часть информации. '
        'Экспертная оценка учитывает размеры групп, средние значения, типичные категории '
        'и доли дефолтов. Небольшая группа или шум не означают автоматически ошибку данных.',
    ],
    3: [
        'Регрессия относится к обучению с учителем и прогнозирует непрерывную величину. '
        'В этой работе прогнозируется процентная ставка loan_int_rate. Линейная модель '
        'имеет вид ŷ = β0 + Σ βj xj и выбирает коэффициенты по ошибкам тренировочных объектов.',
        'Обычная линейная регрессия минимизирует сумму квадратов остатков. '
        'LASSO добавляет L1-штраф α · Σ |βj| и может обнулять коэффициенты. '
        'Ridge добавляет L2-штраф α · Σ βj² и уменьшает величину коэффициентов. '
        'При увеличении α штраф усиливается. Числовые признаки масштабируются, чтобы '
        'штраф сопоставимо действовал на коэффициенты. При OneHot-кодировании одна '
        'базовая категория исключается, чтобы избежать линейной зависимости индикаторов [3].',
        'Для n тестовых объектов MAE = Σ |yi - ŷi| / n; '
        'RMSE = √(Σ (yi - ŷi)² / n). RMSE сильнее реагирует на большие ошибки. '
        'R² = 1 - Σ (yi - ŷi)² / Σ (yi - ȳ)² сравнивает модель с прогнозом '
        'среднего тестовых значений. R² - доля объяснённой вариации, а не доля точных ответов. '
        'Поскольку цель измеряется в процентах, MAE и RMSE выражены в процентных пунктах.',
        'Остаток равен yi - ŷi. График истинных и предсказанных значений показывает '
        'близость к идеальной диагонали, а график остатков помогает обнаружить систематические '
        'ошибки. Коэффициенты отражают условную связь при фиксированных других признаках '
        'и не доказывают причинность. Параметр α выбирается внутри тренировочной '
        'кросс-валидации; итоговое сравнение проводится на отдельном тесте.',
    ],
}

GOALS = {
    1: 'Получить и закрепить навыки предварительной обработки данных и применения '
       'методов машинного обучения для решения задачи классификации дефолта по кредиту.',
    2: 'Получить и закрепить навыки предварительной обработки данных и применения '
       'методов кластеризации для выделения и содержательной оценки групп заёмщиков.',
    3: 'Получить и закрепить навыки предварительной обработки данных и применения '
       'методов регрессии для прогнозирования процентной ставки по кредиту.',
}
TASKS = {
    1: ['Исследовать распределения и связи признаков, удалить пропуски и дубликаты.',
        'Разделить данные на обучение и тест, закодировать категории и масштабировать числа.',
        'Обучить KNN, SVM и дерево решений, подобрать параметры по кросс-валидации.',
        'Вычислить precision, recall, F1 и ROC-AUC; построить матрицы ошибок, ROC-кривые и дерево.',
        'Сравнить модели и сформулировать вывод с учётом пропущенных дефолтов.'],
    2: ['Подготовить общие признаки без loan_status и выбрать одинаковые объекты для всех методов.',
        'Обучить KMeans, DBSCAN и иерархическую кластеризацию, подобрать параметры.',
        'Оценить разделённость и сопоставить кластеры с реальными классами дефолта.',
        'Визуализировать разбиения и дендрограмму, исследовать профили и размеры групп.',
        'Дать экспертную оценку и объяснить ограничения найденного разбиения.'],
    3: ['Выбрать непрерывную цель и исключить её, а также исход кредита, из признаков.',
        'Выполнить визуализацию, удаление пропусков и дубликатов, масштабирование и кодирование.',
        'Обучить линейную регрессию, LASSO и Ridge, подобрать α по кросс-валидации.',
        'Вычислить MAE, RMSE и R²; построить графики прогнозов, остатков и коэффициентов.',
        'Сравнить модели с базовым прогнозом среднего и сформулировать вывод.'],
}

PROCESS = {
    1: [
        'Шаг 1. CSV прочитан с помощью pandas.read_csv. Функция visualize строит '
        'гистограммы числовых признаков, ящики с усами по классам дефолта и диаграммы рассеяния. '
        'Столбец loan_status отделён от 11 признаков. Загруженный файл хранится без изменений.',
        'Шаг 2. dropna удаляет строки с хотя бы одним пропуском; drop_duplicates оставляет '
        'по одной копии одинаковых строк. Для исследовательского CSV выполнена min-max '
        'нормализация: (x - min) / (max - min). Модели этот CSV не используют: '
        'их StandardScaler обучается отдельно внутри Pipeline, чтобы не переносить '
        'информацию теста в обучение. Корреляция Пирсона рассчитана только для числовых столбцов.',
        'Шаг 3. train_test_split выделяет 20% данных в тест с stratify=loan_status '
        'и random_state=42. В тренировочной выборке 17 850 объектов класса 0 и 4950 '
        'класса 1; в тесте 4463 и 1238 соответственно. Для каждой модели создан '
        'Pipeline из преобразований и классификатора.',
        'Шаг 4. GridSearchCV проверяет 6 конфигураций KNN, 6 SVM и 16 дерева '
        'на трёх стратифицированных фолдах. Выбор выполняется по F1 класса дефолта. '
        'Лучшая конфигурация каждого метода переобучается на всех 22 800 тренировочных строках.',
        'Шаг 5. На 5701 тестовой строке рассчитаны метрики и индивидуальные предсказания. '
        'Для ROC-AUC KNN и дерево используют вероятность класса 1, SVM - decision_function. '
        'Сохранены результаты всех комбинаций, матрицы ошибок, ROC-кривые и первые '
        'четыре уровня дерева. Полная глубина выбранного дерева равна 8.',
        'Шаг 6. Файл view_results.py собирает сохранённые метрики и изображения в локальную '
        'HTML-страницу. Ниже приведён снимок этой фактической страницы, подтверждающий '
        'наличие результатов. Для повторного обучения используется параметр --rebuild. '
        'Полный вычислительный код приведён в приложениях А и Б.',
    ],
    2: [
        'Шаг 1. Из общего исходного CSV удалены пропуски и дубликаты. После удаления '
        'loan_status сформированы числовые и категориальные признаки. Для сопоставимого '
        'эксперимента clean.sample с random_state=42 выбирает 4000 одинаковых строк '
        'для всех методов; цель не используется при отборе.',
        'Шаг 2. ColumnTransformer объединяет StandardScaler и OneHotEncoder. '
        'Получено 26 преобразованных признаков. Масштабирование выполняется по этой '
        'исследовательской выборке; отдельного теста нет, поскольку исследуются группы '
        'имеющихся объектов, а не прогноз для новых объектов.',
        'Шаг 3. KMeans проверяет число групп 2–8, n_init=10. DBSCAN проверяет 9 '
        'значений eps и min_samples=3/5/10/25. Иерархический метод проверяет число '
        'групп 2–8 и linkage=ward/average. Все модели работают в полном пространстве признаков.',
        'Шаг 4. Внутренний критерий - silhouette на не более чем 1500 объектах '
        'с фиксированным seed. Для DBSCAN шум исключён, требуется coverage ≥ 0.5 '
        'и не менее двух групп. Оценка выбора равна silhouette минус доля шума. '
        'Это эвристическое правило; оно не гарантирует равномерных или полезных групп.',
        'Шаг 5. После выбора параметров рассчитаны ARI, AMI, homogeneity и completeness '
        'по loan_status. Шум учитывается как отдельная группа -1. Для интерпретации '
        'сохранены численности, средние числовые признаки, типичные категории и доли дефолтов.',
        'Шаг 6. PCA используется только для двумерного рисунка. Дендрограмма отдельно '
        'построена по 150 объектам с выбранным правилом average. Файл view_results.py '
        'открывает метрики, профили и графики. Снимок страницы приведён ниже; '
        'полный вычислительный код расположен в приложении А.',
    ],
    3: [
        'Шаг 1. Целью выбрана ставка loan_int_rate, поскольку она является непрерывной. '
        'Из признаков удалены loan_int_rate и loan_status. Последний характеризует '
        'исход кредита и не используется для прогноза ставки. loan_grade сохранён '
        'как известная категория кредита; это существенное условие интерпретации.',
        'Шаг 2. После dropna и drop_duplicates выполняется разбиение 80/20 '
        'с random_state=42. В отличие от классификации, стратификация здесь не применяется. '
        'Гистограммы, ящики с усами и диаграммы рассеяния построены для исходной таблицы '
        'и отдельно для очищенной тренировочной части.',
        'Шаг 3. StandardScaler и OneHotEncoder(drop="first") включены в Pipeline. '
        'Категории представлены индикаторами без базового уровня. Средние и масштабы '
        'вычисляются только по обучающей части каждого фолда. Преобразованные train/test '
        'экспортированы отдельно в Лаба3/processed; общие данные не перезаписаны.',
        'Шаг 4. Линейная регрессия обучена без параметра штрафа. LASSO проверяет '
        'α=0.0001/0.001/0.01/0.1/1/10; Ridge - α=0.01/0.1/1/10/100/1000. '
        'GridSearchCV использует пять перемешанных фолдов и минимальную RMSE. '
        'max_iter=50000 ограничивает число итераций LASSO; лучшая модель сошлась за 18 итераций.',
        'Шаг 5. На отдельном тесте рассчитаны MAE, RMSE и R². Для сравнения '
        'DummyRegressor прогнозирует среднюю тренировочную ставку. Сохранены '
        'графики истинных и предсказанных значений, остатки, их распределения и коэффициенты.',
        'Шаг 6. view_results.py формирует отчёт и страницу результатов из CSV и JSON. '
        'Снимок фактической страницы подтверждает метрики и выбранные параметры. '
        'Программа обучения приведена целиком в приложении А.',
    ],
}


def add_markdown(builder, path):
    lines = path.read_text(encoding='utf-8').splitlines()
    block, i = [], 0
    def flush():
        if block:
            builder.text(' '.join(block)); block.clear()
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush(); i += 1; continue
        if line.startswith('# '):
            flush(); i += 1; continue
        if line.startswith('## '):
            flush(); title = line[3:]
            if title.startswith('Цель') or title in ['Вывод', 'Воспроизводимость']:
                i += 1
                while i < len(lines) and not lines[i].startswith('## '): i += 1
                continue
            builder.heading(title)
            i += 1; continue
        if line.startswith('### '):
            flush(); builder.items.append(paragraph(line[4:], 'heading')); i += 1; continue
        if line.startswith('```'):
            flush(); i += 1; code=[]
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i += 1
            builder.text('Параметры: ' + ' '.join(code)); i += 1; continue
        match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
        if match:
            flush(); builder.image(path.parent / match[2], match[1]); i += 1; continue
        if line.startswith('|'):
            flush(); rows=[]
            while i < len(lines) and lines[i].strip().startswith('|'):
                values=[v.strip() for v in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\-]+',v) for v in values): rows.append(values)
                i += 1
            builder.add_table(rows, 'Результаты сравнения моделей'); continue
        block.append(line); i += 1
    flush()


def build(number):
    title = {1:'Классификация',2:'Кластеризация',3:'Регрессия'}[number]
    b=Builder(number,title)
    meta=json.loads((ROOT/'reports/title_data.json').read_text(encoding='utf-8'))
    for key in ['university','faculty','department']:
        b.items.append(paragraph(meta[key], 'center'))
    b.items.append(Spacer(1,30*mm))
    for text in ['ОТЧЁТ',f'по лабораторной работе № {number}',title,
                 'по дисциплине',meta['discipline']]:
        b.items.append(paragraph(text,'center'))
    b.items.append(Spacer(1,20*mm))
    for text in [f"Выполнил: {meta['student']}", f"Группа: {meta['group']}",
                 f"Проверил: {meta['teacher']}", 'Подпись: __________________',
                 'Дата: __________________']:
        b.items.append(paragraph(text,'center'))
    b.items.append(Spacer(1,12*mm))
    b.items.append(paragraph(f"{meta['city']} {meta['year']}",'center'))
    b.items.append(PageBreak())
    b.items.append(paragraph('СОДЕРЖАНИЕ','center'))
    toc=TableOfContents()
    toc.levelStyles=[ParagraphStyle('TOC',fontName='TimesRU',fontSize=14,leading=21,
                                    leftIndent=0,firstLineIndent=0,spaceBefore=3)]
    b.items += [toc]
    b.heading('Цель и задачи работы',new_page=True)
    b.text(GOALS[number])
    b.text('Для достижения цели поставлены следующие задачи:')
    for task in TASKS[number]: b.text('- '+task)
    b.heading('Краткие теоретические сведения',new_page=True)
    for text in THEORY[number]: b.text(text)
    b.heading('Исходные данные и среда выполнения',new_page=True)
    b.text('Использован Credit Risk Dataset автора Lao Tse с Kaggle, лицензия CC0 [2]. '
           'Таблица содержит 32 581 запись и 12 столбцов. В person_emp_length отсутствуют '
           '895 значений, в loan_int_rate - 3116. После удаления строк с пропусками '
           'и 137 дубликатов осталось 28 501 наблюдение. Число удалённых строк с пропусками '
           'равно 3943, поскольку пропуски в двух столбцах могут встречаться в одной строке.')
    b.text('Числовые столбцы описывают возраст, доход, стаж, сумму кредита, ставку, '
           'отношение кредита к доходу и длительность кредитной истории. Категории '
           'описывают жильё, цель кредита, категорию кредита и историю дефолтов. '
           'loan_status - бинарный исход кредита. Исходный файл находится в '
           'data/raw/credit_risk_dataset.csv и сохраняется без изменений.')
    b.text('Расчёты выполнены средствами Python 3.12.14 и scikit-learn 1.9.1. '
           'pandas используется для таблиц, NumPy - для массивов, matplotlib и seaborn '
           'для графиков. Точные версии зависимостей сохранены в requirements-lock.txt '
           'соответствующей лабораторной. Аномалии возраста и стажа не удалялись; '
           'они учитываются как ограничение интерпретации результатов.')
    b.heading('Подробный процесс выполнения',new_page=True)
    for text in PROCESS[number]: b.text(text)
    b.text('Команда просмотра из корня проекта: .\\.venv\\Scripts\\python '
           f'Лаба{number}/view_results.py. Для повторного расчёта к команде добавляется --rebuild.')
    b.image(ROOT/f'Лаба{number}/reports/screenshots/results_page.png',
            'Снимок локальной страницы с результатами лабораторной')
    if number==1:
        b.heading('Визуализация предварительной обработки',new_page=True)
        for name,caption in [('histograms.png','Гистограммы очищенных числовых признаков'),
                             ('boxplots.png','Ящики с усами признаков по классу дефолта'),
                             ('scatterplots.png','Диаграммы рассеяния с классами дефолта')]:
            b.image(ROOT/'Лаба1/reports/figures/clean'/name,caption)
        b.image(ROOT/'Лаба1/reports/figures/correlation_matrix.png','Матрица корреляций числовых столбцов')
        b.text('Корреляция возраста и кредитной истории около 0.86. Наибольшая положительная '
               'линейная связь с дефолтом среди этих числовых столбцов наблюдается у '
               'loan_percent_income (около 0.38) и loan_int_rate (около 0.34). '
               'Это описательные связи, а не доказательство причинности или формальной значимости.')
    source=ROOT/f'Лаба{number}/reports'/('lab1/report.md' if number==1 else 'report.md')
    add_markdown(b,source)
    b.heading('ЗАКЛЮЧЕНИЕ',new_page=True,structural=True)
    conclusions={
        1:'Цель достигнута: освоен полный процесс классификации от очистки до оценки. '
          'Все задачи выполнены: построены графики признаков, удалены пропуски и дубликаты, '
          'обучены три метода с подбором параметров, рассчитаны четыре метрики и визуализировано '
          'дерево. По CV F1 выбрано дерево; на тесте F1=0.8055, ROC-AUC=0.9092. '
          'Высокий precision 0.9759 сочетается с recall 0.6858: найдено 849 из 1238 дефолтов, '
          '389 пропущены. Вывод о качестве ограничен одной выборкой и сохранёнными аномалиями.',
        2:'Цель достигнута: подготовлены признаки без целевой метки, обучены и настроены '
          'KMeans, DBSCAN и иерархический метод. Выполнены экспертная оценка, сравнение '
          'с реальными классами и визуализация. ARI около нуля показывает, что кластеры '
          'не воспроизводят дефолт. KMeans даёт интерпретируемые возрастные сегменты, '
          'два других метода отделяют малые необычные группы. Отрицательный результат '
          'сопоставления классов не означает невыполнение задачи кластеризации. '
          'Вывод относится к случайной выборке из 4000 объектов и выбранному представлению.',
        3:'Цель достигнута: выполнены очистка, визуализация и масштабирование данных, '
          'обучены линейная регрессия, LASSO и Ridge, подобраны параметры и оценены '
          'прогнозы. Все модели имеют RMSE около 1 процентного пункта и R² около 0.904 '
          'против RMSE 3.2215 у прогноза среднего. По CV выбрана LASSO с α=0.0001, '
          'но различия методов пренебрежимо малы. Результат предполагает заранее известную '
          'категорию кредита loan_grade и не доказывает причинную связь признаков со ставкой.'}
    b.text(conclusions[number])
    b.heading('СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ',new_page=True,structural=True)
    links={1:'neighbors',2:'clustering',3:'linear_model'}
    refs=[
        '1. ГОСТ 7.32-2001. Отчёт о научно-исследовательской работе. Структура и правила '
        'оформления. URL: https://meganorm.ru/Data2/1/4294847/4294847312.htm '
        '(дата обращения: 03.10.2026).',
        '2. Lao Tse. Credit Risk Dataset. Kaggle. URL: '
        'https://www.kaggle.com/datasets/laotse/credit-risk-dataset (дата обращения: 03.10.2026).',
        f'3. Scikit-learn. Руководство пользователя. URL: https://scikit-learn.org/stable/modules/{links[number]}.html '
        '(дата обращения: 03.10.2026).',
        '4. Исходный код и сохранённые результаты проекта ОМО. URL: '
        'https://github.com/Gemoroyy1/OMO (дата обращения: 03.10.2026).',
    ]
    for ref in refs: b.text(ref)
    if number==1:
        b.code('А',ROOT/'Лаба1/preprocessing.py')
        b.code('Б',ROOT/'Лаба1/classification.py')
    else:
        b.code('А',ROOT/f'Лаба{number}'/('clustering.py' if number==2 else 'regression.py'))
    output=ROOT/f'Лаба{number}/reports/report_gost.pdf'
    doc=Report(output,title=f'Лабораторная работа {number} {title}',author='')
    doc.multiBuild(b.items)
    (ROOT/f'tmp/report_{number}_pages.json').write_text(json.dumps(doc.page_map,ensure_ascii=False,indent=2),encoding='utf-8')
    print(output)


if __name__=='__main__':
    (ROOT/'tmp').mkdir(exist_ok=True)
    for number in [1,2,3]: build(number)
