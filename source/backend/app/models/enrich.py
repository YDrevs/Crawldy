"""Журнал AI-збагачення: прогони й спроби, окремо від правди аудиту.

AI-похідний вихід ЗАВЖДИ відрізняється від детерміністичної правди тим,
що живе у власних таблицях: у core-записах аудиту немає й не буде
колонок на кшталт `anthropic_model` чи `claude_output`. Імена тут
провайдеро-нейтральні; фактичний провайдер і модель — дані провенансу
в рядках спроб, а не частина контракту.

`EnrichmentRun` — логічний результат з ідемпотентною ідентичністю:
аудит + задача + версії задачі/промпта/схеми + хеш канонічного входу.
Унікальний індекс по цій ідентичності — і є правило «повторне відкриття
звіту не породжує повторний платний виклик»: та сама логічна робота
вирішується в той самий рядок. Зміна маршруту чи моделі НЕ переписує
збережений результат: перегенерація — лише через явний reprocess
(перезапуск невдалого рядка) або нову версію задачі/промпта/схеми
(новий рядок, стара провенансія лишається).

`EnrichmentAttempt` — кожна фактична спроба, включно з невдалими:
fallback видно в журналі, а не здогадується з мовчання. `cost_usd`
лишається NULL без надійної цінової бази — токени записуються завжди,
коли провайдер їх віддав.

Секретів тут немає за побудовою: ані ключів, ані заголовків
авторизації, ані сирих провайдерських дампів — канонічний хеш входу,
версії, валідований вихід і метадані.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
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

from app.core.db import Base
from app.enrich.contracts import EnrichmentStatus, TaskType

JSONType = JSON().with_variant(JSONB(), "postgresql")


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), index=True
    )
    task_type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, name="enrichment_task_type", native_enum=False)
    )
    task_version: Mapped[str] = mapped_column(String(16))
    prompt_version: Mapped[str] = mapped_column(String(16))
    schema_version: Mapped[str] = mapped_column(String(16))
    routing_version: Mapped[str] = mapped_column(String(16), default="")
    locale: Mapped[str] = mapped_column(String(8), default="en")
    input_hash: Mapped[str] = mapped_column(String(64))

    status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(EnrichmentStatus, name="enrichment_status", native_enum=False),
        default=EnrichmentStatus.PENDING,
    )
    # Валідований структурний вихід задачі — контракт Crawldy, без
    # провайдерської обгортки. Порожньо, поки прогін не завершився.
    result: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempts: Mapped[list[EnrichmentAttempt]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="EnrichmentAttempt.number"
    )

    __table_args__ = (
        UniqueConstraint(
            "audit_id",
            "task_type",
            "task_version",
            "prompt_version",
            "schema_version",
            "input_hash",
            name="uq_enrichment_identity",
        ),
        Index("ix_enrichment_runs_audit_task", "audit_id", "task_type"),
    )


class EnrichmentAttempt(Base):
    __tablename__ = "enrichment_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrichment_runs.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(SmallInteger)

    # Що фактично викликалось — провенанс, не конфігурація.
    provider: Mapped[str] = mapped_column(String(32))
    # Модель, якою провайдер відпрацював. Може бути датованим знімком
    # запитаної; підміняти її «чистим» імʼям не можна — це запис про те,
    # чим саме пораховано результат.
    model: Mapped[str] = mapped_column(String(64))
    # Що просив маршрут, і під яким імʼям шукалася ціна. Три різні
    # величини живуть окремо, бо збігаються не завжди: перший живий
    # виклик OpenAI повернув знімок, якого в ціннику немає, і вартість
    # вийшла порожньою.
    requested_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pricing_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    outcome: Mapped[str] = mapped_column(String(24))
    error_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Кешовані токени окремо: провайдер тарифікує запис у кеш дорожче за
    # звичайний вхід, а читання — вдесятеро дешевше. Складені в одну
    # колонку, вони дали б у журналі витрат неправильне число.
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # NULL — «цінової бази немає», і це чесніше за вигадане число.
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pricing_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    run: Mapped[EnrichmentRun] = relationship(back_populates="attempts")

    __table_args__ = (UniqueConstraint("run_id", "number", name="uq_enrichment_attempt_number"),)
