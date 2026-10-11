import asyncio
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import audits as application
from app.application import retries
from app.application.failures import classify
from app.audit.enums import AuditStatus
from app.audit.orchestrator import AuditOptions, ProgressReporter, run_audit
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import log
from app.core.run_enums import FailureClass
from app.models.audit import Audit
from app.scheduling import service as schedules
from app.services import audit_service
from app.worker.queue import enqueue_audit

# Скільки цілей аудитуємо одночасно. Кожна тягне власний краул, тож
# паралелити всі одразу — це N×concurrency з'єднань і ризик впертися
# в audit_timeout_s на великому списку.
TARGET_CONCURRENCY = 2


async def run_audit_task(_ctx: dict, audit_id: str, attempt: int = 1) -> dict:
    """Одна **спроба** виконати аудит.

    Номер спроби приходить у завданні, а не рахується тут: черга може
    доставити те саме повідомлення двічі, і обидві доставки мусять
    описувати одну спробу. Дефолт — для завдань, поставлених до появи
    повторів; вони всі перші.

    Резерв квоти закривається тільки на **остаточному** результаті. Поки
    попереду ще спроба, доля резерву не вирішена: списати за невдачу, за
    яку самі ж вирішили спробувати ще раз, означало б взяти гроші двічі
    за одну роботу.
    """
    aid = uuid.UUID(audit_id)
    structlog.contextvars.bind_contextvars(audit_id=audit_id, attempt=attempt)
    try:
        async with SessionLocal() as session:
            audit = await audit_service.get_audit(session, aid)
            if audit is None:
                return {"status": "missing"}
            if audit.status.is_terminal:
                # Аудит уже має остаточний результат: передоставка або
                # гонка двох воркерів. Перезапустити його означало б
                # переписати історичний факт.
                log.info("audit_already_terminal", status=audit.status.value)
                return {"status": audit.status.value, "repeat": True}
            options_raw = audit.options
            targets = [(t.id, t.url) for t in sorted(audit.targets, key=lambda t: t.position)]
            await audit_service.begin_attempt(session, aid, attempt)
            await audit_service.mark_running(session, aid)

        if not targets:
            await _terminal_failure(
                aid, attempt, "аудит без жодної цілі", FailureClass.INTERNAL_ERROR
            )
            return {"status": "failed", "error": "no targets"}

        log.info("audit_started", targets=len(targets))
        options = AuditOptions.from_dict(options_raw)
        semaphore = asyncio.Semaphore(TARGET_CONCURRENCY)
        # Показник ходу — лише для аудиту з ОДНІЄЮ ціллю. При кількох
        # краули йдуть паралельно, і одне число описувало б то одну ціль,
        # то іншу: порожнеча тут чесніша за неоднозначність.
        watcher = _progress_watcher(aid) if len(targets) == 1 else None
        results = await asyncio.gather(
            *(
                _run_target(semaphore, tid, url, options, on_progress=watcher)
                for tid, url in targets
            )
        )

        async with SessionLocal() as session:
            await audit_service.finalize_audit(session, aid)
            audit = await audit_service.get_audit(session, aid)
            status = audit.status if audit else AuditStatus.FAILED
            score = audit.score_overall if audit else None
            rolled_up = audit.failure_class if audit else None
            summary = (audit.error if audit else "") or "жодна ціль не дала результату"
            await session.commit()

        if status is AuditStatus.FAILED:
            # Жодна ціль не дійшла до результату. Це та сама невдача, що й
            # виняток нижче, лише спіймана на рівні цілі — і рішення про
            # квоту й повтор мусить бути те саме. Поки цієї гілки не було,
            # аудит, який упав через наш власний код у всіх цілях, ішов
            # успішним шляхом: клієнту списувалось, повтору не було.
            failure = rolled_up or FailureClass.INTERNAL_ERROR
            decision = retries.decide(failure=failure, attempts=attempt)
            log.warning(
                "audit_all_targets_failed",
                failure=failure.value,
                retry=decision.retry,
                reason=decision.reason_key,
            )
            if decision.retry and await _requeue(aid, attempt, summary, failure, decision):
                return {
                    "status": "queued",
                    "retry_in_s": decision.delay_seconds,
                    "attempt": attempt,
                }
            await _terminal_failure(aid, attempt, summary, failure, decision=decision)
            return {"status": "failed", "error": summary}

        async with SessionLocal() as session:
            audit = await audit_service.get_audit(session, aid)
            if audit is not None:
                # Резерв стає остаточним списанням. Аудит, який дійшов до
                # кінця, — це виконана робота, навіть якщо сайт віддав
                # 403 або не мав вмісту: відповідь чесна, і вона коштувала.
                await application.settle_quota(session, audit)
            await audit_service.finish_attempt(session, aid, attempt, status=status)
            await _note_schedule(session, aid, ok=True)
            await session.commit()

        done = sum(1 for ok in results if ok)
        log.info(
            "audit_finished", status=status.value, score=score, targets_ok=f"{done}/{len(targets)}"
        )
        return {
            "status": status.value,
            "score": score,
            "targets": len(targets),
            "targets_ok": done,
        }
    except Exception as exc:  # noqa: BLE001
        failure = classify(exc)
        message = f"{type(exc).__name__}: {exc}"
        decision = retries.decide(failure=failure, attempts=attempt)
        log.error(
            "audit_attempt_failed",
            error=message,
            failure=failure.value,
            retry=decision.retry,
            reason=decision.reason_key,
            exc_info=True,
        )
        if decision.retry and await _requeue(aid, attempt, message, failure, decision):
            return {"status": "queued", "retry_in_s": decision.delay_seconds, "attempt": attempt}
        await _terminal_failure(aid, attempt, message, failure, decision=decision)
        return {"status": "failed", "error": message}
    finally:
        structlog.contextvars.clear_contextvars()


