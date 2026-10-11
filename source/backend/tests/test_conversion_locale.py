"""`cro.no_action` мусить судити сторінку, а не мову її підписів.

## Дефект, через який ці тести існують

E2-ENGINE-FINDING-02. Шість мовних копій однієї сторінки цін Crawldy —
однакові посилання, однаковий тип сторінки, однакові форми, контакти й
кнопки — отримували різний вирок:

    Buy the pack        (en)  → дія є
    Купить пакет        (ru)  → дія є
    Придбати пакет      (uk)  → дії немає
    Paket kaufen        (de)  → дії немає
    Comprar el paquete  (es)  → дії немає
    Acheter le pack     (fr)  → дії немає

Причина не в перекладі й не в адресі: `path_words` не збігався з
`ACTION_PATHS` ЖОДНОЮ мовою (посилання ведуть на `/login` і `/result`), тож
вирок вирішувала друга гілка — підпис проти переліку, який жив кортежем у
самому чеку й знав англійську та українсько-російські корені. Другий
словник поруч із `vocab` і був тим місцем, де мови розходились.

Підписи взяті з замороженого доказу E2 — це та сама пара «адреса + підпис»,
яку виміряно на прогоні, а не вигадана ілюстрація.
"""

from __future__ import annotations

import json

import pytest

from app.audit import vocab
from app.audit.checks.conversion import NoWayToActCheck
from app.audit.page_kinds import SELLS_SOMETHING
from app.audit.types import RenderResult
from app.audit.vocab.enums import Concept
from tests.factories import context, page_from_html

#: (locale, шлях сторінки цін, підпис кнопки купівлі) — з доказу E2.
MEASURED = [
    ("en", "/pricing", "Buy the pack", "Sign in", "Check your site"),
    ("uk", "/uk/tsiny", "Придбати пакет", "Увійти", "Перевірити сайт"),
    ("de", "/de/preise", "Paket kaufen", "Anmelden", "Website prüfen"),
    ("es", "/es/precios", "Comprar el paquete", "Entrar", "Comprobar el sitio"),
    ("fr", "/fr/tarifs", "Acheter le pack", "Se connecter", "Vérifier le site"),
    ("ru", "/ru/tseny", "Купить пакет", "Войти", "Проверить сайт"),
]

BODY_WORDS = " ".join(f"слово{i}" for i in range(120))  # понад MIN_WORDS_TO_JUDGE


def _pricing_html(buy: str, login: str, check: str, *, with_buy: bool = True) -> str:
    """Сторінка цін: посилання в `<main>`, навігація окремо в `<nav>`."""
    buy_link = (
        f'<a href="/login?next=%2Fapp%2Fplan">{buy}</a>' if with_buy else ""
    )
    return (
        "<html><body>"
        "<nav><a href='/'>Home</a><a href='/contact'>Contact</a></nav>"
        f"<main><h1>Plans</h1><p>{BODY_WORDS}</p>"
        f'<a href="/login">{login}</a>'
        f'<a href="/result">{check}</a>'
        f"{buy_link}"
        "</main>"
        "<footer><a href='/legal'>Legal</a></footer>"
        "</body></html>"
    )


def _verdict(path: str, html: str) -> bool:
    """Чи видає `cro.no_action` знахідку. Через справжній чек, не переспів."""
    url = f"https://example.com{path}"
    page = page_from_html(html, url=url)
    ctx = context(page)
    ctx.renders = {url: RenderResult(url=url, rendered=True,
                                     signals=page_from_html(html, url=url))}
    return bool(list(NoWayToActCheck().run(ctx)))


@pytest.mark.parametrize("loc,path,buy,login,check", MEASURED)
def test_the_frozen_e2_pages_agree_across_every_locale(loc, path, buy, login, check):
    """1 і 2. Той самий вирок шістьма мовами на виміряних підписах."""
    assert _verdict(path, _pricing_html(buy, login, check)) is False, (
        f"{loc}: сторінка з кнопкою «{buy}» має дію, як і англійська"
    )


def test_every_locale_gives_one_and_the_same_answer():
    """2. Інваріант як одне твердження, а не шість окремих."""
    answers = {
        loc: _verdict(path, _pricing_html(buy, login, check))
        for loc, path, buy, login, check in MEASURED
    }
    assert len(set(answers.values())) == 1, f"вирок розійшовся по мовах: {answers}"


def _full_outcome(path: str, html: str):
    """Повний шлях: знахідки, докази й бал, а не лише «спрацювало / ні»."""
    from app.audit.orchestrator import rescore

    url = f"https://example.com{path}"
    page = page_from_html(html, url=url)
    ctx = context(page)
    ctx.renders = {url: RenderResult(url=url, rendered=True,
                                     signals=page_from_html(html, url=url))}
    outcome = rescore(ctx)
    cro = [i for i in (outcome.issues or []) if i.code == "cro.no_action"]
    return {
        "emitted": bool(cro),
        "evidence": cro[0].evidence if cro else None,
        "severity": cro[0].severity.value if cro else None,
        "weight": cro[0].weight if cro else None,
        "tech": (outcome.scores or {}).get("tech"),
    }


