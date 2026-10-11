"""Аудит, ЗАГАЛЬНИЙ вид: те саме вимірювання словами власника бізнесу.

Видів звіту два, і зовні вони так і звуться — «загальний» і «технічний»
(рішення власника 2026-09-06). Технічний відповідає на питання «що
зламано»; цей відповідає на питання «чи варто цим займатися» і має
схилити до «так». Дані під обома ті самі: `ReportDocument` один.

Через це в ньому немає жодного технічного терміна, кожен блок
починається з наочності, а не з тексту, і всі числа подані у формі
«зараз / може бути». Джерело даних те саме, що й у решти звітів, —
вигадувати оптимістичні цифри не можна, інакше документ перестає бути
аудитом і стає рекламою.

Графіка малюється таблицями із заливкою комірок: python-docx не вміє
діаграм, а тягнути matplotlib заради п'яти смужок означало б додати
системну залежність до кожного контейнера.

Документ має два режими. Базовий — усе, що видно нижче: чистий Python,
жодного виклику моделі, працює завжди й без ключа. Розширений додає до
нього те, чого шаблон не вміє, — переказ знахідок словами про цей
конкретний бізнес. Розширення передається готовим (`extras`), а не
робиться тут: рендер документа лишається синхронним і без мережі, а
модель викликається там, де це видно.
"""

from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml.parser import OxmlElement
from docx.shared import Cm, Pt, RGBColor

from app.audit.i18n import Locale
from app.report.docx_brand import (
    BRAND_BROWN,
    LOGO,
    MUTED,
    add_footer,
    set_column_widths,
    style_document,
    style_table,
)
from app.report.i18n import locale_of, t
from app.report.owner_enrich import OwnerExtras
from app.report.types import MODULE_FIELD, ReportDocument

# Ті самі чотири смуги, що всюди, але у вигляді заливки, а не тексту.
BAND_FILL: dict[str, str] = {
    "critical": "C02828",
    # Своя барва для «важливо»: раніше high ділив її з critical, і
    # документ виглядав однаково тривожним завжди.
    "high": "DC5A1E",
    "poor": "D97706",
    "medium": "B48A00",
    "good": "15803D",
    "unknown": "9CA3AF",
}
# Порожня частина смужки — теплим нейтральним, у тон бренду, а не
# холодним сірим системного вигляду.
EMPTY_FILL = "EDE6DC"

# Скільки поділок у смужці. Десять читається як відсотки без пояснень.
SEGMENTS = 10
TOP_PROBLEMS = 6

# Серйозність — смугою кольору й одним словом, а не нашою шкалою severity:
# власнику потрібен порядок терміновості, а не назва рівня.
# Серйозність знахідки → підпис терміновості для власника.
#
# `high` мав тут той самий рядок, що й `critical`, тобто «ТЕРМІНОВО». А
# HIGH-знахідки має майже кожен сайт: `seo.h1` спрацьовує на 21 сайті з
# 29, `tech.analytics` на 19, `a11y.blocking` на 16. Виходило, що звіт
# кричить «терміново» завжди — і слово переставало щось означати. На
# ka-dent.com.ua п'ять таких рядків стояли при нулі критичних знахідок.
SEVERITY_BAND: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "poor",
    "low": "medium",
    "info": "unknown",
}


# Причина, з якої бала немає. Їх три, і власнику треба пояснити ту, що
# сталася: «сайт нас не пустив» на сайті з простроченим хостингом — це
# відповідь не на те питання.
WHY_NO_SCORE: dict[str, str] = {
    "crawl.empty": "empty",
    "crawl.failures": "failures",
}


def _why(report: ReportDocument) -> str:
    """Смуга оцінки, а для «невідомо» — конкретна причина."""
    if report.overall_band != "unknown":
        return report.overall_band
    for missing in report.missing_data:
        if missing.scope in WHY_NO_SCORE:
            return WHY_NO_SCORE[missing.scope]
    return "unknown"


def render_owner_docx(
    report: ReportDocument,
    locale: Locale | None = None,
    extras: OwnerExtras | None = None,
) -> bytes:
    """Мова за замовчуванням — мова самого документа. Див. `docx.render_docx`."""
    locale = locale or locale_of(report)
    document = Document()
    style_document(document)
    _cover(document, report, locale)
    add_footer(document, report)
    _opening(document, extras, locale)
    _what_it_means(document, report, locale)
    _ai_view(document, extras, locale)
    _areas(document, report, locale)
    _problems(document, report, locale, extras)
    _before_after(document, report, locale)
    _closing(document, report, locale)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def filename_for(report: ReportDocument, locale: Locale, extras: OwnerExtras | None = None) -> str:
    host = str(report.target.get("origin", "")).replace("https://", "").replace("/", "")
    # Розширений документ називається інакше: два файли про той самий
    # сайт із різним текстом не мають перезаписувати один одного.
    kind = "general-plus" if extras is not None and extras.analysed else "general"
    return f"audit-{host or 'site'}-{kind}-{locale.value}.docx"


# ── блоки ──────────────────────────────────────────────────────────────────


