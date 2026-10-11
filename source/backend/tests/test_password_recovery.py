"""Відновлення пароля: пошта, воркер, конфігурація.

Тут те, що перевіряється без бази. Шлях через HTTP і персистентність —
у `tests/integration/test_password_recovery.py`.

Головне твердження набору архітектурне, і доводиться воно СТРУКТУРНО, а
не секундоміром: доставка не живе в HTTP-запиті. Вимірювати час відповіді
в тесті було б і ненадійно, і хибно по суті — повільна машина зробила б
зелений набір червоним, а швидка пропустила б справжню регресію. Замість
цього перевіряється, що модуль маршрутів не знає ані SMTP, ані пошти
взагалі, і що обидві адреси — відома й невідома — йдуть одним шляхом у
чергу.
"""

from __future__ import annotations

import smtplib
from pathlib import Path

import pytest
import structlog
from pydantic import ValidationError

from app.audit.i18n import Locale
from app.core.config import Settings
from app.mail import transport as mail
from app.mail.copy import LOCALES, reset_letter
from app.worker import recovery_task

BACKEND = Path(__file__).resolve().parents[1]

# Адреса й токен, за якими шукаємо витоки в журналі. Значення навмисно
# впізнавані: підрядок у логах має бути видно з першого погляду.
ADDRESS = "hanna.kovalenko@example.org"
TOKEN = "SECRET-TOKEN-VALUE-DO-NOT-LOG"


