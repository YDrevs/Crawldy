"""Про що ми маємо право сказати «це тема», і що таке два сигнали.

Обидва дефекти знайдені переглядом знахідок night3 очима, а не тестами:
числа виглядали нормально, брехала інтерпретація.
"""

from __future__ import annotations

import pytest

from app.audit.demo_content import DemoSignals
from app.audit.page_kinds import is_safe_topic_section


@pytest.mark.parametrize("segment", [
    "2024", "2022", "2018", "2000", "05", "31",   # дати з /2024/05/31/slug/
    "12345", "7",                                  # числові ідентифікатори
    # Односимвольні ЛАТИНСЬКІ: усі дев'ять, що трапились у night3,
    # виявились маршрутом — /p/2010-2011.html, /c/gin-company/…,
    # /v/552089, /i/das-sind-wir.
    "p", "c", "v", "i", "b", "l", "w", "a", "d",
    # І числа, які цілком могли б бути назвою: /911/ — серія автомобілів,
    # /360/ — лінійка, /24/ — цілодобова послуга. Саме тому твердження
    # тут про нашу непевність, а не про будову чужого сайту.
    "911", "360", "24",
    "", "   ",
])
def test_ambiguous_segments_are_not_announced_as_topics(segment: str) -> None:
    """1. Мовчимо там, де не можемо назвати тему.

    `985theriver.com` мав «тему 2024» зі сторінок `/2024/05/31/slug/`.
    Вимірювання правдиве — ті сторінки справді не посилаються одна на
    одну, — але сказати клієнтові «сторінки вашої теми „2024“ не
    повʼязані» означає назвати темою рік.

    Твердження тут МІНІМАЛЬНЕ: не «це маршрут CMS», а «доказів назвати
    це темою в нас немає». `/911/` цілком може бути серією автомобілів,
    `/360/` — лінійкою продуктів; з адреси їх від дати не відрізнити,
    тому ми не стверджуємо ні того, ні іншого.
    """
    assert not is_safe_topic_section(segment)


@pytest.mark.parametrize("segment", [
    "blog", "products", "services", "news", "press-releases",
    "featured-cases", "design-portfolio", "actualites", "publications",
    "jobs", "event", "docs", "product-page", "tilbud_og_pakker",
    # Один ієрогліф — це повне слово, тобто можлива назва розділу.
    # Доказів про такі сегменти немає жодного: у night3 їх нуль. Правило,
    # виведене з латиниці, тут мовчки викинуло б справжню тему.
    "本", "新", "家", "書", "ㅇ", "я",
])
def test_named_sections_stay_topics(segment: str) -> None:
    """2. Розділ із назвою лишається темою.

    Це саме те, заради чого чек існує: `featured-cases` на tonkon.com і
    `products` на foodaramatexas.com — справжні групи.

    Не-ASCII односимвольні сюди входять навмисно: правило звужене до
    форм, які має чим підперти. Про ієрогліфи доказів немає, тож вони
    лишаються темою — хибний пропуск дешевший за тихо викинуту тему.
    """
    assert is_safe_topic_section(segment)


def test_two_names_for_one_artefact_are_one_signal() -> None:
    """3. Незалежність — це різні докази, а не різні назви категорій.

    На sparkracingtechnology.com одна адреса — власний запис блогу, у
    слузі якого трапилось слово конструктора, — лежала і в
    `vendor_mentions`, і в `template_pages`. Умова «два незалежні
    сигнали» формально виконувалась, а доказ був один.
    """
    same = "https://x.com/2022/09/19/elementor-10344/"
    assert DemoSignals(vendor_mentions=[same], template_pages=[same]).kinds == 1


def test_genuinely_independent_signals_still_count() -> None:
    """4. Справжні збіги мають лишитись знахідкою."""
    assert DemoSignals(
        vendor_mentions=["info@themeforest-demo.com"],
        template_pages=["https://x.com/elementor-demo"],
    ).kinds == 2
    assert DemoSignals(
        placeholder_contacts=["+1 555 555 5555"],
        vendor_mentions=["info@theme.com"],
        template_pages=["https://x.com/demo"],
    ).kinds == 3


def test_a_shared_artefact_does_not_erase_an_independent_one() -> None:
    """5. Спільний доказ не з'їдає власний.

    Якщо категорія має і спільну адресу, і власну, вона лишається
    самостійним сигналом: інакше виправлення однієї помилки створило б
    протилежну — приховування справжніх знахідок.
    """
    same = "https://x.com/demo"
    assert DemoSignals(
        vendor_mentions=[same, "info@theme.com"],
        template_pages=[same],
    ).kinds == 2


def test_evidence_states_how_many_signals_were_independent() -> None:
    """6. Читач доказу має бачити не лише що знайдено, а й скільки з
    цього незалежного."""
    same = "https://x.com/demo"
    payload = DemoSignals(vendor_mentions=[same], template_pages=[same]).to_json()
    assert payload["independent_signals"] == 1
