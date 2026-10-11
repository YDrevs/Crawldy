"""Чернетка llms.txt: що в ній має бути й чого бути не може."""

from __future__ import annotations

from app.audit.llm.base import SiteBrief
from app.audit.types import PageSignals, SiteContext
from app.report.llms_txt import build_llms_txt


def page(url: str, title: str, description: str = "", words: int = 400) -> PageSignals:
    signals = PageSignals(url=url, status_code=200, title=title, html_bytes=20_000)
    signals.meta_description = description
    signals.word_count = words
    signals.text = "слово " * words
    return signals


def ctx(*pages: PageSignals, brief: SiteBrief | None = None) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.pages = list(pages)
    site.brief = brief
    return site


def test_file_is_built_without_a_model_at_all():
    """Структура береться з краулу. Без ключа файл сухіший, але робочий —
    саме тому джерела розділені."""
    site = ctx(
        page("https://example.com/", "Acme — доставка квітів", "Квіти за годину"),
        page("https://example.com/about/", "Про нас"),
    )

    text = build_llms_txt(site)

    assert text.startswith("# Acme"), "хвіст після тире — слоган, а не назва"
    assert "> Квіти за годину" in text
    assert "[Про нас](https://example.com/about/)" in text


def test_model_summary_replaces_the_meta_description():
    site = ctx(
        page("https://example.com/", "Acme", "старий опис із мета-тега"),
        brief=SiteBrief(analysed=True, name="Acme Flowers", tagline="доставка квітів за годину"),
    )

    text = build_llms_txt(site)

    assert "# Acme Flowers" in text
    assert "> доставка квітів за годину" in text
    # Мета-опис лишається як пояснення до посилання — там він доречний.
    # Перевіряємо саме підзаголовок сайту: він має бути один.
    quoted = [line for line in text.splitlines() if line.startswith("> ")]
    assert quoted == ["> доставка квітів за годину"]


def test_unanalysed_brief_does_not_leak_empty_fields():
    """Аналізу не було — беремо те, що є в HTML, а не порожні рядки моделі."""
    site = ctx(
        page("https://example.com/", "Acme", "опис із мета-тега"),
        brief=SiteBrief(analysed=False, error="не заданий ключ"),
    )

    text = build_llms_txt(site)

    assert "# Acme" in text
    assert "> опис із мета-тега" in text


def test_pages_are_grouped_into_sections():
    site = ctx(
        page("https://example.com/", "Головна"),
        page("https://example.com/services/implants", "Імпланти"),
        page("https://example.com/blog/post", "Стаття"),
    )

    text = build_llms_txt(site)

    assert "## Services" in text
    assert "## Blog" in text
    assert text.index("## Services") < text.index("## Blog"), "спершу те, що продає"


def test_link_budget_is_enforced():
    """llms.txt — карта для моделі, а не другий sitemap: надто довгий
    список змушує її читати все підряд."""
    from app.report.llms_txt import MAX_LINKS

    many = [page(f"https://example.com/p{n}", f"Сторінка {n}") for n in range(200)]

    text = build_llms_txt(ctx(*many))

    assert text.count("\n- [") <= MAX_LINKS


def test_pages_we_never_saw_are_not_listed():
    """Сторінка-оболонка не потрапляє в карту: ми не знаємо, що на ній."""
    shell = PageSignals(url="https://example.com/app", status_code=200, title="App")
    shell.html_bytes = 300_000
    shell.word_count = 2
    shell.text = "Loading"

    text = build_llms_txt(ctx(page("https://example.com/", "Головна"), shell))

    assert "https://example.com/app" not in text


def test_site_without_titles_produces_nothing():
    """Порожній файл краще за файл із порожніми посиланнями."""
    blank = PageSignals(url="https://example.com/", status_code=200)
    blank.word_count = 400
    blank.text = "слово " * 400

    assert build_llms_txt(ctx(blank)) == ""


def test_root_level_pages_are_not_called_other():
    """Сайт, де всі сторінки лежать у корені, — не набір «інших» сторінок.
    Це його головні сторінки, і заголовок має це відображати."""
    site = ctx(
        page("https://example.com/", "Головна"),
        page("https://example.com/ip-licensing", "Ліцензування"),
        page("https://example.com/manufacturing", "Виробництво"),
    )

    text = build_llms_txt(site)

    assert "## Pages" in text
    assert "## Other pages" not in text


def test_other_stays_other_when_real_sections_exist():
    site = ctx(
        page("https://example.com/", "Головна"),
        page("https://example.com/blog/post", "Стаття"),
        page("https://example.com/random-page", "Випадкова"),
    )

    text = build_llms_txt(site)

    assert "## Blog" in text
    assert "## Other pages" in text


def test_demo_pages_never_reach_the_file_we_hand_to_the_client():
    """На smartkp.com.ua генератор вносив у llms.txt Mark Liuw і Angela
    Kwang — вигаданих людей із шаблону теми. Ми не просто не помічали
    чужий шаблон, а складали з нього карту сайту для моделей."""
    from app.audit.site_facts import SiteKnowledge

    site = ctx(
        page("https://s.com/", "Смарт — автоматизація бізнесу", "Працюємо в місті Львів"),
        page("https://s.com/team/mark-liuw/", "Mark Liuw - Smart"),
        page("https://s.com/footer/footer-home-1/", "Footer Home 1"),
        page("https://s.com/poslugy/", "Послуги"),
    )
    site.pages[0].text = "Ми автоматизуємо бізнес у місті Львів. " * 20
    site.known = SiteKnowledge(emails=["seofy@mail.com"])

    text = build_llms_txt(site)

    assert "Mark Liuw" not in text
    assert "footer" not in text
    assert "Послуги" in text


def test_system_and_legal_pages_are_left_out():
    """Модель не має йти на сторінку входу чи на договір: вони нічого не
    стверджують про компанію."""
    site = ctx(
        page("https://s.com/", "Магазин"),
        page("https://s.com/wp-login.php", "Увійти"),
        page("https://s.com/privacy/", "Політика конфіденційності"),
        page("https://s.com/catalog/", "Каталог"),
    )

    text = build_llms_txt(site)

    assert "wp-login" not in text
    assert "privacy" not in text
    assert "Каталог" in text
