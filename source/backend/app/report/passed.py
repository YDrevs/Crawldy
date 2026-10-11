"""Пройдені перевірки: явний доказ успіху, а не відсутність знахідки.

Порожній результат чека означає «проблеми не знайшли» — і це НЕ те саме,
що «перевірили й переконалися». Чек міг не мати даних, бути незастосовним
або вимкненим разом із модулем. Тому пройдене тут ніколи не виводиться з
тиші: кожен пункт обчислюється з явного позитивного факту в доказах
звіту — тих самих, які збирає `build_evidence` тим самим кодом, що й
детектори.

Стани навмисно шість, а не два. Клієнтові показується лише `PASSED`;
решта існують, щоб межа була видимою в коді й тестах, а не в коментарі:

* `FAILED` — є протилежний факт (пройденим не стане ніколи);
* `NOT_APPLICABLE` — перевірка не стосується цього сайту;
* `UNAVAILABLE` — доказу немає: не зібрали, провайдер мовчав, старий
  аудит без цього блоку. Старий аудит так НЕ ВИГАДУЄ собі пройденого;
* `NO_VERDICT` — доказ є, але канонічний стан застосовності не дозволяє
  назвати це успіхом: судження неповне (`PASS + PARTIAL`) або претензія
  взагалі не отримала вердикту. Це НЕ те саме, що `UNAVAILABLE`: там
  доказу не існує, тут він є й прямо каже, що питання не закрите;
* `SKIPPED` — модуль вимкнено користувачем або покриття притримало
  site-level судження: казати «пройдено» про напрям, якому ми не дали
  бала, означало б хвалити наосліп.

Шосте правило — над усіма пʼятьма і над кожною стратегією агрегації:
пройденим стає лише те, чий канонічний стан рівно `PASS + COMPLETE`
(E-05). Оцінювач і застосовність мусять сказати «так» обидва, і
застосовність уміє лише притримати — створити успіх вона не може.

Набір курований і малий. Сюди входить лише те, що справді перевірено,
детерміністично доведено доказом і корисно клієнтові; жоден пункт не
дублює знімок доступності, і site-level формулювання не видається за
page-scoped спостереження.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit import applicability
from app.audit.applicability import ClaimVerdict, Coverage, eligible_for_passed_checks
from app.audit.enums import Module
from app.audit.standards.analytics_vendors import VENDOR_NAMES, Kind


class PassState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    NO_VERDICT = "no_verdict"
    SKIPPED = "skipped"


@dataclass(slots=True)
class PassedCheck:
    """Одна пройдена перевірка: ключ, модуль, обсяг і факти.

    Факти locale-нейтральні: заголовок складається при рендері з ключа
    `passed.<key>` тією мовою, якою читають звіт, — так само, як усі
    рядки каталогу.
    """

    key: str
    module: Module
    # Про що саме твердження: origin | site | page | sampled. Page-scoped
    # факт ніколи не подається як site-level — обсяг частина контракту.
    scope: str
    facts: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "module": self.module.value,
            "scope": self.scope,
            "facts": self.facts,
        }


# Оцінювач повертає (стан, обсяг, факти). Він читає лише evidence — те,
# що персистується з аудитом, — тому той самий код працює і для свіжого
# аудиту, і для збереженого, а старий аудит без потрібного блока чесно
# віддає UNAVAILABLE.
Evaluator = Callable[[dict[str, Any]], tuple[PassState, str, dict[str, Any]]]


def _https(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    http = evidence.get("http") or {}
    if "is_https" not in http:
        return PassState.UNAVAILABLE, "origin", {}
    if not http.get("is_https"):
        return PassState.FAILED, "origin", {}
    # Старі аудити не зберігали tls_error: схема є, а про сертифікат
    # доказу немає — «пройдено» без нього було б вигадкою.
    if "tls_error" not in http:
        return PassState.UNAVAILABLE, "origin", {}
    if http.get("tls_error"):
        return PassState.FAILED, "origin", {}
    return PassState.PASSED, "origin", {"origin": http.get("origin") or ""}


def _robots(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    robots = evidence.get("robots_txt") or {}
    if "exists" not in robots:
        return PassState.UNAVAILABLE, "site", {}
    if not robots.get("exists"):
        return PassState.FAILED, "site", {}
    return PassState.PASSED, "site", {}


def _sitemap(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    sitemap = evidence.get("sitemap_xml") or {}
    if "exists" not in sitemap:
        return PassState.UNAVAILABLE, "site", {}
    if not sitemap.get("exists") or sitemap.get("parse_error"):
        return PassState.FAILED, "site", {}
    declared = sitemap.get("url_count") or 0
    if declared <= 0:
        return PassState.FAILED, "site", {}
    return PassState.PASSED, "site", {"declared": declared}


def _security_headers(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    fact = evidence.get("security_headers") or {}
    if not fact.get("available"):
        # Старий аудит або відповідь без заголовків у сигналах.
        return PassState.UNAVAILABLE, "page", {}
    if not fact.get("complete"):
        return PassState.FAILED, "page", {}
    return PassState.PASSED, "page", {"checked_url": fact.get("checked_url") or ""}


def _analytics(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    """Пройдене — лише впізнаний вендор; невпізнане вимірювання ним не стає.

    Оцінювач читає ВИД доказу, а не наявність рядка. Три стани замість
    двох: вендор — пройдено; вимірювання без вендора — доказу для
    твердження немає (`UNAVAILABLE`), і це не «немає аналітики»; жодного
    сліду — `FAILED`, як і було. Стара мітка `first_party` зі збережених
    аудитів вендором не вважається: вона означала рівно те, що вендора
    назвати не змогли.
    """
    fact = evidence.get("analytics")
    if fact is None:
        return PassState.UNAVAILABLE, "site", {}
    names = [name for name in (fact.get("found") or []) if isinstance(name, str)]
    verified = [name for name in names if name in VENDOR_NAMES]
    if verified:
        return PassState.PASSED, "site", {"found": ", ".join(verified[:4])}
    seen_measurement = bool(fact.get("unidentified")) or len(names) > len(verified) or any(
        row.get("kind") == Kind.UNIDENTIFIED_MEASUREMENT.value
        for row in (fact.get("observations") or [])
        if isinstance(row, dict)
    )
    return (PassState.UNAVAILABLE if seen_measurement else PassState.FAILED), "site", {}


def _llms_txt(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    info = evidence.get("llms_txt") or {}
    if "exists" not in info:
        return PassState.UNAVAILABLE, "site", {}
    if not info.get("exists"):
        status = info.get("status_code")
        observed = status in (404, 410) or (
            status is not None and 200 <= int(status) < 300
        )
        # Не відповіли чи 5xx — ми не знаємо, чи є файл; це не «провал».
        return (PassState.FAILED if observed else PassState.UNAVAILABLE), "site", {}
    return PassState.PASSED, "site", {}


def _form_protection(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    """Видимий захист форм — стан, у якому пʼять варіантів не зайві.

    `NOT_APPLICABLE` тут не формальність: сайт без форм звернення не має
    що захищати, і зарахувати йому «пройдено» означало б дати бал за
    відсутність предмета перевірки. Так само `UNAVAILABLE` для аудиту,
    знятого до появи сканування: порожнеча там описує нас, а не сайт.
    """
    fact = evidence.get("form_protection")
    if not fact or not fact.get("available"):
        return PassState.UNAVAILABLE, "sampled", {}
    if not fact.get("forms_total"):
        return PassState.NOT_APPLICABLE, "sampled", {}
    protected = fact.get("protected") or []
    if not protected:
        return PassState.FAILED, "sampled", {}
    # «Пройдено» стосується лише тих форм, де сигнал справді видно.
    if fact.get("unprotected"):
        return PassState.FAILED, "sampled", {}
    providers: list[str] = []
    for entry in protected:
        for provider in entry.get("providers") or []:
            if provider not in providers:
                providers.append(provider)
    return (
        PassState.PASSED,
        "sampled",
        {"forms": len(protected), "providers": ", ".join(providers)},
    )


def _jsonld(evidence: dict[str, Any]) -> tuple[PassState, str, dict[str, Any]]:
    data = evidence.get("structured_data") or {}
    if "pages_with_jsonld" not in data:
        return PassState.UNAVAILABLE, "sampled", {}
    with_jsonld = data.get("pages_with_jsonld") or 0
    total = data.get("pages_total") or 0
    if total <= 0:
        return PassState.UNAVAILABLE, "sampled", {}
    if with_jsonld <= 0:
        return PassState.FAILED, "sampled", {}
    return PassState.PASSED, "sampled", {"pages": with_jsonld, "total": total}


# Курований набір. Порядок — порядок у звіті.
CURATED: tuple[tuple[str, Module, Evaluator], ...] = (
    ("seo.https", Module.SEO, _https),
    ("seo.robots_txt", Module.SEO, _robots),
    ("seo.sitemap", Module.SEO, _sitemap),
    ("tech.security_headers", Module.TECH, _security_headers),
    ("tech.analytics", Module.TECH, _analytics),
    ("tech.form_protection", Module.TECH, _form_protection),
    ("ai.jsonld", Module.AI_READY, _jsonld),
    ("ai.llms_txt", Module.AI_READY, _llms_txt),
)

# Яку саме претензію двигуна описує кожен пройдений пункт.
#
# Ключ пройденого — ключ КАТАЛОГУ, а не код чека, і те, що сім із восьми
# збіглися з кодами, — випадковість імен: `ai.jsonld` жодним чеком не
# зветься, його претензію несе `ai.jsonld.missing`. Відображення тому
# оголошене явно. Вивести його з імені означало б мовчки втратити гейт
# рівно на тому пункті, де імена розійшлися, — а мовчки втрачений гейт
# тут повертає рівно той дефект, заради якого E-05 і писався.
GOVERNED_BY: dict[str, tuple[str, ...]] = {
    "seo.https": ("seo.https",),
    "seo.robots_txt": ("seo.robots_txt",),
    "seo.sitemap": ("seo.sitemap",),
    "tech.security_headers": ("tech.security_headers",),
    "tech.analytics": ("tech.analytics",),
    "tech.form_protection": ("tech.form_protection",),
    "ai.jsonld": ("ai.jsonld.missing",),
    "ai.llms_txt": ("ai.llms_txt",),
}


def _state_of(row: Any) -> tuple[ClaimVerdict, Coverage] | None:
    """Канонічний стан одного рядка застосовності, або None — якщо його немає.

    Читається саме пара (вердикт, покриття), а не наявність рядка: рядок є
    в КОЖНОГО оголошеного чека, і зарахувати його присутність за успіх
    означало б замінити одну мовчазну похвалу іншою.
    """
    if not isinstance(row, dict):
        return None
    try:
        return ClaimVerdict(str(row.get("verdict"))), Coverage(str(row.get("coverage")))
    except ValueError:
        return None


def applicability_states(
    evidence: dict[str, Any], key: str
) -> list[tuple[ClaimVerdict, Coverage]] | None:
    """Стани всіх претензій, що стоять за цим пройденим пунктом.

    `None` означає «аудит знято до E-05»: у збереженому доказі блока немає
    взагалі, і вигадувати йому стан не можна — тоді рішення лишається за
    самим оцінювачем, як було до цієї хвилі. Порожній список означає інше:
    блок є, а рядка немає, тобто ствердити `PASS + COMPLETE` немає з чого.
    """
    block = evidence.get("applicability")
    if not isinstance(block, dict) or not block:
        return None
    return [state for name in GOVERNED_BY.get(key, (key,))
            if (state := _state_of(block.get(name))) is not None]


def eligible(evidence: dict[str, Any], key: str) -> bool:
    """Чи має ця перевірка ПРАВО потрапити в пройдені.

    Рівно `PASS + COMPLETE`, і в КОЖНІЙ стратегії агрегації без винятку —
    рішення приймає `applicability.eligible_for_passed_checks`, щоб правило
    жило в одному місці, а не двома копіями, які розійдуться.

    `PASS + PARTIAL` не допускається ніде: «на тому, що прочитали, не
    знайшли» — не те саме, що «перевірили». `NOT_APPLICABLE` не
    допускається тим більше: перевірка, якій не було чого судити, не стає
    успіхом від власної тиші — саме так порожнеча й ставала похвалою.
    """
    # Режим сумісності знімає й це правило: політики немає — немає й
    # гейта. Читається саме модуль, а не імпортована копія константи,
    # щоб важіль лишався один і щоб тест міг його перемкнути.
    if applicability.COMPATIBILITY_MODE:
        return True
    states = applicability_states(evidence, key)
    if states is None:
        return True
    return bool(states) and all(
        eligible_for_passed_checks(verdict, coverage) for verdict, coverage in states
    )


def _withheld(evidence: dict[str, Any], key: str) -> PassState:
    """Чим стає притриманий успіх: незастосовним чи бездоказовим.

    Розрізняти обовʼязково. «Перевірка не стосується цього сайту» і «доказу
    для твердження немає» — різні відповіді, і злити їх в одну означало б
    повторити ту саму помилку, через яку один `scope` колись позначав два
    стани.
    """
    states = applicability_states(evidence, key) or []
    if states and all(verdict is ClaimVerdict.NOT_APPLICABLE for verdict, _ in states):
        return PassState.NOT_APPLICABLE
    return PassState.NO_VERDICT


def collect_passed(
    evidence: dict[str, Any], skipped_modules: set[Module]
) -> list[PassedCheck]:
    """Пройдені перевірки з доказів. Лише PASSED; решта станів — межа."""
    found: list[PassedCheck] = []
    for key, module, evaluate in CURATED:
        if module in skipped_modules:
            continue
        state, scope, facts = evaluate(evidence)
        if state is not PassState.PASSED or not eligible(evidence, key):
            continue
        found.append(PassedCheck(key=key, module=module, scope=scope, facts=facts))
    return found


def evaluate_all(
    evidence: dict[str, Any], skipped_modules: set[Module]
) -> dict[str, PassState]:
    """Стан кожної курованої перевірки — для тестів і діагностики."""
    states: dict[str, PassState] = {}
    for key, module, evaluate in CURATED:
        if module in skipped_modules:
            states[key] = PassState.SKIPPED
            continue
        state, _scope, _facts = evaluate(evidence)
        # Застосовність може лише ПРИТРИМАТИ успіх, ніколи не створити
        # його: `FAILED` лишається `FAILED`, а незастосовне не стає
        # пройденим від того, що політика промовчала.
        if state is PassState.PASSED and not eligible(evidence, key):
            state = _withheld(evidence, key)
        states[key] = state
    return states


__all__ = [
    "CURATED",
    "GOVERNED_BY",
    "PassState",
    "PassedCheck",
    "applicability_states",
    "collect_passed",
    "eligible",
    "evaluate_all",
]
