from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.audit.enums import AuditStatus, AuditTrigger, Module, Severity, Verdict
from app.audit.fetcher import UnsafeUrlError, normalize_url
from app.audit.i18n import DEFAULT_LOCALE, Locale, notice, render
from app.audit.llm.models import AVAILABLE_MODELS, MODEL_IDS
from app.core.run_enums import FailureClass, QuotaState


class AuditOptionsIn(BaseModel):
    max_pages: int = Field(default=25, ge=1, le=200)
    max_depth: int = Field(default=2, ge=0, le=4)
    strategies: list[Literal["mobile", "desktop"]] = Field(default_factory=lambda: ["mobile"])
    modules: list[Module] | None = None

    # Мови, у яких клієнт хоче отримати звіт. На сам аудит не впливають —
    # рендер завжди доступний будь-якою мовою — але роблять запис
    # самоописовим: сторінка результату знає, які файли пропонувати.
    languages: list[Locale] = Field(
        default_factory=lambda: [DEFAULT_LOCALE], min_length=1
    )

    # None — як налаштовано на сервері; False вимикає для цього аудиту.
    render: bool | None = None
    llm: bool | None = None
    # Модель семантичного аналізу. None — серверна за замовчуванням.
    # Вибір видно у відповіді разом із рештою опцій: без нього два звіти
    # про той самий сайт із різними балами неможливо пояснити.
    llm_model: str | None = None

    @field_validator("languages")
    @classmethod
    def _unique_languages(cls, v: list[Locale]) -> list[Locale]:
        return list(dict.fromkeys(v))

    @field_validator("llm_model")
    @classmethod
    def _known_model(cls, v: str | None) -> str | None:
        if v is not None and v not in MODEL_IDS:
            raise ValueError(f"невідома модель: {v}. Доступні: {', '.join(MODEL_IDS)}")
        return v


class LlmModelOut(BaseModel):
    """Список для інтерфейсу. Береться з того самого каталогу, що й
    валідація, — інакше UI пропонував би модель, яку API відбиває."""

    id: str
    label: str
    cost_per_audit: float
    note: str
    default: bool

    @staticmethod
    def catalogue() -> list[LlmModelOut]:
        return [
            LlmModelOut(
                id=m.id,
                label=m.label,
                cost_per_audit=m.cost_per_audit,
                note=m.note,
                default=m.default,
            )
            for m in AVAILABLE_MODELS
        ]


MAX_TARGETS = 10


class AuditCreate(BaseModel):
    """Приймає `url` або `urls` — старі клієнти шлють перше, нові друге."""

    url: str | None = None
    urls: list[str] | None = None
    options: AuditOptionsIn = Field(default_factory=AuditOptionsIn)

    @model_validator(mode="after")
    def _normalize_targets(self) -> AuditCreate:
        raw = self.urls if self.urls else ([self.url] if self.url else [])
        if not raw:
            raise ValueError("вкажіть url або urls")

        normalized: list[str] = []
        for candidate in raw:
            try:
                value = normalize_url(candidate)
            except UnsafeUrlError as exc:
                raise ValueError(f"{candidate}: {exc}") from exc
            if value not in normalized:
                normalized.append(value)

        if len(normalized) > MAX_TARGETS:
            raise ValueError(f"не більше {MAX_TARGETS} URL на один аудит")

        self.urls = normalized
        self.url = normalized[0]
        return self

    @property
    def targets(self) -> list[str]:
        return self.urls or []


class IssueOut(BaseModel):
    id: uuid.UUID
    module: Module
    code: str
    severity: Severity
    title: str
    description: str
    recommendation: str
    evidence: dict[str, Any]
    page_url: str | None = None
    # Ключ повідомлення: один `code` віддає різні проблеми, і для
    # клієнта це різні дії. Порівняння з конкурентами оперує саме
    # ключами, тож без нього інтерфейсу нема чим підписати їхні списки.
    msg: str = ""
    # Що сказала про знахідку людина, якщо вже казала. Без цього
    # інтерфейс не може показати, на що вже відповіли, і те саме
    # питання ставилося б знову при кожному відкритті звіту.
    verdict: Verdict | None = None
    verdict_note: str = ""

    # Мова, якою текст справді віддали. Може відрізнятися від запитаної:
    # у частковому каталозі окремі ключі падають в англійську. Клієнту це
    # не шум — це підпис під текстом іншою мовою, ніж решта сторінки.
    text_locale: str = ""

    @classmethod
    def from_issue(cls, issue: Any, locale: Locale | None = None) -> IssueOut:
        """Знахідка потрібною мовою, разом із відповіддю людини.

        Текст **не** береться зі збережених стовпців `title` /
        `description` / `recommendation`: вони кеш однієї мови, і брати їх
        означало б віддавати той самий аудит завжди однією. Джерело
        правди — `msg_key` і `msg_params`, тобто ключ каталогу й дані для
        підстановки. Саме тому завершений торік аудит віддається новою
        мовою без жодного повторного запуску двигуна.
        """
        out = cls.model_validate(issue)
        out.msg = getattr(issue, "msg_key", "") or issue.code
        if locale is not None:
            text = render(out.msg, dict(getattr(issue, "msg_params", None) or {}), locale)
            out.title = text.title
            out.description = text.description
            out.recommendation = text.recommendation
            out.text_locale = text.locale.value
        recorded = getattr(issue, "human_verdict", None)
        if recorded is not None:
            out.verdict = recorded.verdict
            out.verdict_note = recorded.note
        return out

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    url: str
    status_code: int | None
    response_ms: int | None
    depth: int
    raw: dict[str, Any]

    model_config = {"from_attributes": True}