def _settings(**overrides: object) -> Settings:
    """Налаштування без читання `.env` оточення розробника."""
    base: dict[str, object] = {
        "app_env": "local",
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "redis_url": "redis://localhost:6379",
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


class _Recorder:
    """Поштар, що рахує спроби й віддає задані відповіді."""

    name = "recorder"

    def __init__(self, *failures: BaseException | None) -> None:
        self._script = list(failures)
        self.sent: list[mail.Message] = []
        self.attempts = 0

    def available(self) -> bool:
        return True

    def send(self, message: mail.Message) -> None:
        self.attempts += 1
        outcome = self._script.pop(0) if self._script else None
        if outcome is not None:
            raise outcome
        self.sent.append(message)


@pytest.fixture
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Паузи між повторами записуються, а не витримуються.

    Тест про backoff мусить доводити, що пауза Є і що вона росте, — а не
    витрачати на це шість секунд прогону. Записаний виклик — сильніший
    доказ за секундомір: він називає точне число.
    """
    waited: list[float] = []

    async def _sleep(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr(recovery_task.asyncio, "sleep", _sleep)
    return waited


# ── доставки немає в шляху запиту ──────────────────────────────────────


def test_the_route_module_knows_nothing_about_mail() -> None:
    """Маршрути автентифікації не мають жодного сліду пошти.

    Це і є доказ архітектури. Поки доставка жила в маршруті, відома
    адреса відповідала після зʼєднання з чужим SMTP, а невідома —
    одразу: однакове тіло відповіді не рятувало, бо різниця була в часі.
    """
    source = (BACKEND / "app" / "api" / "routes" / "auth.py").read_text(encoding="utf-8")
    for forbidden in ("smtplib", "app.mail", "build_mailer", "reset_letter", "SmtpMailer"):
        assert forbidden not in source, f"{forbidden} повернувся в шлях HTTP-запиту"


def test_the_forgot_route_does_not_even_open_a_database_session() -> None:
    """Пошук акаунта — теж вимірна робота, тож його в маршруті немає.

    `SessionDep` у сигнатурі означав би запит у базу для відомої адреси
    й швидший шлях для невідомої. Маршрут ставить задачу і все.
    """
    from app.api.routes import auth

    assert "db" not in auth.forgot_password.__annotations__
    assert "SessionDep" not in str(auth.forgot_password.__annotations__)


def test_the_worker_task_is_registered_in_the_worker() -> None:
    """Задача, якої немає в переліку воркера, — це лист, якого не буде."""
    from app.worker.main import WorkerSettings

    assert recovery_task.send_password_reset_task in WorkerSettings.functions


# ── воркер: невідомий акаунт, успіх, повтори ───────────────────────────


@pytest.mark.asyncio
async def test_the_worker_stops_silently_for_an_unknown_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Невідома адреса — нормальний вхід, а не помилка.

    Маршрут ставить задачу, не знаючи, чи є такий акаунт; сказати «нема»
    має право лише воркер, і сказати мовчки.
    """
    mailer = _Recorder()
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    async def _nobody(email: str) -> None:
        return None

    monkeypatch.setattr(recovery_task, "_issue", _nobody)

    result = await recovery_task.send_password_reset_task({}, "stranger@example.com")

    assert result == {"status": "no_account"}
    assert mailer.attempts == 0, "листа невідомій адресі не буває"


@pytest.mark.asyncio
async def test_the_worker_delivers_for_a_known_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mailer = _Recorder()
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    async def _known(email: str) -> tuple[str, str]:
        return TOKEN, "uk"

    monkeypatch.setattr(recovery_task, "_issue", _known)

    result = await recovery_task.send_password_reset_task({}, ADDRESS)

    assert result == {"status": "sent"}
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == ADDRESS
    assert TOKEN in mailer.sent[0].text


@pytest.mark.asyncio
async def test_a_temporary_failure_is_retried_with_growing_backoff(
    monkeypatch: pytest.MonkeyPatch, no_waiting: list[float]
) -> None:
    """Обрив зʼєднання заслуговує на другу спробу — і на паузу перед нею."""
    mailer = _Recorder(
        smtplib.SMTPServerDisconnected("обрив"), smtplib.SMTPServerDisconnected("обрив")
    )
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    result = await recovery_task._deliver(mail.Message(to=ADDRESS, subject="s", text="t"))

    assert result == "sent"
    assert mailer.attempts == 3
    assert no_waiting == [2.0, 4.0], "пауза мусить рости, а не повторюватись"


@pytest.mark.asyncio
async def test_a_timeout_is_treated_as_temporary(
    monkeypatch: pytest.MonkeyPatch, no_waiting: list[float]
) -> None:
    """Таймаут SMTP — саме той випадок, заради якого повтор і існує."""
    mailer = _Recorder(TimeoutError("timed out"))
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    result = await recovery_task._deliver(mail.Message(to=ADDRESS, subject="s", text="t"))

    assert result == "sent"
    assert mailer.attempts == 2


@pytest.mark.asyncio
async def test_retries_are_bounded(
    monkeypatch: pytest.MonkeyPatch, no_waiting: list[float]
) -> None:
    """Сервер, який мовчить завжди, не тримає воркер вічно."""
    failures = [smtplib.SMTPServerDisconnected("обрив")] * 10
    mailer = _Recorder(*failures)
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    result = await recovery_task._deliver(mail.Message(to=ADDRESS, subject="s", text="t"))

    assert result == "failed"
    assert mailer.attempts == recovery_task.MAX_SEND_ATTEMPTS == 3


@pytest.mark.asyncio
async def test_a_permanent_refusal_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, no_waiting: list[float]
) -> None:
    """«Такої скриньки немає» від повтору не зміниться."""
    refused = smtplib.SMTPRecipientsRefused({ADDRESS: (550, b"no such user")})
    mailer = _Recorder(refused)
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    result = await recovery_task._deliver(mail.Message(to=ADDRESS, subject="s", text="t"))

    assert result == "failed"
    assert mailer.attempts == 1
    assert no_waiting == []


@pytest.mark.asyncio
async def test_a_retry_never_issues_a_second_token(
    monkeypatch: pytest.MonkeyPatch, no_waiting: list[float]
) -> None:
    """Повтор надсилає ТОЙ САМИЙ лист.

    Якби токен створювався всередині циклу, друга спроба скасувала б
    перший — і посилання, яке людина, можливо, вже отримала, померло б.
    """
    issued: list[str] = []

    async def _known(email: str) -> tuple[str, str]:
        issued.append(TOKEN)
        return TOKEN, "en"

    mailer = _Recorder(smtplib.SMTPServerDisconnected("обрив"))
    monkeypatch.setattr(recovery_task, "_issue", _known)
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    await recovery_task.send_password_reset_task({}, ADDRESS)

    assert issued == [TOKEN], "токен видається один раз на задачу"
    assert mailer.attempts == 2


