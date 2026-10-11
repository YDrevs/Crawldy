"""Міграції на справжньому PostgreSQL.

Фаза 4 — це production-схема, і кожна її ревізія має відповідати трьом
питанням: чи накочується з чистої бази, чи описує вона рівно те, що
описують моделі, і чи можна її відкотити. Досі на жодне з них не було
чим відповісти — тестів проти БД у проєкті не існувало.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND = Path(__file__).resolve().parents[2]

# Таблиці, які мусять існувати після `upgrade head`. Список перевіряє не
# схему, а те, що міграції справді виконались: порожня база з накатаним
# alembic_version і без таблиць виглядала б успішною.
CORE_TABLES = {
    "alembic_version",
    "audits",
    "audit_targets",
    "audit_pages",
    "audit_issues",
    "issue_verdicts",
    "report_links",
}


@pytest.mark.asyncio
async def test_upgrade_head_creates_the_schema(postgres_url: str):
    engine = create_async_engine(postgres_url)
    async with engine.connect() as conn:
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    await engine.dispose()

    missing = CORE_TABLES - tables
    assert not missing, f"після upgrade head бракує таблиць: {sorted(missing)}"


@pytest.mark.asyncio
async def test_models_and_migrations_do_not_disagree(postgres_url: str):
    """Autogenerate на свіжій базі має не знайти чого додати.

    Розбіжність означає, що модель змінили, а ревізію не написали — і
    наступний, хто підніме середовище з нуля, отримає іншу схему, ніж та,
    на якій усе працювало.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.core.db import Base
    from app.models import (  # noqa: F401
    audit,
    billing,
    identity,
    scheduling,
    sites,
    usage,
)

    engine = create_async_engine(postgres_url)

    def _diff(connection) -> list:
        context = MigrationContext.configure(connection)
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as conn:
        diff = await conn.run_sync(_diff)
    await engine.dispose()

    assert not diff, "моделі розійшлися з міграціями: " + "; ".join(str(d)[:120] for d in diff)


@pytest.mark.asyncio
async def test_every_revision_is_reachable_in_one_line(postgres_url: str):
    """Одна голова, без розгалужень.

    Дві голови означають, що дві гілки додали ревізію паралельно, і
    `upgrade head` стане неоднозначним. Дізнаватися про це на розгортанні
    дорожче, ніж тут.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    assert len(heads) == 1, f"у графі міграцій {len(heads)} голів: {heads}"


@pytest.mark.asyncio
async def test_the_frozen_scoring_columns_survived_the_schema(postgres_url: str):
    """Колонки, на яких тримається порівнянність історії.

    `versions` несе detector/scoring/config; `snapshot` дає перерахунок;
    `issue_variant` — семантичний ключ, на якому рахується стеля штрафу.
    Втратити будь-яку з них означає втратити здатність пояснити старий
    аудит через рік.
    """
    engine = create_async_engine(postgres_url)

    def _columns(connection, table: str) -> set[str]:
        return {c["name"] for c in inspect(connection).get_columns(table)}

    async with engine.connect() as conn:
        targets = await conn.run_sync(_columns, "audit_targets")
        issues = await conn.run_sync(_columns, "audit_issues")
    await engine.dispose()

    assert {"versions", "snapshot", "scores", "score_overall"} <= targets
    assert {"issue_variant", "code", "msg_key"} <= issues


@pytest.mark.asyncio
async def test_jsonb_is_really_jsonb(postgres_url: str):
    """Не косметика: на JSONB тримаються запити по версіях і опціях.

    Якщо колонка виявиться text, усе працюватиме до першого запиту з
    оператором `->>`, тобто до першого разу, коли історія спробує
    відфільтрувати аудити за версією скорингу.
    """
    engine = create_async_engine(postgres_url)
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'audit_targets' "
                "AND column_name IN ('versions', 'scores', 'snapshot', 'evidence')"
            )
        )
        types = dict(rows.all())
    await engine.dispose()

    assert types, "колонок не знайдено — схема не та, що очікується"
    assert set(types.values()) == {"jsonb"}, f"не JSONB: {types}"
