import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.audit.enums import AuditStatus, AuditTrigger, Module, Severity, Verdict
from app.audit.i18n import DEFAULT_LOCALE
from app.core.db import Base
from app.core.run_enums import FailureClass, QuotaSource, QuotaState

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Audit(Base):
    """Один запуск аудиту. Він же AuditRun.

    Окремої сутності «запуск» не заводимо навмисно: ця таблиця вже
    незмінна після завершення, вже несе версії, статуси й часові мітки.
    Паралельна audit_runs означала б дві історії того самого — і питання
    «яка з них правда» без відповіді.

    Власник — організація. `site_id` порожній для аудитів із CLI, які
    сайту не мають; `created_by_user_id` порожній для запланованих, у
    яких немає людини.
    """

    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    # RESTRICT, а не CASCADE: аудити — історія, за яку заплатили. Видалення
    # організації не має тихо забирати її з собою; це окремий свідомий крок.
    #
    # Після завершення в аудиту можуть змінитися РІВНО ДВА поля, обидва —
    # організаційне групування, і кожна зміна пояснюється журналом:
    #
    # - `site_id` — при обʼєднанні сайтів; причина в `site_merges`;
    # - `organization_id` — ЛИШЕ при злитті гостьової організації в
    #   наявну (`application.guest.merge_into`); причина в `guest_merges`.
    #   Це вузький виняток, а не дозвіл: загального шляху перенести
    #   завершений аудит між організаціями немає і не має зʼявитися —
    #   джерело злиття буває лише гостьовим, операція одноразова,
    #   термінальна (kind → CLAIMED) і тримає перелік перенесеного.
    #
    # Групування — відповідь на питання «до якого ресурсу належить цей
    # запис», а не «що ми виміряли». Виміряне лежить у `url`, `origin`,
    # `requested_options`, `options`, `scores`, `versions`, `snapshot`,
    # `evidence` і часових мітках — і воно незмінне назавжди.
    #
    # Різниця не термінологічна: вона дозволяє переставити записи між
    # ресурсами, не переписавши жодного минулого числа. Крива історії
    # йде за ресурсом, а кожен аудит і далі каже, яку саме адресу він
    # читав і якими правилами був порахований.
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Розклад, який породив цей запуск, і **момент входження**, на який
    # він запланований.
    #
    # Разом вони дають стабільний ключ входження: один запланований
    # момент = рівно один AuditRun. Без нього повтор — прострочена
    # оренда, перезапуск планувальника, повторна доставка в чергу —
    # створював би другий історичний запис про ту саму дев'яту ранку, і
    # крива показувала б два аудити там, де був один.
    #
    # `scheduled_for` зберігається як абсолютний момент у UTC. Локальними
    # є **правила** розкладу (зона, година, день тижня); момент, на який
    # вони розв'язалися, локальним бути не може — інакше його неможливо
    # порівняти з `now()`.
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_schedules.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Скільки разів бралися виконувати. Повтор — це нова спроба того
    # самого запуску, а не новий запуск: історія має показувати один
    # аудит, який довелося перезапустити, а не два аудити.
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    trigger: Mapped[AuditTrigger] = mapped_column(
        Enum(AuditTrigger, name="audit_trigger", native_enum=False),
        default=AuditTrigger.MANUAL,
        server_default=AuditTrigger.MANUAL.name,
    )
    # Що саме почищено за строком утримання. Дві мітки, а не одна: у
    # сирих даних і знахідок різні строки, і одним полем «почищено» їх не
    # розрізнити — а різниця видима клієнту. Аудит без знімка ще можна
    # перечитати, аудит без знахідок — уже ні.
    #
    # Сам рядок не чиститься ніколи: на ньому тримається крива історії, і
    # діра в ній читається як «нічого не сталося».
    raw_purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    findings_purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Зведення знахідок: скільки й яких. Рахується при завершенні аудиту,
    # а не при чистці.
    #
    # Це похідні дані поруч із джерелом — те саме, за що в цьому проєкті
    # уже викидали колонку (`audit_schedules.last_audit_id`). Різниця в
    # критерії: там джерело лишалося назавжди й похідне могло з ним
    # розійтися, тут джерело **свідомо знищується за строком**. Зведення,
    # яке переживає своє джерело, — не дубль, а єдине, що лишиться.
    findings_summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    # Що клієнт просив, до обрізання правами тарифу.
    #
    # Окремо від `options`, бо мовчазне обрізання — це відповідь не на те
    # питання, яке поставили. Клієнт просив 100 сторінок і отримав 10;
    # якщо в записі лишається тільки 10, ні він, ні ми через місяць не
    # зможемо пояснити, чому звіт неповний. Пара «просив / зробили» — це
    # факт, і з неї видно різницю без жодного третього поля.
    requested_options: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    # Доля зарезервованої одиниці квоти. Резерв при створенні закриває
    # гонку, але мусить мати завершення: інакше «списали й забули»
    # перетворюється на «клієнт заплатив за нашу поломку».
    quota_state: Mapped[QuotaState] = mapped_column(
        Enum(QuotaState, name="audit_quota_state", native_enum=False),
        default=QuotaState.RESERVED,
        server_default=QuotaState.RESERVED.name,
    )
    # З чого оплачено: періодна квота чи окремо куплений кредит. Від
    # цього залежить, куди повертати одиницю, якщо аудит не відбувся з
    # нашої вини. Порожньо — аудит, створений до появи разових покупок.
    quota_source: Mapped[QuotaSource | None] = mapped_column(
        Enum(QuotaSource, name="audit_quota_source", native_enum=False), nullable=True
    )
    # Чому не вийшло. Поле, а не розбір рядка `error`: від класу залежить,
    # чи повертається квота.
    failure_class: Mapped[FailureClass | None] = mapped_column(
        Enum(FailureClass, name="audit_failure_class", native_enum=False), nullable=True
    )

    url: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, name="audit_status", native_enum=False),
        default=AuditStatus.QUEUED,
        index=True,
    )
    options: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    score_overall: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Матеріал для звіту, якого не відновити з issues та pages.
    degraded: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    skipped_modules: Mapped[list[str]] = mapped_column(JSONType, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    # Чим саме порахований цей аудит: версії краулера, детекторів,
    # скорингу, конфігурації й моделі. Без них два аудити того самого
    # сайту не можна порівняти — різниця однаково пояснюється і змінами
    # на сайті, і змінами в нас.
    versions: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    # Де саме зараз аудит: `{"stage": …, "pages_read": N, "pages_known": M}`.
    #
    # Числа справжні — ті самі, що потім стануть покриттям у звіті. Саме
    # тому поле й існує: показати клієнту вигадану смужку, яка повзе до
    # 90% і чекає, означало б порушити те правило, на якому тримається
    # весь продукт. Немає чесного числа — немає й індикатора.
    #
    # Заповнюється лише для аудиту з ОДНІЄЮ ціллю: при кількох цілях
    # краули йдуть паралельно, і одне число описувало б то одну, то іншу.
    # Порожнеча тут чесніша за неоднозначність.
    progress: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    targets: Mapped[list["AuditTarget"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AuditTarget.position",
    )
    pages: Mapped[list["AuditPage"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", lazy="selectin"
    )
    issues: Mapped[list["AuditIssue"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", lazy="selectin"
    )
    attempt_log: Mapped[list["AuditAttempt"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AuditAttempt.number",
    )

    __table_args__ = (
        # Головний запит історії: аудити організації в зворотному
        # хронологічному порядку, і той самий по сайту.
        Index("ix_audits_org_created", "organization_id", "created_at"),
        Index("ix_audits_site_created", "site_id", "created_at"),
        # Один запланований момент — рівно один запуск. Обмеження в базі,
        # бо перевірка в коді не переживе двох планувальників, що взялися
        # за той самий розклад після простроченої оренди.
        Index(
            "uq_audit_scheduled_occurrence",
            "schedule_id",
            "scheduled_for",
            unique=True,
            postgresql_where=schedule_id.is_not(None),
        ),
    )



class AuditAttempt(Base):
    """Одна спроба виконати запуск. Їх може бути кілька, запуск один.

    Лічильника `Audit.attempts` вистачає, щоб знати *скільки* разів
    бралися, але не *чому* кожна не вийшла. А саме це і є питання, яке
    ставлять через рік до розкладу, що падає щоночі: перша спроба
    провалилась на провайдері, друга — на нашому коді, і це зовсім інша
    історія, ніж дві однакові.

    Таблиця не входить у «важкі дані»: чистка за строком утримання
    прибирає сторінки й докази, а журнал спроб лишається — він маленький
    і саме він пояснює діри в кривій.
    """

    __tablename__ = "audit_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    # Порядковий номер, з одиниці. Разом із audit_id — природний ключ:
    # повторна доставка того самого повідомлення в чергу не має додавати
    # рядок про спробу, якої не було.
    number: Mapped[int] = mapped_column(SmallInteger)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Чим скінчилася саме ця спроба, не запуск. Спроба, обірвана падінням
    # воркера, лишається незавершеною — і це теж відповідь.
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, name="audit_status", native_enum=False),
        default=AuditStatus.RUNNING,
    )
    failure_class: Mapped[FailureClass | None] = mapped_column(
        Enum(FailureClass, name="audit_failure_class", native_enum=False), nullable=True
    )
    error: Mapped[str] = mapped_column(Text, default="")
    # Чому після цієї спроби вирішили пробувати ще раз — або не пробувати.
    #
    # Ключ і параметри — джерело правди; рядок поруч лишається технічним
    # слідом канонічною мовою. Той самий поділ, що в знахідок і
    # деградацій, і з тієї ж причини: інакше клієнт, який читає продукт
    # німецькою, бачив би тут українське речення.
    retry_decision: Mapped[str] = mapped_column(Text, default="")
    retry_decision_key: Mapped[str] = mapped_column(String(64), default="")
    retry_decision_params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    audit: Mapped[Audit] = relationship(back_populates="attempt_log")

    __table_args__ = (UniqueConstraint("audit_id", "number", name="uq_attempt_number"),)


class AuditTarget(Base):
    """Одна ціль аудиту: свій краул, свої issues, свій скор.

    Аудит стає контейнером: його score_overall — зведений по цілях.
    Поля url/origin/status/scores на audits лишаються як «первинна ціль»,
    щоб наявні клієнти API не зламалися.
    """

    __tablename__ = "audit_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, default=0)
    url: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, name="audit_status", native_enum=False), default=AuditStatus.QUEUED
    )
    score_overall: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Чому саме ця ціль не вийшла. Клас живе тут, а не лише на аудиті,
    # бо тут його ще видно: виняток ловиться на рівні цілі, і до зведення
    # від нього лишається сам текст. А від класу залежать і гроші, і те,
    # чи є сенс пробувати ще раз.
    failure_class: Mapped[FailureClass | None] = mapped_column(
        Enum(FailureClass, name="audit_failure_class", native_enum=False), nullable=True
    )

    degraded: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    skipped_modules: Mapped[list[str]] = mapped_column(JSONType, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    # Чим саме порахований цей аудит: версії краулера, детекторів,
    # скорингу, конфігурації й моделі. Без них два аудити того самого
    # сайту не можна порівняти — різниця однаково пояснюється і змінами
    # на сайті, і змінами в нас.
    versions: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    # Зібране без втрат: із цього можна перерахувати аудит за новими
    # правилами, не краулячи сайт заново. Порожньо для аудитів, зроблених
    # до появи знімка, — вигадати їх заднім числом ми не можемо.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audit: Mapped[Audit] = relationship(back_populates="targets")
    pages: Mapped[list["AuditPage"]] = relationship(
        back_populates="target", lazy="selectin", viewonly=True
    )
    issues: Mapped[list["AuditIssue"]] = relationship(
        back_populates="target", lazy="selectin", viewonly=True
    )

    __table_args__ = (UniqueConstraint("audit_id", "url", name="uq_audit_targets_audit_url"),)


class ReportLink(Base):
    """Публічне посилання на звіт.

    Токен лежить лише як SHA-256: дамп бази або випадковий SELECT не має
    роздавати робочі посилання на чужі звіти. Відкритий токен існує один
    раз — у відповіді на створення.
    """

    __tablename__ = "report_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_targets.id", ondelete="CASCADE"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Мова документа, зафіксована при створенні посилання.
    #
    # Рядок BCP-47, а не enum у базі: додати мову має бути правкою коду, а
    # не міграцією типу. Довжина з запасом на регіон (`pt-BR`), хоч
    # каталогів на регіон поки немає.
    lang: Mapped[str] = mapped_column(String(8), default=DEFAULT_LOCALE.value)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # NULL — безстрокове. Зʼявилося разом із платним доступом гостя:
    # куплений звіт не має зникати через сім днів разом із сесією, а
    # вигаданий «довгий» строк був би тим самим правдоподібним числом,
    # якого проєкт уникає всюди. Право закінчується відкликанням —
    # повернення коштів, безпека, — а не календарем.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Розблокування, заради якого посилання видано. Порожньо в
    # звичайних посилань з кабінету. Токен — не саме право, а лише
    # предʼявлення: право лежить у AuditUnlock, і відкликання токена
    # його не чіпає. Звʼязок потрібен, щоб при поверненні коштів
    # відкликати саме платні посилання, не зачепивши поділені з
    # кабінету, — і щоб пояснити, звідки посилання взялося.
    unlock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_unlocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    views: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > datetime.now(UTC)


class AuditPage(Base):
    __tablename__ = "audit_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_targets.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    html_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depth: Mapped[int] = mapped_column(SmallInteger, default=0)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    audit: Mapped[Audit] = relationship(back_populates="pages")
    target: Mapped["AuditTarget"] = relationship(back_populates="pages")

    __table_args__ = (Index("ix_audit_pages_audit_url", "audit_id", "url"),)


class AuditIssue(Base):
    __tablename__ = "audit_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_targets.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_pages.id", ondelete="CASCADE"), nullable=True
    )
    module: Mapped[Module] = mapped_column(Enum(Module, name="issue_module", native_enum=False))
    code: Mapped[str] = mapped_column(String(96))
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="issue_severity", native_enum=False)
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    weight: Mapped[int] = mapped_column(SmallInteger, default=1)

    # Яку саме проблему з тих, що розрізняє чек, описує ця знахідка.
    # Порожньо — чек знає лише одну. Разом із `code` дає `issue_key`,
    # за яким рахується стеля штрафу й групуються рекомендації.
    #
    # Окрема колонка, а не виведення з msg_key: ключ каталогу міняється
    # разом із формулюванням, а ідентифікатор проблеми мусить пережити
    # переписаний текст. Порожньо в старих рядках означає «до поділу» —
    # там issue_key дорівнює коду, тобто рівно те, чим він і був.
    issue_variant: Mapped[str] = mapped_column(String(48), default="")

    # Ключ каталогу i18n і його параметри: без них збережений аудит
    # не перекласти іншою мовою — у БД лежить лише відрендерений текст.
    msg_key: Mapped[str] = mapped_column(String(96), default="")
    msg_params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    audit: Mapped[Audit] = relationship(back_populates="issues")
    target: Mapped["AuditTarget"] = relationship(back_populates="issues")
    # Порядок INSERT'ів SQLAlchemy будує за relationship'ами, а не за FK на
    # рівні таблиць. Без цього issues летіли в базу раніше за сторінки.
    page: Mapped["AuditPage | None"] = relationship()
    # Що сказала про цю знахідку людина. Один вердикт на знахідку:
    # думка може змінитися, і тоді запис оновлюється.
    #
    # Не `verdict`: у схемі API поле з такою назвою тримає сам enum, а
    # pydantic із `from_attributes` бере атрибут за іменем і падає на
    # ORM-обʼєкті. Помилка вилазила лише після першого записаного
    # вердикту, тобто на живому стеку й не одразу.
    human_verdict: Mapped["IssueVerdict | None"] = relationship(
        back_populates="issue", cascade="all, delete-orphan", lazy="selectin",
        uselist=False,
    )

    __table_args__ = (Index("ix_audit_issues_filter", "audit_id", "module", "severity"),)


class IssueVerdict(Base):
    """Що сказала людина про конкретну знахідку.

    Єдине джерело зовнішньої правди, яке в цього проєкту може зʼявитися.
    Калібрування досі спиралося на гіпотезу про рівень сайту, і саме
    тому розділення в середині діапазону нічим не перевірити: немає з
    чим звіряти. Вердикти дають те, з чим.

    Один вердикт на знахідку: думка може змінитися, і тоді запис
    оновлюється, а не додається другий. Історія тут не потрібна —
    потрібна нинішня відповідь.
    """

    __tablename__ = "issue_verdicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_issues.id", ondelete="CASCADE"), index=True
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    # Дублюються з issue навмисно: зведення по чеках має працювати після
    # того, як аудит видалять, інакше дані про якість чека живуть рівно
    # стільки, скільки аудит, у якому вони зібрані.
    code: Mapped[str] = mapped_column(String(96), index=True)
    msg: Mapped[str] = mapped_column(String(96), default="")

    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, name="issue_verdict", native_enum=False))
    note: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    issue: Mapped["AuditIssue"] = relationship(back_populates="human_verdict")

    __table_args__ = (UniqueConstraint("issue_id", name="uq_issue_verdicts_issue"),)