def _cover(document: Any, report: ReportDocument, locale: Locale) -> None:
    if LOGO.exists():
        logo = document.add_paragraph()
        logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo.add_run().add_picture(str(LOGO), width=Cm(4.2))
        logo.paragraph_format.space_after = Pt(18)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(t("owner_title", locale))
    run.bold = True
    run.font.size = Pt(24)
    run.font.color.rgb = BRAND_BROWN

    kind = document.add_paragraph()
    kind.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kind_run = kind.add_run(t("kind_general", locale))
    kind_run.font.size = Pt(11)
    kind_run.font.color.rgb = MUTED
    kind.paragraph_format.space_after = Pt(8)

    site = document.add_paragraph()
    site.alignment = WD_ALIGN_PARAGRAPH.CENTER
    site_run = site.add_run(str(report.target.get("origin", "")))
    site_run.font.size = Pt(13)
    site_run.font.color.rgb = MUTED
    site.paragraph_format.space_after = Pt(2)

    date = document.add_paragraph()
    date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date.add_run(f"{report.generated_at:%Y-%m-%d}")
    date_run.font.size = Pt(9.5)
    date_run.font.color.rgb = MUTED

    document.add_paragraph()
    _big_score(document, report, locale)
    _scale_bar(document, report.overall_score, report.overall_band)


def _big_score(document: Any, report: ReportDocument, locale: Locale) -> None:
    line = document.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    score = report.overall_score
    run = line.add_run("—" if score is None else str(score))
    run.bold = True
    # Прочерк на 72 пункти виглядає як сірий брусок; невиміряне — менше.
    run.font.size = Pt(72) if score is not None else Pt(40)
    run.font.color.rgb = RGBColor.from_string(BAND_FILL.get(report.overall_band, EMPTY_FILL))

    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_run = caption.add_run(
        f"{t('owner_score_caption', locale)} · {t(f'band_{report.overall_band}', locale)}"
    )
    caption_run.font.size = Pt(11)
    caption_run.font.color.rgb = MUTED


def _what_it_means(document: Any, report: ReportDocument, locale: Locale) -> None:
    _heading(document, t("owner_meaning_title", locale))
    body = document.add_paragraph()
    body.add_run(t(f"owner_meaning_{_why(report)}", locale)).font.size = Pt(12)


def _areas(document: Any, report: ReportDocument, locale: Locale) -> None:
    """П'ять напрямів смужками. Назви — те, що впізнає власник, а не модулі."""
    _heading(document, t("owner_areas_title", locale))
    for module, field in MODULE_FIELD.items():
        score = report.module_scores.get(field)
        label = t(f"owner_area_{module.value}", locale)
        _labelled_bar(document, label, score, _band_of(score))
    note = document.add_paragraph()
    note_run = note.add_run(t("owner_areas_note", locale))
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = MUTED


def _opening(document: Any, extras: OwnerExtras | None, locale: Locale) -> None:
    """Особисте звернення. Його пише модель, і без неї блоку просто немає —
    порожній заголовок гірший за відсутній розділ."""
    if extras is None or not extras.opening:
        return
    para = document.add_paragraph()
    para.paragraph_format.space_before = Pt(12)
    run = para.add_run(extras.opening)
    run.font.size = Pt(12)
    run.italic = True


def _ai_view(document: Any, extras: OwnerExtras | None, locale: Locale) -> None:
    """Як штучний інтелект описує цей бізнес сьогодні.

    Найпереконливіший блок документа: власник бачить не нашу оцінку, а
    те, що про нього скаже помічник, до якого прийде його покупець. Якщо
    опис бідний — це і є доказ проблеми, сильніший за будь-яку смужку.
    """
    if extras is None or not extras.ai_view:
        return
    _heading(document, t("owner_ai_view_title", locale))
    quote = document.add_paragraph()
    quote.paragraph_format.left_indent = Pt(18)
    run = quote.add_run(f"«{extras.ai_view}»")
    run.font.size = Pt(12)
    run.italic = True

    note = document.add_paragraph()
    note.paragraph_format.left_indent = Pt(18)
    note_run = note.add_run(t("owner_ai_view_note", locale))
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = MUTED


def _enrichment_missing(document: Any, extras: OwnerExtras | None, locale: Locale) -> None:
    """Розширення просили, але його немає — і документ каже чому.

    Мовчазний відкат до базового режиму виглядав би так, ніби розширений
    звіт саме такий і має бути.
    """
    if extras is None or extras.analysed or not extras.requested:
        return
    para = document.add_paragraph()
    run = para.add_run(t("owner_enrich_failed", locale).format(reason=extras.error or "—"))
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED


def _problems(
    document: Any,
    report: ReportDocument,
    locale: Locale,
    extras: OwnerExtras | None = None,
) -> None:
    """Що знайдено — мовою наслідку, без жодної поради, як це виправити.

    Порада «що зробити» — це і є те, що продається. У звіті вона віддає
    товар безкоштовно, а власнику й не потрібна: він не робитиме цього
    сам. Йому треба бачити проблему й розуміти її ціну.

    Текст береться з consequence — єдиного поля каталогу, яке за
    побудовою не містить жаргону, і на це є окремий тест.
    """
    problems = [r for r in report.recommendations if r.consequence][:TOP_PROBLEMS]
    if not problems:
        return
    _heading(document, t("owner_problems_title", locale))

    table = document.add_table(rows=1, cols=2)
    header = table.rows[0].cells
    header[0].text = t("owner_problem_gravity", locale)
    header[1].text = t("owner_problem_what", locale)

    for rec in problems:
        row = table.add_row().cells
        band = SEVERITY_BAND.get(rec.severity.value, "unknown")
        _shade(row[0], BAND_FILL[band])
        row[0].text = ""
        run = row[0].paragraphs[0].add_run(t(f"owner_gravity_{band}", locale))
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        row[1].text = rec.consequence
        # Переказ про цей бізнес — додатком до наслідку з каталогу, а не
        # замість нього: доведений текст лишається в документі завжди.
        personal = extras.note_for(rec.msg) if extras is not None else ""
        if personal:
            extra = row[1].add_paragraph()
            extra_run = extra.add_run(personal)
            extra_run.font.size = Pt(10)
            extra_run.italic = True

    style_table(table)
    # Вузька смуга терміновості, широкий наслідок: навпаки автопідбір
    # Word віддавав кольоровим коміркам половину сторінки, і таблиця
    # ставала світлофором замість переліку проблем.
    set_column_widths(table, (3.8, 12.7))
    # Наслідок — основний текст блоку, а не службове значення: після
    # спільного стилю таблиць повертаємо йому читабельний кегль.
    for row_cells in table.rows[1:]:
        for paragraph in row_cells.cells[1].paragraphs:
            for run in paragraph.runs:
                if run.font.size == Pt(9.5):
                    run.font.size = Pt(10.5)

    _enrichment_missing(document, extras, locale)

    note = document.add_paragraph()
    note_run = note.add_run(
        t("owner_problems_note", locale).format(total=report.summary.get("issues_total", 0))
    )
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = MUTED


def _before_after(document: Any, report: ReportDocument, locale: Locale) -> None:
    """Зараз і після — двома смужками поруч.

    potential_score рахується перерахунком скора без цих проблем, а не
    сумою окремих приростів: сумувати їх не можна, і завищена обіцянка
    зруйнувала б довіру до всього документа при повторному аудиті.
    """
    current = report.overall_score
    potential = report.potential_score
    if current is None or potential is None or potential <= current:
        return

    _heading(document, t("owner_gain_title", locale))
    _labelled_bar(document, t("owner_gain_now", locale), current, _band_of(current))
    _labelled_bar(document, t("owner_gain_after", locale), potential, _band_of(potential))

    note = document.add_paragraph()
    note_run = note.add_run(t("owner_gain_note", locale).format(points=potential - current))
    note_run.font.size = Pt(10)
    note_run.font.color.rgb = MUTED


def _closing(document: Any, report: ReportDocument, locale: Locale) -> None:
    _heading(document, t("owner_next_title", locale))
    para = document.add_paragraph()
    para.add_run(t("owner_next_body", locale)).font.size = Pt(12)


# ── графіка ────────────────────────────────────────────────────────────────


def _labelled_bar(document: Any, label: str, score: int | None, band_name: str) -> None:
    caption = document.add_paragraph()
    caption.paragraph_format.space_after = Pt(2)
    name = caption.add_run(f"{label}   ")
    name.bold = True
    name.font.size = Pt(11)
    value = caption.add_run("—" if score is None else f"{score}/100")
    value.font.size = Pt(11)
    value.font.color.rgb = RGBColor.from_string(BAND_FILL.get(band_name, EMPTY_FILL))
    _scale_bar(document, score, band_name)


def _scale_bar(document: Any, score: int | None, band_name: str) -> None:
    """Смужка з десяти комірок: заповнені — заливкою смуги, решта — сірим."""
    filled = 0 if score is None else round(score / 100 * SEGMENTS)
    table = document.add_table(rows=1, cols=SEGMENTS)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    fill = BAND_FILL.get(band_name, EMPTY_FILL)
    for index, cell in enumerate(table.rows[0].cells):
        _shade(cell, fill if index < filled else EMPTY_FILL)
        cell.text = ""
        cell.paragraphs[0].paragraph_format.space_after = Pt(0)
        cell.paragraphs[0].add_run(" ").font.size = Pt(8)
    document.add_paragraph().paragraph_format.space_after = Pt(4)


def _shade(cell: Any, hex_color: str) -> None:
    """Заливка комірки. python-docx не має API для цього — тільки XML."""
    element = OxmlElement("w:shd")
    element.set(qn("w:val"), "clear")
    element.set(qn("w:color"), "auto")
    element.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(element)


def _heading(document: Any, text: str) -> None:
    para = document.add_paragraph()
    para.paragraph_format.space_before = Pt(18)
    para.paragraph_format.keep_with_next = True
    run = para.add_run(text)
    run.bold = True
    run.font.size = Pt(15)
    run.font.color.rgb = BRAND_BROWN


def _band_of(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score < 40:
        return "critical"
    if score < 60:
        return "poor"
    if score < 80:
        return "medium"
    return "good"
