import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any, TextIO

import structlog

from app.core.config import settings

# PSI приймає ключ лише як query-параметр, а httpx на INFO пише повний URL —
# без редагування ключ лягає у логи воркера й у `docker logs` відкритим текстом.
SECRET_QUERY = re.compile(
    r"([?&](?:key|api_key|apikey|access_token|token|password|secret)=)[^&\s\"']+",
    re.IGNORECASE,
)
# Paddle передає ключ заголовком, а не в адресі, тож шаблон вище його не
# бачить. httpx заголовків не пише, але виняток, трасування чи
# необережний `log.info(headers=...)` — пишуть, і одного разу досить.
SECRET_HEADER = re.compile(
    r"((?:Bearer|Basic)\s+)[A-Za-z0-9._\-+/=]{8,}",
    re.IGNORECASE,
)

# Ключі провайдерів мають упізнавані префікси. Це остання сітка: рядок,
# який проліз повз обидва шаблони вище, усе одно не має лягти в лог
# відкритим текстом.
SECRET_PREFIXED = re.compile(
    r"\b(?:pdl_(?:sdbx|live|ntfset|ntf|apikey)[A-Za-z0-9._\-]*|sk-[A-Za-z0-9._\-]{8,})"
)

REDACTED = r"\1***"


def redact(text: str) -> str:
    text = SECRET_QUERY.sub(REDACTED, text)
    text = SECRET_HEADER.sub(REDACTED, text)
    return SECRET_PREFIXED.sub("***", text)


class RedactSecrets(logging.Filter):
    """Вирізає секрети з будь-якого запису stdlib-логера, не лише з наших."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Без гейта на «=»: секрет буває і в заголовку `Bearer …`, і
        # голим префіксованим ключем, а в них знака рівності немає.
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def _redact_event(
    _logger: Any, _name: str, event: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Той самий запобіжник для structlog: секрет може бути й у нашому полі."""
    for key, value in event.items():
        if isinstance(value, str):
            event[key] = redact(value)
    return event


def _install_redaction() -> None:
    """Повісити фільтр на КОЖЕН логер, а не лише на кореневий.

    `RedactSecrets` обіцяє вирізати секрети «з будь-якого запису
    stdlib-логера, не лише з наших», і саме цієї обіцянки реалізація не
    виконувала. Фільтр вішався на обробники КОРЕНЕВОГО логера, а
    uvicorn заводить власний `uvicorn.access` із власним обробником і
    `propagate = False` — тобто його записи до кореня не доходять
    ніколи. А пише він саме те, чого не можна писати: повний рядок
    запиту разом із query.

    Наслідок був не теоретичний. Перевірка посилання відновлення — це
    `GET …/password/reset?token=…`, і токен лягав у журнал доступу
    відкритим текстом: ключ від акаунта, живий до першого використання,
    у файлі, який зазвичай переживає і сам токен, і кілька переїздів
    між сервісами збору логів.

    Фільтр вішається і на логер, і на його обробники: обробник
    перекриває дочірні записи, логер — ті, що йдуть повз обробник
    кореня.
    """
    redactor = RedactSecrets()
    names = ["", *logging.root.manager.loggerDict]
    for name in names:
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactSecrets) for f in logger.filters):
            logger.addFilter(redactor)
        for handler in logger.handlers:
            if not any(isinstance(f, RedactSecrets) for f in handler.filters):
                handler.addFilter(redactor)


def configure_logging(stream: TextIO | None = None) -> None:
    """stream=sys.stderr для CLI, який віддає JSON у stdout."""
    logging.basicConfig(
        format="%(message)s", stream=stream or sys.stdout, level=settings.log_level, force=True
    )
    _install_redaction()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _redact_event,
            structlog.dev.ConsoleRenderer()
            if settings.app_env == "local"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        # structlog пише через власну фабрику, а не через logging — без цього
        # рядок піде в stdout повз basicConfig і зіпсує машинний вивід.
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger()