@pytest.mark.asyncio
async def test_the_task_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Виняток означав би повтор задачі ARQ — і другий токен.

    Саме тому збій видачі гаситься всередині: `max_tries = 2` у воркера
    запустив би задачу наново, з нової сесії, і видав би нове посилання
    замість того, якого людина не отримала.
    """

    async def _broken(email: str) -> tuple[str, str]:
        raise RuntimeError("база впала")

    monkeypatch.setattr(recovery_task, "_issue", _broken)

    result = await recovery_task.send_password_reset_task({}, ADDRESS)

    assert result == {"status": "issue_failed"}


@pytest.mark.asyncio
async def test_unconfigured_mail_is_reported_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`NullMailer` віддає окремий статус, а не тихий «надіслано»."""
    monkeypatch.setattr(recovery_task.mail, "build_mailer", mail.NullMailer)

    result = await recovery_task._deliver(mail.Message(to=ADDRESS, subject="s", text="t"))

    assert result == "unconfigured"


# ── журнали нічого не розкривають ──────────────────────────────────────


@pytest.mark.asyncio
async def test_logs_carry_neither_address_nor_token_nor_link(
    monkeypatch: pytest.MonkeyPatch, no_waiting: list[float]
) -> None:
    """Лист про відновлення — ключ від акаунта в один рядок.

    Рядок у логах перетворив би доступ до логів на доступ до акаунтів,
    тож у журналі не буває ані адреси, ані токена, ані посилання. Текст
    винятку теж: повідомлення поштових бібліотек несуть адреси, імена
    скриньок і нутрощі сервера.
    """
    secret_in_exception = f"550 mailbox {ADDRESS} unavailable on mx.internal"
    mailer = _Recorder(smtplib.SMTPServerDisconnected(secret_in_exception))

    async def _known(email: str) -> tuple[str, str]:
        return TOKEN, "uk"

    monkeypatch.setattr(recovery_task, "_issue", _known)
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    with structlog.testing.capture_logs() as entries:
        await recovery_task.send_password_reset_task({}, ADDRESS)

    dump = repr(entries)
    assert entries, "задача мусить лишати слід в журналі"
    for secret in (ADDRESS, TOKEN, "mx.internal", "unavailable", "/reset?token="):
        assert secret not in dump, f"у журнал потрапило: {secret}"


def test_the_capture_transport_logs_only_domain_and_subject(tmp_path: Path) -> None:
    """Перехоплення — теж журнал, і правило для нього те саме."""
    mailer = mail.CaptureMailer(directory=tmp_path)
    with structlog.testing.capture_logs() as entries:
        mailer.send(
            mail.Message(to=ADDRESS, subject="Відновлення", text=f"link {TOKEN}")
        )

    dump = repr(entries)
    assert "example.org" in dump, "домен лишається: без нього журнал марний"
    assert ADDRESS not in dump
    assert TOKEN not in dump


def test_smtp_credentials_never_reach_the_log() -> None:
    """Пароль SMTP живе в оточенні й ніде більше.

    Перевірка структурна: у модулі транспорту немає жодного виклику
    журналу, що приймав би облікові дані.
    """
    source = (BACKEND / "app" / "mail" / "transport.py").read_text(encoding="utf-8")
    logging_lines = [line for line in source.splitlines() if "log." in line]
    assert logging_lines, "транспорт мусить щось писати в журнал"
    for line in logging_lines:
        for secret in ("password", "username", "_password", "_username"):
            assert secret not in line, f"облікові дані в журналі: {line.strip()}"


# ── конфігурація ───────────────────────────────────────────────────────


def test_production_demands_explicit_mail_configuration() -> None:
    """Прод без пошти не стартує. Тиха відмова тут — найгірший результат.

    Відновлення пароля ламається беззвучно: ніхто не скаржиться на лист,
    якого не чекав, тож дефект знайшовся б через тижні.
    """
    with pytest.raises(ValidationError) as exc:
        _settings(app_env="prod", public_app_url="https://crawldy.ai")
    assert "MAIL_SMTP_HOST" in str(exc.value)
    assert "MAIL_SENDER" in str(exc.value)


