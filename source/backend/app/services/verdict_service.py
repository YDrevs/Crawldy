"""Вердикти людини по знахідках і зведення по чеках.

Зведення тут — єдине, заради чого варто збирати вердикти. Окремий
вердикт цікавий клієнту; проєкту цікава частка `wrong` по коду чека,
бо це перше в цьому проєкті число про якість детекції, яке не є нашою
власною гіпотезою.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.enums import AGAINST_THE_CHECK, Verdict
from app.models.audit import AuditIssue, IssueVerdict

# Скільки вердиктів по коду треба, щоб частка помилок щось означала.
# На двох відповідях 50% помилок — це одна незгода, а не властивість чека.
MIN_VERDICTS_TO_JUDGE = 5


@dataclass(slots=True)
class CheckFeedback:
    """Що люди сказали про один чек."""

    code: str
    total: int
    by_verdict: dict[str, int]

    @property
    def wrong_share(self) -> float:
        against = sum(self.by_verdict.get(v.value, 0) for v in AGAINST_THE_CHECK)
        return against / self.total if self.total else 0.0

    @property
    def is_meaningful(self) -> bool:
        """Чи достатньо відповідей, щоб частка щось значила."""
        return self.total >= MIN_VERDICTS_TO_JUDGE

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "total": self.total,
            "by_verdict": self.by_verdict,
            "wrong_share": round(self.wrong_share, 3),
            # Без цього прапорця перший же чек із двома вердиктами
            # опинився б угорі списку «найгірших».
            "enough_answers": self.is_meaningful,
        }


async def record(
    session: AsyncSession,
    issue_id: uuid.UUID,
    verdict: Verdict,
    *,
    note: str = "",
    author: str = "",
) -> IssueVerdict | None:
    """Записує вердикт, замінюючи попередній по цій знахідці.

    Думка може змінитися — тоді запис оновлюється, а не додається
    другий: потрібна нинішня відповідь, а не історія вагань.
    """
    issue = await session.get(AuditIssue, issue_id)
    if issue is None:
        return None

    existing = await session.scalar(
        select(IssueVerdict).where(IssueVerdict.issue_id == issue_id)
    )
    if existing is None:
        existing = IssueVerdict(
            id=uuid.uuid4(),
            issue_id=issue_id,
            audit_id=issue.audit_id,
            code=issue.code,
            msg=issue.msg_key or issue.code,
        )
        session.add(existing)
    existing.verdict = verdict
    existing.note = note[:2000]
    existing.author = author[:120]
    await session.commit()
    return existing


async def feedback_by_check(session: AsyncSession) -> list[CheckFeedback]:
    """Зведення по кодах чеків, найпроблемніші — першими.

    Порядок: спершу ті, де відповідей достатньо, і серед них — за
    часткою «такого немає». Чек із двома вердиктами не має обганяти чек
    із сорока лише тому, що одна з двох відповідей була незгодою.
    """
    stmt = select(
        IssueVerdict.code, IssueVerdict.verdict, func.count(IssueVerdict.id)
    ).group_by(IssueVerdict.code, IssueVerdict.verdict)
    rows = (await session.execute(stmt)).all()

    grouped: dict[str, dict[str, int]] = {}
    for code, verdict, count in rows:
        value = verdict.value if isinstance(verdict, Verdict) else str(verdict)
        grouped.setdefault(code, {})[value] = int(count)

    summary = [
        CheckFeedback(code=code, total=sum(counts.values()), by_verdict=counts)
        for code, counts in grouped.items()
    ]
    return sorted(summary, key=lambda f: (f.is_meaningful, f.wrong_share, f.total), reverse=True)


__all__ = ["MIN_VERDICTS_TO_JUDGE", "CheckFeedback", "feedback_by_check", "record"]