def test_locales_agree_on_evidence_and_scoring_not_only_on_presence():
    """Інваріант — увесь наслідок, а не сам факт знахідки.

    Зрівняти лише «спрацювало / ні» було б замало: доказ і бал модуля йдуть
    клієнтові, і розійтися вони можуть і тоді, коли присутність збігається.
    """
    for with_buy in (True, False):
        seen = {
            loc: _full_outcome(path, _pricing_html(buy, login, check, with_buy=with_buy))
            for loc, path, buy, login, check in MEASURED
        }
        assert len({o["emitted"] for o in seen.values()}) == 1, (with_buy, seen)
        assert len({o["severity"] for o in seen.values()}) == 1, (with_buy, seen)
        assert len({o["weight"] for o in seen.values()}) == 1, (with_buy, seen)
        assert len({o["tech"] for o in seen.values()}) == 1, (
            f"бал модуля розійшовся по мовах ({with_buy=}): "
            f"{ {k: v['tech'] for k, v in seen.items()} }"
        )
        assert len({json.dumps(o["evidence"], sort_keys=True, default=str)
                    for o in seen.values()}) == 1, (with_buy, seen)
    #: Обидва боки потрібні: перший доводить згоду там, де дія є, другий — там,
    #: де знахідка справді видається, а отже доказ, серйозність і бал існують і
    #: можуть розійтися. Порівняння лише присутності не побачило б другого.


def test_an_actionless_page_still_gets_the_finding():
    """4. Виправлення не глушить чек: без кнопки купівлі знахідка лишається."""
    for loc, path, buy, login, check in MEASURED:
        assert _verdict(path, _pricing_html(buy, login, check, with_buy=False)) is True, (
            f"{loc}: сторінка без дії мусить дати знахідку"
        )


def test_pages_whose_content_really_differs_may_differ():
    """5. Рівність не нав'язується: різний вміст лишається різним."""
    with_action = _verdict("/pricing", _pricing_html("Buy the pack", "Sign in", "Check"))
    without = _verdict("/de/preise",
                       _pricing_html("Paket kaufen", "Anmelden", "Prüfen", with_buy=False))
    assert with_action is False
    assert without is True


def test_a_route_that_cro_does_not_apply_to_is_untouched():
    """6. Незастосовний маршрут лишається незастосовним."""
    url = "https://example.com/legal/terms"
    page = page_from_html(_pricing_html("Buy", "Sign in", "Check", with_buy=False), url=url)
    ctx = context(page)
    ctx.renders = {url: RenderResult(url=url, rendered=True, signals=page)}
    assert ctx.type_of(page) not in SELLS_SOMETHING
    assert list(NoWayToActCheck().run(ctx)) == []


def test_the_answer_does_not_depend_on_order_or_hash_seed():
    """7. Словник — множина; порядок її обходу залежить від засіву.

    Перелік фіксується `sorted`, тож він однаковий у кожному процесі, а
    вирок не залежить ані від порядку слів, ані від порядку сторінок.
    """
    from app.audit.checks import conversion

    assert conversion.ACTION_ANCHORS == tuple(sorted(conversion.ACTION_ANCHORS))

    forward = [_verdict(p, _pricing_html(b, lg, c)) for _, p, b, lg, c in MEASURED]
    backward = [_verdict(p, _pricing_html(b, lg, c))
                for _, p, b, lg, c in reversed(MEASURED)]
    assert forward == list(reversed(backward))


def test_the_anchor_vocabulary_is_the_shared_one_not_a_second_list():
    """3 і 8. Джерело одне — `vocab`, і воно покриває мови запуску."""
    from app.audit.checks import conversion
    from app.audit.vocab.enums import ContentLanguage

    assert conversion.ACTION_ANCHORS == tuple(
        sorted(vocab.words_for(Concept.CALL_TO_ACTION_TEXT))
    )
    for language in (ContentLanguage.EN, ContentLanguage.UK, ContentLanguage.DE,
                     ContentLanguage.ES, ContentLanguage.FR, ContentLanguage.RU):
        assert vocab.words_for(Concept.CALL_TO_ACTION_TEXT, [language]), (
            f"{language.value}: підписи мови запуску мусять бути в словнику"
        )


def test_version_transition_is_pinned_for_locale_independent_cro():
    """8. Літеральні значення переходу, не звірка величини з нею самою."""
    from app.audit import versions

    assert versions.DETECTOR_RULES == "14"
    assert versions.detector_version() == "3b9a556ab798"

    assert versions.CRAWLER_VERSION == "4"
    assert versions.SCORING_RULES == "5"
    assert versions.scoring_version() == "aa4ecc62a5a3"