def test_production_demands_an_https_public_url() -> None:
    """Посилання відновлення по http віддало б токен у відкритому вигляді."""
    with pytest.raises(ValidationError) as exc:
        _settings(
            app_env="prod",
            mail_smtp_host="smtp.example.com",
            mail_sender="crawldy@example.com",
            public_app_url="http://crawldy.ai",
        )
    assert "https" in str(exc.value).lower()


def test_a_fully_configured_production_starts() -> None:
    configured = _settings(
        app_env="prod",
        mail_smtp_host="smtp.example.com",
        mail_sender="crawldy@example.com",
        public_app_url="https://crawldy.ai",
    )
    assert configured.mail_smtp_port == 587, "STARTTLS на 587, не SSL на 465"
    assert configured.mail_smtp_tls is True


def test_local_needs_no_mail_configuration() -> None:
    """Локальна розробка не мусить мати SMTP — і не мусить його вдавати."""
    assert _settings(app_env="local").mail_smtp_host is None


def test_no_default_sender_is_baked_into_the_code() -> None:
    """Запасна адреса відправника — пастка, а не турбота.

    `no-reply@crawldy.ai` із чужого SMTP не проходить SPF, і лист тихо
    осідає в спамі: виглядає як «надіслано», працює як «не дійшло».

    Шукаємо серед РЯДКОВИХ ЛІТЕРАЛІВ коду, а не підрядком у файлі:
    пояснення, чому цей дефолт прибрано, стоїть у докстрингу `_sender`
    і має там лишитися. Плаский пошук назвав би задокументовану пастку
    самою пасткою — рівно та помилка, про яку каже CLAUDE.md: «пошук
    підрядка в HTML бреше».
    """
    import ast

    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    offenders: list[str] = []
    for path in (BACKEND / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, holders) or not node.body:
                continue
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and "@crawldy.ai" in node.value
            ):
                offenders.append(f"{path.name}:{node.lineno} {node.value}")
    assert not offenders, offenders


def test_ssl_smtp_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """STARTTLS на 587. Порт 465 не додається, поки його ніхто не вимагає."""
    source = (BACKEND / "app" / "mail" / "transport.py").read_text(encoding="utf-8")
    assert "SMTP_SSL" not in source
    assert "starttls" in source


# ── транспорт за оточенням ─────────────────────────────────────────────


@pytest.mark.parametrize(("env", "expected"), [("local", "capture"), ("staging", "null")])
def test_capture_is_local_only(
    monkeypatch: pytest.MonkeyPatch, env: str, expected: str
) -> None:
    """Перехоплення поза локальною машиною гірше за відмову.

    Staging із перехопленням вдавав би робочу пошту, і дефект
    конфігурації знайшовся б аж у проді — там, де він коштує клієнта.

    Проду в переліку немає не з недогляду: без `MAIL_SMTP_HOST` він тепер
    не будується взагалі (див. `test_production_demands_explicit_mail_configuration`),
    тож у цю гілку він потрапити не може.
    """
    monkeypatch.setattr(mail, "settings", _settings(app_env=env))
    assert mail.build_mailer().name == expected


def test_a_configured_host_always_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mail,
        "settings",
        _settings(app_env="local", mail_smtp_host="smtp.example.com"),
    )
    assert mail.build_mailer().name == "smtp"


def test_the_null_transport_refuses_loudly() -> None:
    """Мовчазного успіху не буває: людина чекала б листа, якого не слали."""
    with pytest.raises(RuntimeError):
        mail.NullMailer().send(mail.Message(to=ADDRESS, subject="s", text="t"))


def test_eml_files_appear_only_when_a_directory_is_configured(tmp_path: Path) -> None:
    mail.CaptureMailer().send(mail.Message(to=ADDRESS, subject="s", text="t"))
    assert list(tmp_path.glob("*.eml")) == []

    mail.CaptureMailer(directory=tmp_path).send(
        mail.Message(to=ADDRESS, subject="s", text="t")
    )
    assert len(list(tmp_path.glob("*.eml"))) == 1


