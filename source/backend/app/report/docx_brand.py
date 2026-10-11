"""Бренд Crawldy у Word-документі: кольори, типографіка, обкладинка.

Звіт — це артефакт продукту, а не системний експорт: клієнт надсилає
його керівнику чи власному клієнту, і документ мусить належати тому
самому продукту, що й crawldy.ai. Тому мова бренду тут одна з сайтом:
коричневий #522A05, бірюзовий акцент #00B2BA, основний текст #2B211E —
і стриманість: колір підтримує зміст, а не замінює підписи.

## Чому Calibri

Документ мусить однаково добре виглядати шістьма мовами, включно з
кирилицею, у Word, у в'юерах і на друці — без вбудовування шрифтів.
Calibri є в кожному Word, повністю покриває кирилицю й діакритику
DE/ES/FR і не зчитується як «системний експорт», на відміну від Times.
Моноширинним значенням служить Consolas із тих самих міркувань.

## Логотип

`assets/crawldy-lockup.png` — копія офіційного
`frontend/public/brand/crawldy-lockup.png`, зменшена до 520 px по
ширині (вбудовується в кожен docx; 366 КБ оригіналу там зайві), без
змін кольору чи пропорцій. Бекенд не має доступу до фронтенду під час
виконання, тому копія; джерело правди — файл у frontend/public/brand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml.parser import OxmlElement
from docx.shared import Cm, Pt, RGBColor

from app.audit.i18n import Locale
from app.report.i18n import t
from app.report.types import ReportDocument

# ── палітра бренду ─────────────────────────────────────────────────────────

BRAND_BROWN = RGBColor(0x52, 0x2A, 0x05)
TURQUOISE = RGBColor(0x00, 0xB2, 0xBA)
TEXT = RGBColor(0x2B, 0x21, 0x1E)
MUTED = RGBColor(0x8A, 0x7B, 0x70)
# Тепла нейтральна заливка для шапок таблиць: папір, а не дашборд.
FILL_WARM = "F4EFE8"
RULE_WARM = "D9CFC4"

BODY_FONT = "Calibri"
MONO_FONT = "Consolas"

LOGO = Path(__file__).parent / "assets" / "crawldy-lockup.png"

# Смуги оцінки — наявна палітра серйозності продукту, без змін.
BAND_COLOR: dict[str, RGBColor] = {
    "critical": RGBColor(0xC0, 0x28, 0x28),
    "high": RGBColor(0xDC, 0x5A, 0x1E),
    "poor": RGBColor(0xD9, 0x77, 0x06),
    "medium": RGBColor(0xB4, 0x8A, 0x00),
    "good": RGBColor(0x15, 0x80, 0x3D),
    "unknown": RGBColor(0x6B, 0x72, 0x80),
}

SEVERITY_COLOR: dict[str, RGBColor] = {
    "critical": BAND_COLOR["critical"],
    "high": BAND_COLOR["high"],
    "medium": BAND_COLOR["poor"],
    "low": BAND_COLOR["medium"],
    "info": BAND_COLOR["unknown"],
}


def style_document(document: Any) -> None:
    """Базова типографіка: одна система на всі шість мов.

    Ієрархію тримають шрифт, колір і повітря, а не рамки. Заголовки —
    напівжирний Calibri у коричневому бренду; keep_with_next не дає
    розриву сторінки залишити заголовок сиротою над порожнечею.
    """
    styles = document.styles

    normal = styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = TEXT
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for name, size, color, before in (
        ("Heading 1", 20, BRAND_BROWN, 18),
        ("Heading 2", 14, BRAND_BROWN, 16),
        ("Heading 3", 12, BRAND_BROWN, 12),
        ("Heading 4", 10.5, TEXT, 10),
    ):
        style = styles[name]
        style.font.name = BODY_FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.keep_with_next = True
        # Word успадковує сині кольори теми, якщо їх не зняти явно.
        style.font.underline = False

    title = styles["Title"]
    title.font.name = BODY_FONT
    title.font.size = Pt(26)
    title.font.bold = True
    title.font.color.rgb = BRAND_BROWN


def add_cover(
    document: Any,
    report: ReportDocument,
    locale: Locale,
    kind: str | None = None,
) -> None:
    """Перша сторінка: логотип, назва, домен, дата, бал.

    Достатньо гарна, щоб піти керівнику чи клієнту без супровідного
    листа — і чесна: коли бала немає, тут прочерк і «не вимірювалось»,
    а не вигаданий нуль.
    """
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(36)

    if LOGO.exists():
        logo_paragraph = document.add_paragraph()
        logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo_paragraph.add_run().add_picture(str(LOGO), width=Cm(5.2))
        logo_paragraph.paragraph_format.space_after = Pt(30)

    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = heading.add_run(t("doc_title", locale))
    run.font.name = BODY_FONT
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = BRAND_BROWN

    # Вид документа. Файлів про один сайт тепер чотири, і назва в теці
    # завантажень — не єдине місце, де їх треба розрізняти: роздрукований
    # аркуш назви файлу не має взагалі.
    if kind is not None:
        kind_line = document.add_paragraph()
        kind_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        kind_run = kind_line.add_run(t(kind, locale))
        kind_run.font.size = Pt(11)
        kind_run.font.color.rgb = MUTED
        kind_line.paragraph_format.space_after = Pt(10)

    host = document.add_paragraph()
    host.alignment = WD_ALIGN_PARAGRAPH.CENTER
    host_run = host.add_run(str(report.target.get("url", "")))
    host_run.font.size = Pt(14)
    host_run.font.color.rgb = TEXT
    host.paragraph_format.space_after = Pt(2)

    meta = document.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_run = meta.add_run(
        f"{t('generated', locale)}: {report.generated_at:%Y-%m-%d}  ·  "
        f"{t('pages_crawled', locale)}: {report.target.get('pages_crawled', 0)}"
    )
    meta_run.font.size = Pt(9.5)
    meta_run.font.color.rgb = MUTED
    meta.paragraph_format.space_after = Pt(30)

    add_rule(document)

    score = document.add_paragraph()
    score.alignment = WD_ALIGN_PARAGRAPH.CENTER
    score.paragraph_format.space_before = Pt(24)
    value = "—" if report.overall_score is None else str(report.overall_score)
    score_run = score.add_run(value)
    score_run.font.name = BODY_FONT
    score_run.font.bold = True
    # Прочерк у 64 пункти читається як сірий брусок, а не як «немає
    # числа», тож для невиміряного стану кегль менший.
    score_run.font.size = Pt(64) if report.overall_score is not None else Pt(36)
    score_run.font.color.rgb = BAND_COLOR.get(report.overall_band, BAND_COLOR["unknown"])
    score.paragraph_format.space_after = Pt(0)

    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if report.overall_score is None:
        caption_text = f"{t('overall', locale)}: {t('not_measured', locale)}"
    else:
        caption_text = (
            f"{t('overall', locale)} {t('of_100', locale)} — "
            f"{t(f'band_{report.overall_band}', locale)}"
        )
    caption_run = caption.add_run(caption_text)
    caption_run.font.size = Pt(11)
    caption_run.font.color.rgb = MUTED

    # Обмежене покриття або відсутні дані видно вже з обкладинки —
    # тими самими рядками, що й у самому звіті.
    if report.missing_data:
        note = document.add_paragraph()
        note.alignment = WD_ALIGN_PARAGRAPH.CENTER
        note.paragraph_format.space_before = Pt(12)
        note_run = note.add_run(t("part1_missing_intro", locale).rstrip(":"))
        note_run.font.size = Pt(9.5)
        note_run.italic = True
        note_run.font.color.rgb = MUTED

    document.add_page_break()


def add_footer(document: Any, report: ReportDocument) -> None:
    """Колонтитул звіту аудиту: домен береться з цілі документа."""
    host = str(report.target.get("origin", "")).replace("https://", "").replace("http://", "")
    add_footer_for(document, host)


def add_footer_for(document: Any, host: str) -> None:
    """Колонтитул: бренд і домен ліворуч, номер сторінки праворуч.

    Стримано й без внутрішніх ідентифікаторів: жодних токенів, id
    аудиту чи посилань на провайдерів. Обкладинка — без колонтитула.

    Домен приходить рядком, а не `ReportDocument`: той самий колонтитул
    стоїть у документах присутності, а вони будуються не зі звіту
    аудиту й такого обʼєкта не мають.
    """
    section = document.sections[0]
    section.different_first_page_header_footer = True

    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.text = ""

    left = paragraph.add_run(f"Crawldy  ·  {host}" if host else "Crawldy")
    left.font.size = Pt(8.5)
    left.font.color.rgb = MUTED

    # Табуляція до правого краю; номер сторінки — полем PAGE, щоб Word
    # рахував його сам.
    paragraph.add_run("\t\t")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run_element = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "17")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "8A7B70")
    props.append(size)
    props.append(color)
    run_element.append(props)
    fld.append(run_element)
    paragraph._p.append(fld)


def add_rule(document: Any) -> None:
    """Тонка бірюзова лінія — єдина прикраса, яку документ собі дозволяє."""
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(2)
    paragraph.paragraph_format.space_after = Pt(2)
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:color"), "00B2BA")
    border.append(bottom)
    paragraph._p.get_or_add_pPr().append(border)


def style_table(table: Any) -> None:
    """Таблиця бренду: тепла шапка, тонкі теплі лінії, без синього Word.

    Вбудовані стилі Word («Light Grid Accent 1») — це та сама «синя
    корпоративна» мова, від якої документ тікає. Шапка повторюється на
    кожній сторінці, довгі значення переносяться в межах колонки.
    """
    table.style = "Table Grid"
    _set_table_borders(table)

    header = table.rows[0]
    _repeat_header(header)
    for cell in header.cells:
        _shade(cell, FILL_WARM)
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = BRAND_BROWN

    for row in table.rows[1:]:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9.5)


def set_column_widths(table: Any, widths_cm: tuple[float, ...]) -> None:
    """Явні ширини колонок: автопідбір Word віддає половину таблиці
    короткій колонці з числом, а довгий текст тисне в вузьку."""
    table.autofit = False
    for row in table.rows:
        for cell, width in zip(row.cells, widths_cm, strict=True):
            cell.width = Cm(width)


def _set_table_borders(table: Any) -> None:
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), RULE_WARM)
        borders.append(element)
    table._tbl.tblPr.append(borders)


def _repeat_header(row: Any) -> None:
    properties = row._tr.get_or_add_trPr()
    element = OxmlElement("w:tblHeader")
    element.set(qn("w:val"), "true")
    properties.append(element)


def _shade(cell: Any, fill: str) -> None:
    element = OxmlElement("w:shd")
    element.set(qn("w:val"), "clear")
    element.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(element)


def severity_run(paragraph: Any, label: str, severity: str) -> None:
    """Серйозність — словом у кольорі рівня. Слово несе зміст і без кольору."""
    run = paragraph.add_run(label)
    run.font.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["info"])


def mono_run(paragraph: Any, text: str, size: float = 8.5) -> Any:
    """Технічне значення чи адреса — моноширинним, дрібнішим, приглушеним."""
    run = paragraph.add_run(breakable(text))
    run.font.name = MONO_FONT
    run.font.size = Pt(size)
    run.font.color.rgb = TEXT
    return run


def breakable(text: str) -> str:
    """Довгі адреси отримують точки переносу після роздільників.

    Word не ламає довге «слово» посередині, і URL без пробілів вилазив
    би за поле. Нульової ширини пробіл після / ? & = дає місце для
    переносу, не змінюючи видимого тексту й того, що скопіюється.
    """
    if len(text) < 60:
        return text
    out = []
    for ch in text:
        out.append(ch)
        if ch in "/?&=_-":
            out.append("​")
    return "".join(out)