def _progress_watcher(audit_id: uuid.UUID) -> ProgressReporter:
    """Слухач ходу, який пише в базу власною короткою сесією.

    Власною саме тому, що аудит триває хвилини: тримати транзакцію
    відкритою весь цей час заради лічильника означало б платити за
    показник ціною з'єднання.
    """

    async def report(stage: str, read: int, known: int) -> None:
        async with SessionLocal() as session:
            await audit_service.record_progress(
                session, audit_id, stage=stage, read=read, known=known
            )

    return report


async def _run_target(
    semaphore: asyncio.Semaphore,
    target_id: uuid.UUID,
    url: str,
    options: AuditOptions,
    *,
    on_progress: ProgressReporter | None = None,
) -> bool:
    """Одна ціль. Її падіння не має зачіпати решту — аудит стане partial."""
    async with semaphore:
        try:
            async with SessionLocal() as session:
                await audit_service.mark_target_running(session, target_id)

            log.info("target_started", url=url)
            outcome = await asyncio.wait_for(
                run_audit(url, options, on_progress=on_progress),
                timeout=settings.audit_timeout_s,
            )
            async with SessionLocal() as session:
                await audit_service.persist_outcome(session, target_id, outcome)
            log.info("target_finished", url=url, score=outcome.overall)
            return True
        except Exception as exc:  # noqa: BLE001
            reason = "перевищено таймаут" if isinstance(exc, TimeoutError) else str(exc)
            failure = classify(exc)
            log.warning("target_failed", url=url, error=reason, failure=failure.value)
            async with SessionLocal() as session:
                await audit_service.mark_target_failed(
                    session, target_id, reason, failure=failure
                )
            return False


async def _requeue(
    audit_id: uuid.UUID,
    attempt: int,
    error: str,
    failure: FailureClass,
    decision: retries.RetryDecision,
) -> bool:
    """Поставити наступну спробу. Повертає, чи вдалося.

    Якщо не вдалося — черга недоступна, — брехати про заплановану спробу
    не можна: аудит лишився б `queued` назавжди. Тоді викликач робить
    невдачу остаточною, і квота повертається: це наша інфраструктура.
    """
    try:
        await enqueue_audit(audit_id, attempt=attempt + 1, delay_s=decision.delay_seconds)
    except Exception as exc:  # noqa: BLE001
        log.error("retry_enqueue_failed", error=str(exc))
        return False

    async with SessionLocal() as session:
        await audit_service.finish_attempt(
            session,
            audit_id,
            attempt,
            status=AuditStatus.FAILED,
            failure=failure,
            error=error,
            retry_decision_key=decision.reason_key,
            retry_decision_params={**decision.reason_params, "in_s": decision.delay_seconds},
        )
        await audit_service.mark_requeued(session, audit_id, error)
        await session.commit()
    log.info("audit_retry_scheduled", in_s=decision.delay_seconds, next_attempt=attempt + 1)
    return True


async def _terminal_failure(
    audit_id: uuid.UUID,
    attempt: int,
    error: str,
    failure: FailureClass,
    *,
    decision: retries.RetryDecision | None = None,
) -> None:
    """Остаточна невдача: закрити спробу, запуск, резерв і розклад.

    Клас невдачі визначається типом винятку, а не текстом: від нього
    залежать гроші клієнта, і правило, зав'язане на формулювання, тихо
    перестане діяти при першому переписуванні повідомлення.
    """
    why = decision.reason_key if decision is not None else "notice.retry.not_attempted"
    why_params = decision.reason_params if decision is not None else {}
    async with SessionLocal() as session:
        await audit_service.finish_attempt(
            session,
            audit_id,
            attempt,
            status=AuditStatus.FAILED,
            failure=failure,
            error=error,
            retry_decision_key=why,
            retry_decision_params=why_params,
        )
        await audit_service.mark_failed(session, audit_id, error, failure=failure)
        audit = await audit_service.get_audit(session, audit_id)
        if audit is not None:
            state = await application.settle_quota(session, audit, failure=failure)
            log.info("quota_settled", state=state.value, failure=failure.value)
        await _note_schedule(session, audit_id, ok=False, reason=error)
        await session.commit()


async def _note_schedule(
    session: AsyncSession, audit_id: uuid.UUID, *, ok: bool, reason: str = ""
) -> None:
    """Передати розкладу, чим скінчився його запуск.

    Ручний аудит розкладу не має — тоді просто нема кому повідомляти.
    """
    audit = await session.get(Audit, audit_id)
    if audit is None or audit.schedule_id is None:
        return
    await schedules.note_outcome(
        session, schedule_id=audit.schedule_id, ok=ok, reason=reason
    )
