"""Контракт результату аудиту для інтерфейсу.

Окремий від JSON-експорту навмисно, і це головне рішення файлу.

    ReportDocument            ← спільна бізнес-логіка: пріоритети,
       │                        наслідки, impact, покриття, прогалини
       ├──► AuditResultResponse   (цей файл — веб-інтерфейс)
       ├──► DOCX renderer
       ├──► JSON export           (`report.to_json`, файл на диск)
       └──► публічне посилання

Логіка одна, контракти різні. Якби інтерфейс читав `to_json()`, вони
злиплися б через спільний серіалізатор: зміна формату файла ламала б UI,
а вимога UI спотворювала б файл, який клієнт віддає підряднику. Те, що
вони зараз однакові за змістом, — не привід робити їх одним обʼєктом:
однаковими вони бути перестануть.

**Інтерфейс нічого з цього не рахує.** Ні пріоритетів, ні impact, ні
смуг, ні потенційного балу. Усе поле нижче — готова відповідь; React
лише малює. Інакше бізнес-логіка розповзається у два місця, і друге
неможливо перевірити тестами двигуна.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.audit.enums import (
    AuditStatus,
    Confidence,
    Effort,
    Module,
    Severity,
    Verdict,
)
from app.audit.i18n import DEFAULT_LOCALE, Locale
from app.core.run_enums import FailureClass

# Версія контракту результату. Росте при несумісній зміні форми — саме
# щоб «несумісна зміна» була видимим рішенням, а не наслідком правки поля.
# 2: доступність пішла з `modules` у власний `accessibility`-знімок.
# Споживач, який шукав модуль accessibility серед балів, більше його
# там не знайде — це несумісна зміна, і мовчати про неї не можна.
RESULT_CONTRACT_VERSION = 2

# Чому напряму немає бала. Адитивне поле: версія контракту не росте.
#   "excluded_by_request"   — клієнт вимкнув модуль, нічого не вимірювали
#                             за задумом (деградація `module_excluded`);
#   "withheld_not_measured" — модуль просили, але придатного виміру немає:
#                             провайдер не відповів або не віддав категорії,
#                             вимкнено швидкість, від якої залежить
#                             доступність, сайт не віддав вмісту, оцінку
#                             притримано за покриттям;
#   null                    — бал є.
WithheldReason = Literal["excluded_by_request", "withheld_not_measured"]


class ModuleScoreOut(BaseModel):
    """Оцінка одного напряму разом із тим, наскільки їй можна вірити."""

    module: Module
    score: int | None
    band: str
    weight: float
    issues_count: int
    # Напрям виключено зі скора: даних не було або клієнт його вимкнув.
    excluded: bool
    # Оцінка є, але побудована не на всіх сигналах напряму.
    partial: bool
    # Чому `excluded`: вимкнено клієнтом чи не виміряно. `excluded`
    # лишається тим, чим був, — старі споживачі читають його як і раніше.
    withheld_reason: WithheldReason | None = None


class EvidenceOut(BaseModel):
    """Що саме бачили. Форма вільна — доказ у кожного чека свій."""

    found: Any = None
    expected: Any = None
    extra: dict[str, Any] = Field(default_factory=dict)


class FindingOut(BaseModel):
    """Одна знахідка. Технічний рівень, для розгортання деталей."""

    id: uuid.UUID | None = None
    code: str
    issue_key: str
    module: Module
    severity: Severity
    title: str
    description: str
    recommendation: str
    page_url: str | None
    evidence: dict[str, Any] = Field(default_factory=dict)
    verdict: Verdict | None = None
    verdict_note: str = ""


class PriorityOut(BaseModel):
    """Пріоритезована проблема — одна, а не одне входження.

    Пʼять сторінок без canonical — це один пункт, бо це одна дія.
    Порядок уже правильний: спершу смуга серйозності, всередині —
    вигода на вартість, помножена на важливість сторінки. Сортувати
    заново на клієнті означає зламати цей порядок.
    """

    rank: int
    issue_key: str
    module: Module
    severity: Severity
    title: str
    problem: str
    action: str
    # Наслідок простою мовою, без жаргону — для того, хто ухвалює рішення.
    consequence: str
    scope: str  # "site" | "page"
    affected_pages: int
    affected_examples: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    # Скільки балів дасть виправлення. Сумувати не можна: кожен міряний
    # окремо проти того самого базового скора — див. `impact_is_independent`.
    impact_points: int
    impact_by_module: dict[str, int] = Field(default_factory=dict)
    effort: Effort
    confidence: Confidence


class NextActionOut(BaseModel):
    """Що робити першим. Коротший зріз пріоритетів для тих, хто діє."""

    rank: int
    issue_key: str
    module: Module
    action: str
    why: str
    expected_gain_points: int
    expected_gain: str
    effort: Effort
    affected_pages: int


class MissingDataOut(BaseModel):
    """Чого ми не виміряли і чому. Мовчання про це гірше за пропуск."""

    scope: str
    kind: str
    reason: str
    affects: list[str] = Field(default_factory=list)
    note: str = ""


class CoverageOut(BaseModel):
    """Скільки сайту ми справді прочитали.

    Стоїть поруч із балом навмисно: 20 адрес із 3407 дають бал, поданий
    так само впевнено, як бал за прочитаним повністю сайтом.
    """

    pages_read: int = 0
    pages_fetched: int = 0
    pages_failed: int = 0
    urls_known: int = 0
    # Чи репрезентує прочитане живий сайт. "scored" — так;
    # "scored_with_coverage_limitation" — бали є, але щось матеріально
    # завадило ширшому оглядові; "withheld" — прочитаного замало, а на
    # сайті видно живий вміст, якого ми не оглянули. Причини — слаги
    # фактів (robots_restricted, access_failures, ...), а не пороги.
    state: str = "scored"
    state_reasons: list[str] = Field(default_factory=list)


class ApplicabilityTotalsOut(BaseModel):
    """Скільки претензій модуля справді судилося, а скільки — ні.

    Поруч із балом модуля стоїть те, з чого він складений: `evaluated` —
    претензії, яким було що судити; `not_applicable` — ті, що цього сайту
    не стосуються; `no_verdict` — ті, для яких відповіді немає. Без цих
    трьох чисел мовчання читається як успіх, а саме так порожнеча роками
    й ставала похвалою.
    """

    checks: int = 0
    evaluated: int = 0
    not_applicable: int = 0
    no_verdict: int = 0
    not_measured: int = 0
    failed: int = 0
    # Розклади по канонічному стану: скільки претензій модуля дійшли до
    # PASS/FAIL, а скільки лишились без вердикту або з неповним покриттям.
    verdicts: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, int] = Field(default_factory=dict)


class ResultSummaryOut(BaseModel):
    issues_total: int
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_module: dict[str, int] = Field(default_factory=dict)
    coverage: CoverageOut
    # Бали окремих проблем незалежні: сумувати їх не можна.
    impact_is_independent: bool = True
    # Додано разом із E-05 і лишається порожнім для аудитів, знятих
    # раніше: старий запис цього блока не має, і вигадувати йому числа
    # не можна. Порожній словник тут означає «не рахували», а не «нуль».
    applicability: dict[str, ApplicabilityTotalsOut] = Field(default_factory=dict)


class LocalizationOut(BaseModel):
    """Якою мовою відповідь і чи довелося падати у фолбек."""

    locale: str
    fallback_locale: str
    # Скільки рядків віддано не запитаною мовою. Нуль — переклад повний.
    fell_back_strings: int = 0


class PassedCheckOut(BaseModel):
    """Одна пройдена перевірка — явний доказ, а не тиша чека.

    Другорядна до знахідок: на бали не впливає, штрафів не компенсує.
    `scope` каже, про що твердження: origin | site | page | sampled —
    page-scoped факт ніколи не подається як site-level.
    """

    key: str
    module: Module
    scope: str
    title: str
    facts: dict[str, Any] = Field(default_factory=dict)


class AccessibilityFindingOut(BaseModel):
    """Одна провалена перевірка доступності на виміряній сторінці."""

    audit_id: str
    title: str
    impact: str = ""
    # Наш чек, який говорить про це саме — і лише якщо він СПРАВДІ
    # спрацював у цьому аудиті. None означає «більше ніде не сказано».
    also_reported_as: str | None = None
    also_reported_module: Module | None = None


class AccessibilitySnapshotOut(BaseModel):
    """Доступність ОДНІЄЇ сторінки, а не оцінка сайту.

    Балу 0..100 тут немає навмисно: ми міряємо одну сторінку одним
    зовнішнім інструментом, і бал поруч із балами, порахованими по
    всьому сайту, читався б як рівне з рівним.

    Знаменника «з 76» теж немає: із 76 оголошених перевірок 10 —
    `manual`, їх не виконує ніхто, і ще 0..4 — `informative`.
    """

    available: bool
    measured_url: str | None = None
    strategy: str = "mobile"
    applicable: int | None = None
    passed: int | None = None
    failed: int | None = None
    findings: list[AccessibilityFindingOut] = Field(default_factory=list)
    # Бал Lighthouse для цієї сторінки: зовнішній орієнтир, не наш бал.
    lighthouse_score: float | None = None
    # Доступність показується знімком, але свою частку загального бала
    # поки зберігає — вклад лишили незмінним до калібрування ваг. Без
    # цих полів видимі ваги модулів сходяться до 90%, і споживач не має
    # звідки дізнатися, чому.
    counts_toward_overall: bool = False
    overall_weight: float | None = None
    # Доступність не входить у `modules`, тож причина, чому її не
    # виміряно, стоїть тут. Значення ті самі, що в `ModuleScoreOut`.
    withheld_reason: WithheldReason | None = None


class InspectedPageOut(BaseModel):
    """Одна сторінка, яку аудит справді відкривав.

    Рівно чотири поля, і всі чотири читаються з уже збережених колонок
    `audit_pages`. Полів `rendered` і `discovered_via` тут навмисно немає:
    база їх не зберігає, і показати їх можна було б лише вгадавши — а
    вгадане значення в оплаченому звіті гірше за відсутнє поле.

    `read` виводиться ЛИШЕ зі статусу, тим самим правилом, що й
    `SiteContext.ok_pages`: двохсотий діапазон означає, що сторінку
    прочитано. Розмір тіла, тип вмісту й `raw` тут не беруть участі —
    інакше це була б друга, розбіжна відповідь на те саме питання.
    """

    url: str
    #: `None` — рядок є, а відповіді не було: статус не вигадується.
    status: int | None
    depth: int
    read: bool


class AuditResultResponse(BaseModel):
    """Продуктове представлення результату аудиту.

    Усе, що потрібно головному екрану, одним запитом: як почувається
    сайт, що не так, що виправляти першим, чому це важливо, де саме, і
    чого ми не побачили.
    """

    contract_version: int = RESULT_CONTRACT_VERSION
    audit_id: uuid.UUID
    site_id: uuid.UUID | None = None
    url: str
    origin: str
    status: AuditStatus
    generated_at: datetime
    finished_at: datetime | None = None

    overall_score: int | None
    overall_band: str
    # Бал, який вийде після виправлення всього з next_actions. Рахується
    # перерахунком, а не сумою impact_points: сума завищена.
    potential_score: int | None = None

    modules: list[ModuleScoreOut] = Field(default_factory=list)
    summary: ResultSummaryOut
    priorities: list[PriorityOut] = Field(default_factory=list)
    next_actions: list[NextActionOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)
    missing_data: list[MissingDataOut] = Field(default_factory=list)
    # Доступність подається знімком сторінки замість бала модуля.
    accessibility: AccessibilitySnapshotOut | None = None
    # Пройдені перевірки: курований набір із явним доказом успіху.
    # Адитивне поле: старі відповіді читаються без нього.
    passed_checks: list[PassedCheckOut] = Field(default_factory=list)

    # Чим саме порахований аудит. Без версій дві точки історії однаково
    # пояснюються і змінами на сайті, і змінами в нас.
    engine_versions: dict[str, Any] = Field(default_factory=dict)
    localization: LocalizationOut

    # ── E-14: які саме сторінки ми відкривали ────────────────────────────
    #
    # Лише в оплаченому повному звіті. Адитивні поля: збережений звіт без
    # них читається як раніше, і саме тому вони необовʼязкові, а не
    # порожні за замовчуванням — `None` означає «цей звіт про сторінки не
    # каже», а `[]` означало б «сторінок не було».
    inspected_pages: list[InspectedPageOut] | None = None
    #: Скільки рядків сторінок збережено ДО обрізання списку.
    inspected_pages_total: int | None = None
    #: Істина рівно тоді, коли total більший за довжину поверненого списку.
    inspected_pages_truncated: bool | None = None


# ── E-13: гостьова проєкція незавершеного аудиту ──────────────────────────


class GuestCoverageOut(BaseModel):
    """Покриття короткої проєкції. Чотири ключі, і вони заморожені."""

    pages_read: int | None
    pages_known: int | None
    level: str
    pages_failed: int


class GuestProblemOut(BaseModel):
    """Одна з головних проблем у короткій проєкції."""

    problem: str
    why: str
    impact_points: int
    floored: bool


class GuestShortReportOut(BaseModel):
    """Коротка проєкція готового аудиту, рівно як її складає `to_short`.

    Поля перелічені в тому самому порядку, що й у `FreeAuditResult.to_json`,
    щоб оголошений контракт і надіслані байти збігалися до ключа.

    `extra="forbid"` тут робить дві роботи. Він розрізняє цю проєкцію й
    стан аудиту, коли обидві оголошені однією схемою; і він перетворює
    майбутнє розходження `to_short` із цим контрактом на гучну помилку
    замість тихого поля, якого немає в оголошеній відповіді.
    """

    model_config = ConfigDict(extra="forbid")

    audit_id: str
    url: str
    origin: str
    status: str
    generated_at: str
    overall_score: int | None
    overall_band: str
    issues_total: int
    severity: dict[str, int]
    coverage: GuestCoverageOut
    problems: list[GuestProblemOut] = Field(default_factory=list)
    unlocked: bool


class GuestAuditStatusOut(BaseModel):
    """Стан аудиту, який ще не дає звіту.

    `failure_class` — стабільний машинний перелік; `failure_reason` — уже
    локалізоване речення, а не ключ каталогу: гість не має словника, щоб
    ключ розгорнути. Обидва зʼявляються лише на термінальній невдачі, бо
    поле про невдачу в аудиті, що виконується, — це твердження про те,
    чого ще не сталося.

    `extra="forbid"` тут навмисно: саме воно дозволяє відрізнити цю
    проєкцію від короткого звіту, коли обидві оголошені однією схемою.
    """

    model_config = ConfigDict(extra="forbid")

    audit_id: str
    status: AuditStatus
    unlocked: bool
    progress: dict[str, Any] = Field(default_factory=dict)
    failure_class: FailureClass | None = None
    failure_reason: str | None = None


#: Безпечні пояснення невдачі, по одному на кожен нормалізований клас.
#:
#: Тексти — наслідок для людини, а не діагностика: вони не називають ані
#: провайдера, ані виняток, ані адресу. `provider_failed` свідомо каже
#: «сервіс аналізу», бо назвати постачальника означало б розповісти
#: сторонньому, з чого ми зібрані.
FAILURE_REASONS: dict[FailureClass, dict[Locale, str]] = {
    FailureClass.SITE_UNREACHABLE: {
        Locale.EN: "We could not reach the site. Check the URL and site availability, "
                   "then try again.",
        Locale.UK: "Не вдалося відкрити сайт. Перевірте адресу й доступність сайту "
                   "та спробуйте ще раз.",
        Locale.DE: "Die Website war nicht erreichbar. Prüfen Sie die Adresse und die "
                   "Verfügbarkeit der Website und versuchen Sie es erneut.",
        Locale.ES: "No pudimos acceder al sitio. Comprueba la dirección y la "
                   "disponibilidad del sitio e inténtalo de nuevo.",
        Locale.FR: "Nous n'avons pas pu accéder au site. Vérifiez l'adresse et la "
                   "disponibilité du site, puis réessayez.",
        Locale.RU: "Не удалось открыть сайт. Проверьте адрес и доступность сайта "
                   "и попробуйте ещё раз.",
    },
    FailureClass.SITE_BLOCKED: {
        Locale.EN: "The site blocked automated access to its pages, so the check could "
                   "not be completed.",
        Locale.UK: "Сайт заблокував автоматичний доступ до своїх сторінок, тому "
                   "перевірку не вдалося завершити.",
        Locale.DE: "Die Website hat den automatisierten Zugriff auf ihre Seiten "
                   "blockiert, daher konnte die Prüfung nicht abgeschlossen werden.",
        Locale.ES: "El sitio bloqueó el acceso automatizado a sus páginas, por lo que "
                   "no se pudo completar la comprobación.",
        Locale.FR: "Le site a bloqué l'accès automatisé à ses pages, la vérification "
                   "n'a donc pas pu être terminée.",
        Locale.RU: "Сайт заблокировал автоматический доступ к своим страницам, поэтому "
                   "проверку не удалось завершить.",
    },
    FailureClass.PROVIDER_FAILED: {
        Locale.EN: "An analysis service is temporarily unavailable. Try the check again "
                   "later.",
        Locale.UK: "Сервіс аналізу тимчасово недоступний. Спробуйте перевірку пізніше.",
        Locale.DE: "Ein Analysedienst ist vorübergehend nicht verfügbar. Versuchen Sie "
                   "die Prüfung später erneut.",
        Locale.ES: "Un servicio de análisis no está disponible temporalmente. Vuelve a "
                   "intentar la comprobación más tarde.",
        Locale.FR: "Un service d'analyse est temporairement indisponible. Réessayez la "
                   "vérification plus tard.",
        Locale.RU: "Сервис анализа временно недоступен. Попробуйте проверку позже.",
    },
    FailureClass.INTERNAL_ERROR: {
        Locale.EN: "The check could not be completed because of an internal error. Try "
                   "again or contact support.",
        Locale.UK: "Перевірку не вдалося завершити через внутрішню помилку. Спробуйте "
                   "ще раз або зверніться до підтримки.",
        Locale.DE: "Die Prüfung konnte wegen eines internen Fehlers nicht abgeschlossen "
                   "werden. Versuchen Sie es erneut oder wenden Sie sich an den Support.",
        Locale.ES: "La comprobación no se pudo completar por un error interno. Inténtalo "
                   "de nuevo o contacta con soporte.",
        Locale.FR: "La vérification n'a pas pu être terminée en raison d'une erreur "
                   "interne. Réessayez ou contactez l'assistance.",
        Locale.RU: "Проверку не удалось завершить из-за внутренней ошибки. Попробуйте "
                   "ещё раз или обратитесь в поддержку.",
    },
    FailureClass.CANCELLED: {
        Locale.EN: "The check was cancelled. Start a new check if needed.",
        Locale.UK: "Перевірку скасовано. За потреби запустіть нову.",
        Locale.DE: "Die Prüfung wurde abgebrochen. Starten Sie bei Bedarf eine neue "
                   "Prüfung.",
        Locale.ES: "La comprobación se canceló. Inicia una nueva si la necesitas.",
        Locale.FR: "La vérification a été annulée. Lancez-en une nouvelle si nécessaire.",
        Locale.RU: "Проверка отменена. При необходимости запустите новую.",
    },
}


def failure_reason(
    failure_class: FailureClass | None, locale: Locale | None = DEFAULT_LOCALE
) -> str:
    """Безпечне речення для класу невдачі, тією мовою, якою просили.

    Та сама резолюція, що в `report.i18n.t`: мова, якої немає в каталозі,
    падає на мову за замовчуванням, а не на сирий ключ. Невідомий або
    відсутній клас подається як внутрішня помилка — це єдиний чесний
    загальний стан, і він ніколи не показує, чого саме ми не знаємо.

    `None` як мова — не помилка виклику, а звичайний стан маршруту:
    `i18n.parse` віддає саме його на незнайомому `?lang=`, і сусідні
    `short_view` та `full_view` приймають той самий тип. Означає воно те
    саме, що й незнайома мова, — англійську.
    """
    return failure_fields(failure_class, locale)[1]


def failure_fields(
    stored: FailureClass | str | None, locale: Locale | None = DEFAULT_LOCALE
) -> tuple[FailureClass, str]:
    """Клас і речення ОДНИМ рішенням — бо нарізно вони розходяться.

    Попередня версія нормалізувала лише текст: `failure_reason` падав на
    `INTERNAL_ERROR`, а клас маршрут брав із бази як є. Аудит із
    порожньою колонкою через це віддавав `failure_class: null` поруч із
    реченням про внутрішню помилку — два твердження про одну невдачу,
    які суперечать одне одному. Гірше: нерозпізнаний рядок у колонці
    валив валідацію моделі, тобто гість отримував 500 замість
    пояснення.

    Тому нормалізація тут одна, і вона віддає пару. Розійтися їм більше
    немає де: викликач не може взяти клас з одного джерела, а текст з
    іншого.

    Сире `audit.error` сюди не потрапляє й потрапити не може — на вході
    лише колонка класу.
    """
    if isinstance(stored, str) and not isinstance(stored, FailureClass):
        try:
            stored = FailureClass(stored)
        except ValueError:
            stored = None
    if stored is None or stored not in FAILURE_REASONS:
        stored = FailureClass.INTERNAL_ERROR
    texts = FAILURE_REASONS[stored]
    return stored, (texts.get(locale) if locale is not None else None) or texts[DEFAULT_LOCALE]


__all__ = [
    "FAILURE_REASONS",
    "RESULT_CONTRACT_VERSION",
    "AccessibilityFindingOut",
    "AccessibilitySnapshotOut",
    "AuditResultResponse",
    "CoverageOut",
    "EvidenceOut",
    "FindingOut",
    "GuestAuditStatusOut",
    "GuestCoverageOut",
    "GuestProblemOut",
    "GuestShortReportOut",
    "InspectedPageOut",
    "LocalizationOut",
    "MissingDataOut",
    "ModuleScoreOut",
    "NextActionOut",
    "PassedCheckOut",
    "PriorityOut",
    "ResultSummaryOut",
    "failure_fields",
    "failure_reason",
]