class AuditOut(BaseModel):
    id: uuid.UUID
    # Сайт, до якого належить запуск. Порожньо для аудитів із CLI, які
    # сайту не мають.
    #
    # Без цього поля інтерфейс зіставляв би аудит із сайтом за рядком
    # origin — тобто рівно тим способом, від якого сутність Site і
    # рятує: переїзд на інший хост розривав би звʼязок.
    site_id: uuid.UUID | None = None
    url: str
    origin: str
    status: AuditStatus
    score_overall: int | None
    scores: dict[str, int] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    # Звідки взявся запуск. Історія без цього не відповідає на найчастіше
    # питання до неї — «я цього не запускав, звідки воно?».
    trigger: AuditTrigger = AuditTrigger.MANUAL
    # Якою мовою складено звіт. Один клієнт може мати звіти двома мовами,
    # і в переліку це має бути видно без відкривання кожного.
    locale: str = ""

    # Що просили і що з цього тариф дозволив. Порожній перелік означає,
    # що обмежень не було, — і це теж відповідь.
    #
    # Обчислюється з пари requested/effective, а не зберігається третім
    # полем: третє поле може розійтися з першими двома, похідне — ні.
    option_adjustments: list[dict[str, Any]] = Field(default_factory=list)
    # Доля зарезервованої одиниці квоти й причина невдачі, якщо була.
    quota_state: QuotaState = QuotaState.RESERVED
    failure_class: FailureClass | None = None
    # Скільки разів бралися виконувати. Більше одного означає, що були
    # повтори — і що це один запуск, а не кілька.
    attempts: int = 0

    model_config = {"from_attributes": True}

    @classmethod
    def of(cls, audit: Any) -> AuditOut:
        """Зібрати відповідь, доклавши похідні поля.

        `model_validate` сам їх не порахує: різниця опцій живе не в
        колонці, а в порівнянні двох колонок.
        """
        from app.application.options import describe

        out = cls.model_validate(audit)
        out.option_adjustments = describe(audit.requested_options or {}, audit.options or {})
        return out


class TargetOut(BaseModel):
    id: uuid.UUID
    position: int
    url: str
    origin: str
    status: AuditStatus
    score_overall: int | None
    scores: dict[str, int] | None
    error: str | None
    failure_class: FailureClass | None = None

    model_config = {"from_attributes": True}


class AttemptOut(BaseModel):
    """Одна спроба виконати запуск.

    Показується разом з аудитом, а не окремим ендпойнтом: питання «чому
    цей запуск такий» ставлять, дивлячись саме на нього, і відповідь має
    бути там же.
    """

    number: int
    status: AuditStatus
    failure_class: FailureClass | None
    # Технічний слід. Не пояснення для клієнта: це текст винятку,
    # машинний і англійський, і локалізувати його нема чого.
    error: str
    retry_decision: str
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}

    @classmethod
    def of(cls, attempt: Any, locale: Locale | None = None) -> AttemptOut:
        out = cls.model_validate(attempt)
        key = getattr(attempt, "retry_decision_key", "")
        if locale is not None and key:
            out.retry_decision = notice(
                key, dict(getattr(attempt, "retry_decision_params", None) or {}), locale
            )
        return out


class ShareLinkCreate(BaseModel):
    target: uuid.UUID | None = None
    # Порожньо — резолвити з налаштувань того, хто створює посилання.
    #
    # Мова тут фіксується назавжди й навмисно: одержувач посилання
    # налаштувань не має, і читати її з його браузера означало б віддати
    # документ мовою, якої автор не обирав.
    lang: Locale | None = None
    ttl_days: int = Field(default=14, ge=1, le=90)


class ShareLinkOut(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID | None
    lang: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    views: int

    model_config = {"from_attributes": True}


class ShareLinkCreated(ShareLinkOut):
    """Токен є лише тут: у базі лежить його SHA-256, відновити не вийде."""

    token: str
    path: str


class AuditDetailOut(AuditOut):
    # Мова, якою віддано тексти знахідок. Не властивість аудиту: той
    # самий запуск віддається різними мовами різним читачам, і це поле
    # описує саме цю відповідь, а не виміряний факт.
    locale: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    targets: list[TargetOut] = Field(default_factory=list)
    pages_count: int = 0
    issues_count: int = 0
    issues_by_severity: dict[str, int] = Field(default_factory=dict)
    issues: list[IssueOut] = Field(default_factory=list)
    pages: list[PageOut] = Field(default_factory=list)
    # Порожній для запуску, який вийшов з першого разу. Заповнений —
    # єдина відповідь на питання, чи були всі невдачі однакові.
    attempt_log: list[AttemptOut] = Field(default_factory=list)


class VerdictIn(BaseModel):
    """Що людина каже про знахідку.

    `wrong` і `wont_fix` розділені навмисно: перше свідчить проти чека,
    друге — про пріоритети клієнта. Одна кнопка «відхилити» зробила б
    обидва однаково марними як дані.
    """

    verdict: Verdict
    note: str = Field("", max_length=2000)
    author: str = Field("", max_length=120)
