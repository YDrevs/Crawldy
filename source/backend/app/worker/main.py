from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import configure_logging, log
from app.worker.enrichment_task import run_enrichment_task
from app.worker.presence_task import run_presence_task
from app.worker.recovery_task import send_password_reset_task
from app.worker.retention_job import sweep
from app.worker.scheduler import tick
from app.worker.tasks import run_audit_task


async def startup(_ctx: dict[str, Any]) -> None:
    configure_logging()
    await _check_renderer()


async def _check_renderer() -> None:
    """Чи є браузер, і скаржитись голосно, якщо ні.

    Аудит без рендеру не падає — він стає partial і чесно пише причину в
    звіт. Саме тому дефект може прожити довго: у контейнері стояв пакет
    playwright без виконуваного файла, і вся фаза 2 мовчки не працювала,
    поки хтось не прочитав слово «partial» у звіті клієнта.

    Перевірка на старті переносить це з кожного аудиту в один рядок логу
    при запуску воркера, де його видно одразу.
    """
    if not settings.render_enabled:
        log.info("renderer_disabled", reason="вимкнено налаштуванням")
        return
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            await browser.close()
    except Exception as exc:  # noqa: BLE001 — воркер має стартувати попри це
        log.warning(
            "renderer_unavailable",
            error=str(exc)[:200],
            hint="playwright install --with-deps chromium",
            consequence="аудити будуть partial: без SSR-дельти, third-party і mobile-gap",
        )
        return
    log.info("renderer_ready")


class WorkerSettings:
    # Збагачення зареєстроване як завдання, але ніхто його не ставить:
    # продуктових шляхів, що звертаються до черги збагачення, немає до
    # затвердження бенчмарку. Реєстрація тут — щоб внутрішній тригер
    # мав куди поставити задачу, а не щоб щось запускалося саме.
    functions: ClassVar[list[Any]] = [
        run_audit_task,
        run_enrichment_task,
        run_presence_task,
        send_password_reset_task,
    ]
    # Хвилинний крок планувальника. Частіше немає сенсу: найдрібніша
    # одиниця розкладу — хвилина, і перевіряти вдвічі частіше означає
    # вдвічі більше порожніх запитів у базу.
    #
    # Кілька воркерів із цим кроном безпечні: оренда в базі не дасть
    # двом узяти той самий розклад.
    cron_jobs: ClassVar[list[Any]] = [
        cron(tick, minute=set(range(60)), run_at_startup=False, max_tries=1),
        # Чистка раз на добу о третій ночі. Година вибрана не для
        # краси: це найдешевший час і найдовше вікно до ранкових
        # запланованих аудитів, які змагалися б за ту саму базу.
        #
        # `max_tries=1` навмисно: прохід порційний і ідемпотентний, тож
        # невдалий просто повториться завтра. Повтор того самого проходу
        # нічого не додає, а на заблокованих рядках лише заважає.
        cron(sweep, hour={3}, minute={0}, run_at_startup=False, max_tries=1),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = settings.audit_timeout_s
    keep_result = 3600
    max_tries = 2
