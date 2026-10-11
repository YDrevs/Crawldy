"""Персистентність Actual AI Presence: прогони і спостереження.

Родини доказів розділені структурно: синтетичні спостереження живуть у
`presence_observations`; first-party телеметрія (P1) отримає ВЛАСНУ
таблицю з полями source/surface/metric_type/period/native value —
Google-івські покази й майкрософтівські цитати не нормалізуються в одну
метрику, тож і не діляться таблицею.

Ідентичність спостереження — (run, provider, prompt_id, run_index):
UNIQUE тримає «повторний запуск не платить двічі» на рівні бази, як
ідентичність збагачення.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.audit import JSONType


class PresenceRun(Base):
    __tablename__ = "presence_runs"
    __table_args__ = (
        # Один прогін на (організація, ключ ідемпотентності). NULL-ключі
        # унікальність не обмежують — внутрішні прогони без організації
        # та запити без ключа лишаються звичайними.
        UniqueConstraint(
            "organization_id", "idempotency_key",
            name="uq_presence_run_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    origin: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str] = mapped_column(String(255))
    brand_aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)
    prompt_set_version: Mapped[str] = mapped_column(String(32))
    # Точний набір промптів прогону: виконання читає ЗВІДСИ, а не
    # перегенеровує — зміна правил генерації після постановки в чергу
    # не може підмінити виміряне.
    prompts: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    # Знімок ефективної політики на момент запуску: історія знає, чим
    # саме міряли, навіть коли адмін-конфігурація давно інша.
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # Чим оплачено право на прогін: subscription (місячна квота) або
    # credit (куплена/грантована одиниця). Розрахунок — при
    # завершенні: достатнє покриття списує, недостатнє — повертає.
    entitlement_source: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    # Розрахунок відбувається РІВНО раз: повтор задачі чи докат
    # клітинок не сміє ні списати вдруге, ні повернути списане.
    entitlement_settled: Mapped[bool] = mapped_column(default=False)
    # Підсумок розрахунку: чи виявився прогін метрично придатним (тобто
    # чи списано право). None — ще не розраховано.
    deliverable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Ключ ідемпотентності подання: подвійний клік або повторений запит
    # з тим самим ключем знаходить той самий прогін і не резервує право
    # вдруге. Свідомий НОВИЙ запуск іде без ключа або з новим ключем.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations_total: Mapped[int] = mapped_column(Integer, default=0)
    observations_ok: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    observations: Mapped[list[PresenceObservation]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class PresenceObservation(Base):
    __tablename__ = "presence_observations"
    __table_args__ = (
        # Ідентичність клітинки включає режим: natural і explicit — різні
        # спостереження одного промпту, і повтор задачі не сміє злити їх.
        UniqueConstraint(
            "run_id", "provider", "prompt_id", "mode", "run_index",
            name="uq_presence_observation_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presence_runs.id", ondelete="CASCADE"),
        index=True,
    )
    evidence_family: Mapped[str] = mapped_column(String(16), default="synthetic")
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    tool_version: Mapped[str] = mapped_column(String(64), default="")
    prompt_id: Mapped[str] = mapped_column(String(64))
    prompt_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(16))
    segment: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8))
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    run_index: Mapped[int] = mapped_column(SmallInteger)
    # Режим вимірювання. Старі P0-рядки — natural: інших тоді не було.
    mode: Mapped[str] = mapped_column(
        String(16), default="natural", server_default="natural"
    )
    status: Mapped[str] = mapped_column(String(40))
    searched: Mapped[bool] = mapped_column(Boolean, default=False)
    # Точний надісланий текст: у explicit-режимі відрізняється від
    # prompt_text доданою інструкцією. Порожньо в старих рядках — там
    # надсилався сам prompt_text.
    sent_text: Mapped[str] = mapped_column(Text, default="")
    # Пошукові запити, які модель виконала, — коли провайдер їх віддає.
    search_queries: Mapped[list[str]] = mapped_column(JSONType, default=list)
    answer_excerpt: Mapped[str] = mapped_column(Text, default="")
    cited_urls: Mapped[list[str]] = mapped_column(JSONType, default=list)
    cited_domains: Mapped[list[str]] = mapped_column(JSONType, default=list)
    brand_mentioned: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain_cited: Mapped[bool] = mapped_column(Boolean, default=False)
    pages_cited: Mapped[list[str]] = mapped_column(JSONType, default=list)
    # Пряме посилання: власна адреса в ТЕКСТІ відповіді — не те саме, що
    # цитата провайдера, і твердження в метриках у нього окреме.
    domain_linked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    linked_urls: Mapped[list[str]] = mapped_column(JSONType, default=list)
    recommended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    observed_domains: Mapped[list[str]] = mapped_column(JSONType, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    searches: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    # Скільки повторів знадобилося цій клітинці й скільки вона тривала.
    retries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Версія правил тлумачення (normalize). Порожньо — рядок до n2.
    normalize_version: Mapped[str] = mapped_column(
        String(8), default="", server_default=""
    )
    # Сирий доказ — тимчасовий: політика утримання зануляє його після
    # спливу строку, нормалізований рядок лишається назавжди.
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped[PresenceRun] = relationship(back_populates="observations")


class PresenceAttempt(Base):
    """Довговічна резервація однієї платної спроби. Історія append-only.

    Рядок комітиться ДО мережевого виклику: падіння процесу між
    диспетчеризацією і персистенцією відповіді лишає DISPATCHED-рядок,
    який при резюме консервативно рахується за зарезервованим
    максимумом — «памʼятна резервація зникла разом із процесом» більше
    не існує як діра. Балансів тут немає: витрачене завжди виводиться
    сумою по станах, і жоден рядок не переписується, щоб баланс
    «зійшовся».
    """

    __tablename__ = "presence_attempts"
    __table_args__ = (
        # Повтор задачі воркера не сміє створити другий рядок тієї самої
        # спроби: ідентичність включає номер спроби.
        UniqueConstraint(
            "run_id", "provider", "prompt_id", "mode", "run_index",
            "attempt_no",
            name="uq_presence_attempt_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presence_runs.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32))
    prompt_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    run_index: Mapped[int] = mapped_column(SmallInteger)
    attempt_no: Mapped[int] = mapped_column(SmallInteger)
    # reserved | dispatched | settled | known_zero | unknown_cost |
    # released | cost_bound_violated
    state: Mapped[str] = mapped_column(String(24))
    # Гроші — NUMERIC: допуск порівнює точні величини, не float.
    reserved_max_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    # Знімок стель, проти яких резервувалась ця спроба. NULL для спроб
    # після скасування стель — величини, проти якої резервували, немає.
    provider_cap_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    total_cap_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    # Відбиток прейскуранта, яким рахувався максимум.
    pricing_version: Mapped[str] = mapped_column(String(16))
    provider_request_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(),
    )