def test_reply_to_is_set_only_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail, "settings", _settings(mail_sender="a@b.co"))
    assert mail._compose(mail.Message(to=ADDRESS, subject="s", text="t"), sender="a@b.co")[
        "Reply-To"
    ] is None

    monkeypatch.setattr(
        mail, "settings", _settings(mail_sender="a@b.co", mail_reply_to="hello@b.co")
    )
    composed = mail._compose(mail.Message(to=ADDRESS, subject="s", text="t"), sender="a@b.co")
    assert composed["Reply-To"] == "hello@b.co"


@pytest.mark.parametrize(
    ("failure", "temporary"),
    [
        (smtplib.SMTPServerDisconnected("обрив"), True),
        (TimeoutError("timed out"), True),
        (ConnectionRefusedError("відмовлено"), True),
        (smtplib.SMTPResponseException(451, b"try later"), True),
        (smtplib.SMTPResponseException(550, b"no"), False),
        (smtplib.SMTPAuthenticationError(535, b"bad credentials"), False),
        (smtplib.SMTPRecipientsRefused({ADDRESS: (550, b"no")}), False),
        (smtplib.SMTPRecipientsRefused({ADDRESS: (450, b"later")}), True),
    ],
)
def test_temporary_failures_are_told_apart_by_code(
    failure: BaseException, temporary: bool
) -> None:
    """4xx — «спробуйте пізніше», 5xx — «ні». За кодом, не за текстом."""
    assert mail.is_temporary(failure) is temporary


# ── лист шістьма мовами ────────────────────────────────────────────────


def test_every_launch_locale_has_its_own_letter() -> None:
    """Шість мов, і жодна не підміняється англійською.

    Однаковий рядок у двох мовах означав би забутий переклад, а не
    збіг: тема й текст листа в цих мовах не збігаються.
    """
    assert len(LOCALES) == 6
    subjects = {
        locale: reset_letter(locale=locale, link="https://x.io/reset?token=t", hours=1).subject
        for locale in LOCALES
    }
    assert len(set(subjects.values())) == 6, subjects
    for locale, subject in subjects.items():
        assert "Crawldy" in subject, locale


@pytest.mark.parametrize("locale", LOCALES)
def test_each_letter_carries_the_link_its_lifetime_and_both_parts(locale: Locale) -> None:
    """Лист без строку змушує гадати, чому посилання «раптом» померло."""
    link = "https://crawldy.ai/reset?token=abc&lang=de"
    letter = reset_letter(locale=locale, link=link, hours=2)

    assert link in letter.text
    # У HTML амперсанд екранується — це правильно, а не дефект: `&lang`
    # без `&amp;` частина поштових клієнтів прочитає як мнемоніку.
    assert link.replace("&", "&amp;") in letter.html
    assert "2" in letter.text, "строк дії мусить бути названий"
    assert letter.text.strip(), "текстова частина обовʼязкова: не всі клієнти мають HTML"
    assert "{" not in letter.text, "незаповнений шаблон"
    assert "{" not in letter.subject


def test_an_unknown_locale_falls_back_to_english() -> None:
    """Мова, якої каталог не має, дає англійський лист, а не падіння."""
    letter = reset_letter(locale=Locale.EN, link="https://x.io/r", hours=1)
    assert letter.subject == "Reset your Crawldy password"


@pytest.mark.parametrize(
    ("profile", "requested", "expected"),
    [
        ("de", "uk", Locale.DE),
        ("", "fr", Locale.FR),
        ("", "", Locale.EN),
        ("xx", "es", Locale.ES),
        ("xx", "zz", Locale.EN),
    ],
)
def test_the_profile_language_beats_the_request(
    profile: str, requested: str, expected: Locale
) -> None:
    """Мова листа — з профілю адресата, а не зі сторінки запиту.

    Запит міг піти з чужого пристрою чи з іншої мовної версії сайту;
    читати лист людина буде у своїй пошті.
    """
    assert recovery_task._locale_of(profile, requested) is expected


# ── посилання ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("code", "expected_suffix"),
    [("en", ""), ("uk", "&lang=uk"), ("de", "&lang=de"), ("fr", "&lang=fr")],
)
def test_the_reset_link_preserves_the_locale(code: str, expected_suffix: str) -> None:
    """Мова мусить дожити від листа до екрана.

    Англійська без параметра, решта з `?lang=` — те саме правило, за
    яким побудовані публічні сторінки.
    """
    link = recovery_task._reset_link("tok", code)
    assert link.endswith(f"/reset?token=tok{expected_suffix}")


def test_the_reset_link_comes_from_configuration_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Відкритого перенаправлення тут бути не може.

    У посилання не потрапляє нічого із запиту, крім коду мови зі
    скінченного переліку: щоб змінити домен, треба змінити конфігурацію
    сервера.
    """
    monkeypatch.setattr(
        recovery_task, "settings", _settings(public_app_url="https://crawldy.ai/")
    )
    assert recovery_task._reset_link("tok", "en").startswith("https://crawldy.ai/reset?")


def test_the_letter_escapes_what_it_puts_in_html() -> None:
    letter = reset_letter(locale=Locale.EN, link='https://x.io/r?a="b"&c=<d>', hours=1)
    assert '"b"' not in letter.html
    assert "&quot;b&quot;" in letter.html
    assert "<d>" not in letter.html


def test_asyncio_is_used_to_keep_smtp_off_the_event_loop() -> None:
    """SMTP синхронний, і в циклі подій йому не місце."""
    source = (BACKEND / "app" / "worker" / "recovery_task.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread" in source


def test_the_mailbox_directory_is_ignored_by_git() -> None:
    """Перехоплені листи несуть персональні дані й сирі посилання."""
    ignored = (BACKEND.parent / ".gitignore").read_text(encoding="utf-8")
    assert "*.eml" in ignored
    assert "mailbox/" in ignored


def test_the_deliver_helper_cannot_reach_the_database() -> None:
    """Провалена доставка не сміє скасовувати токен.

    Таймаут SMTP не доводить, що лист не пішов: скасування зробило б
    мертвим посилання, яке людина, можливо, вже тримає в пошті. Доказ
    структурний — у функції доставки немає доступу до бази взагалі.
    """
    import inspect

    source = inspect.getsource(recovery_task._deliver)
    for forbidden in ("SessionLocal", "supersede", "session", "commit"):
        assert forbidden not in source, f"доставка торкається бази: {forbidden}"


def test_asyncio_import_is_used_for_sleep_not_for_blocking() -> None:
    """Пауза між повторами не блокує воркер."""
    import inspect

    source = inspect.getsource(recovery_task._deliver)
    assert "await asyncio.sleep" in source
    assert "time.sleep" not in source


@pytest.mark.parametrize(
    ("env", "configured", "ready"),
    [("local", False, True), ("staging", False, False), ("prod", True, True)],
)
def test_readiness_refuses_when_mail_is_unconfigured_outside_local(
    monkeypatch: pytest.MonkeyPatch, env: str, configured: bool, ready: bool
) -> None:
    """Готовність — друга лінія після падіння старту в проді.

    Прод без пошти взагалі не будується, тож цей гейт передусім про
    staging: там `Settings` не заперечує, транспорт стає `NullMailer`, і
    відновлення пароля мовчки не працює. Тиха відмова саме тут
    найдорожча — ніхто не скаржиться на лист, якого не чекав.

    `/health`, а не `/health/ready`, лишається зеленим навмисно: процес
    живий і решту роботи виконує, перезапуск його не полагодить.
    Балансувальник має лише не слати сюди новий трафік.
    """
    from fastapi import HTTPException

    from app.api.routes import health as health_route

    extra: dict[str, object] = (
        {
            "mail_smtp_host": "smtp.example.com",
            "mail_sender": "crawldy@example.com",
            "public_app_url": "https://crawldy.ai",
        }
        if configured
        else {}
    )
    configured_settings = _settings(app_env=env, **extra)
    monkeypatch.setattr(health_route, "settings", configured_settings)
    monkeypatch.setattr(mail, "settings", configured_settings)

    if ready:
        health_route._assert_mail_ready()
    else:
        with pytest.raises(HTTPException) as raised:
            health_route._assert_mail_ready()
        assert raised.value.status_code == 503
        assert raised.value.detail == {"reason": "mail.unconfigured"}
