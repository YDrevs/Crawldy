from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Службові ключі, які стоять у прикладах конфігурації й тому відомі всім.
PUBLIC_EXAMPLE_KEYS = frozenset({"dev-key-change-me"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "staging", "prod"] = "local"
    log_level: str = "INFO"
    # NoDecode обовʼязковий: для list[str] pydantic-settings пробує json.loads
    # ще до валідаторів, і `API_KEYS=dev-key` з .env валить старт застосунку.
    #
    # Без значення за замовчуванням: ключ із прикладу конфігурації відомий
    # усім, хто бачив репозиторій, а він давав роль OWNER службової
    # організації. Порожньо — службового ключа немає взагалі.
    api_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Звідки браузеру дозволено ходити в API. Точні origin'и, а не "*":
    # cookie-сесія вимагає `allow_credentials`, а з ним браузер відкидає
    # зірочку — і вхід мовчки не працює саме в проді, де це найдорожче.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    database_url: str = "postgresql+asyncpg://seo:seo@localhost:5432/seo"
    redis_url: str = "redis://localhost:6379/0"

    perf_provider: Literal["psi", "lighthouse", "auto"] = "psi"
    psi_api_key: str | None = None
    lighthouse_url: str = "http://lighthouse:3000"

    # Семантичний шар. Вимкнений за замовчуванням: на відміну від решти
    # аудиту, він коштує грошей за кожен виклик, і вмикати його мовчки за
    # клієнта не можна. Без ключа не працює навіть при llm_enabled=True.
    # Скільки днів прав лишається після невдалого списання.
    #
    # Явна політика, а не безмежний доступ: нуль означає відрізати одразу,
    # більше нуля — дати клієнту шанс полагодити картку. Значення в
    # налаштуваннях, бо це рішення бізнесу, а не коду, і міняти його не
    # має вимагати релізу.
    billing_past_due_grace_days: int = 7

    # За які класи невдач повертається квота. None — політика за
    # замовчуванням (`billing.refund_policy.DEFAULT_REFUNDABLE`).
    #
    # Списком, а не прапорцями: політика мусить читатися цілком в одному
    # місці. Набір із трьох булевих налаштувань дає вісім комбінацій, з
    # яких половину ніхто ніколи не перевірить.
    billing_refundable_failures: list[str] | None = None

    llm_enabled: bool = False
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"
    llm_max_pages: int = 3
    llm_max_tokens: int = 2000
    # Задача вузька й описова — прочитати текст і повернути факти. Глибші
    # рівні тут не покращують відповідь, лише збільшують рахунок.
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"

    # ── AI Enrichment (фаза 1, експериментальна) ──────────────────────────
    #
    # Окремий шар від семантики вище: він стоїть ПІСЛЯ детерміністичної
    # правди й не може змінити ані знахідку, ані бал. Тому й прапорець
    # окремий: `llm_enabled` вмикає шар, що впливає на бал, і лишається
    # вимкненим незалежно від цього.
    #
    # Вимкнено за замовчуванням, і самого прапорця замало: запуск вимагає
    # ще й явного внутрішнього тригера. Клієнтських шляхів, які його
    # передають, не існує — до затвердження бенчмарку.
    enrich_enabled: bool = False
    # Другий провайдер збагачення. Ключ читається лише адаптером; жоден
    # продуктовий шлях його не торкається, поки шар вимкнений.
    openai_api_key: str | None = None
    # Межа на СПРОБУ, не на прогін: дефолт SDK у 10 хвилин не має права
    # тримати платний процес.
    enrich_attempt_timeout_s: float = 45.0
    # Скільки кандидатів маршруту пробуємо, доки не здамося.
    enrich_max_attempts: int = 2
    enrich_max_output_tokens: int = 3000

    # ── Actual AI Presence (P0, beta) ─────────────────────────────────────
    #
    # Ключ третього провайдера присутності. Політика виконання (які
    # провайдери, скільки промптів і повторів, бюджети) живе НЕ тут, а в
    # адмін-конфігурації домену (`ai_domain_settings`): секрети — в
    # оточенні, рішення — в політиці, і вони не міняються разом.
    perplexity_api_key: str | None = None

    # Ключ Gemini API (Google AI Studio). Той самий поділ: ключ — в
    # оточенні, рішення про використання — в політиці домену presence.
    # Стосується ЛИШЕ бекенда developer_api; автентифікацією Vertex він
    # не буває ніколи (як і psi_api_key — то зовсім інший продукт).
    google_api_key: str | None = None

    # Vertex AI (продуктовий бекенд google-провайдера присутності).
    # Ідентифікатор проєкту — не секрет; секретів тут немає взагалі:
    # автентифікація — Application Default Credentials (локально) або
    # workload identity (деплой), тобто механізми google-auth поза
    # нашою конфігурацією. Мінімальні вимоги до проєкту: увімкнений
    # aiplatform.googleapis.com і роль roles/aiplatform.user у
    # службової ідентичності (docs.cloud.google.com/vertex-ai/docs/
    # general/iam-permissions, звірено 2026-09-01).
    google_vertex_project: str | None = None
    google_vertex_location: str = "global"

    # Хто зараз обслуговує касу. Значення — імʼя адаптера в реєстрі.
    #
    # За замовчуванням фейк: розробник без ключів Paddle мусить бачити
    # робочу воронку, а не 503. Безпека проду тримається не на цьому
    # значенні, а на тому, що в `app_env=prod` фейк узагалі не
    # реєструється, — дефолт не може стати дірою через недогляд у .env.
    billing_provider: str = "fake"

    # Ключ шифрування секретів, які адміністратор зберігає зі службового
    # кабінету (`runtime_settings`). Без нього збереження секрету
    # відхиляється з явною причиною, а секрети з оточення працюють як і
    # раніше: поява кабінету не робить установлення ненастроєним.
    secrets_key: str | None = None

    # ── Paddle (перший платіжний провайдер) ──────────────────────────
    #
    # Оточення явне й перевіряється за префіксом ключа: переплутати
    # пісочницю з бойовим коштувало б справжніх грошей, тож це має бути
    # неможливо, а не малоймовірно.
    paddle_env: Literal["sandbox", "live"] = "sandbox"
    paddle_api_key: str | None = None
    # Токен для браузера. Публічний за задумом Paddle — на відміну від
    # ключа API, який до фронтенду не потрапляє ніколи.
    paddle_client_token: str | None = None
    paddle_webhook_secret: str | None = None
    paddle_timeout_s: float = 20.0
    # Ширше за пʼятисекундний дефолт SDK Paddle навмисно: розбіжність
    # годинника сервера — реальний режим відмови, і виглядає він як
    # невірний підпис, тобто як атака.
    paddle_signature_tolerance_s: int = 300

    # Рендеринг свідомо йде не на всіх сторінках: браузер коштує на два
    # порядки дорожче за запит, а SSR-дельта на трьох сторінках відповідає
    # на те саме питання, що й на двадцяти п'яти.
    render_enabled: bool = True
    render_max_pages: int = 3
    render_timeout_s: float = 30.0

    crawl_max_pages: int = 25
    crawl_max_depth: int = 2
    crawl_concurrency: int = 5
    http_timeout_s: float = 15.0
    max_response_bytes: int = 5 * 1024 * 1024
    audit_timeout_s: int = 600
    # Без адреси в дужках. Заглушка example.com виглядає для WAF рівно
    # тим, чим і є, — ознакою скрапера: detailtyler.com віддавав нам 403
    # саме на неї, хоча його robots.txt дозволяє всім. Той самий рядок без
    # адреси проходив. Порожньо чесніше за фальшиве посилання; коли
    # зʼявиться справжня сторінка про бота, її сюди й треба дописати.
    user_agent: str = "SeoAgentBot/0.1"
    allow_private_hosts: bool = False

    # Контакт для скриптів, що збирають корпус (`scripts/samples/`).
    #
    # Окреме від `user_agent` і навмисно. Той рядок представляється
    # ЧУЖИМ сайтам під час аудиту, і адреси в ньому немає за рішенням
    # вище. Тут ідеться про інше: Wikidata і Tranco прямо просять того,
    # хто тягне з них масово, назвати себе, і анонімний масовий запит
    # там — привід для блокування по заслузі.
    #
    # Порожньо за замовчуванням, і жодної адреси в коді. Скрипт, якому
    # контакт потрібен, відмовляється працювати без нього замість того,
    # щоб підставити вигадану адресу: фальшивий контакт гірший за
    # відсутній, бо виглядає як справжній.
    crawler_contact: str = ""

    # ── анонімна воронка ───────────────────────────────────────────────
    #
    # Числа тут — захист від зловживання, а не тариф. Вони обмежують
    # частоту звернень з однієї адреси, і до продуктових лімітів
    # («скільки аудитів входить у план») стосунку не мають: ті живуть у
    # правах тарифу й визначаються окремо.
    public_rate_limit: int = 10
    public_rate_window_seconds: int = 3600
    # Окремо — повторне відкриття власної каси. Воно не створює нічого
    # нового (та сама покупка, та сама транзакція), тож десятка тут
    # захищала б не нас, а лише заважала людині, яка закрила вікно
    # оплати й повернулася. Скільки КАС може завести одна адреса,
    # обмежує ліміт на відкриття гостьової сесії.
    checkout_rate_limit: int = 60
    # Сіль для хешування адрес у лічильниках. Порожня означає, що хеш
    # відновлюється перебором за пів секунди — тому в проді її задають.
    ip_hash_salt: str = ""
    # Заголовку `X-Forwarded-For` можна вірити лише за нашим проксі.
    # На прямому доступі він обходить лічильник одним рядком.
    trust_proxy_headers: bool = False
    # Скільки НАШИХ проксі дописують адресу в `X-Forwarded-For`. Кожен
    # дописує праворуч, тож справжній клієнт — N-й запис справа; усе, що
    # лівіше, прислав сам клієнт і довіри не має.
    trusted_proxy_hops: int = Field(default=1, ge=1)

    # ── контактна форма ────────────────────────────────────────────────
    #
    # Антибот. Секрет живе ЛИШЕ на сервері; у браузер їде тільки
    # site-key, і те через API, а не через NEXT_PUBLIC_*, щоб
    # конфігурація провайдера лишалась в одному місці.
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None

    # Куди доставляти звернення. Адреса не потрапляє ані в базу, ані у
    # відповідь API: те, чого немає в клієнті, не збирають поштові роботи.
    contact_recipient: str | None = None
    contact_sender: str | None = None
    contact_smtp_host: str | None = None
    contact_smtp_port: int = 587
    contact_smtp_username: str | None = None
    contact_smtp_password: str | None = None
    contact_smtp_tls: bool = True

    # Окремий лічильник: зловживання контактною формою не має ділити
    # вікно з запуском аудитів, інакше одне глушить друге.
    contact_rate_limit: int = 5
    contact_rate_window_seconds: int = 3600

    # ── відновлення пароля ─────────────────────────────────────────────
    #
    # Куди веде посилання з листа. Це адреса САЙТУ, а не API: лист
    # відкриває людина в браузері. `request.base_url` тут не годиться —
    # він дає хост API, і в проді це інший домен.
    public_app_url: str = "http://localhost:3000"

    # Скільки живе посилання. Година — компроміс: досить, щоб дійти до
    # пошти й повернутись, і замало, щоб лист у відкритій скриньці
    # лишався ключем від акаунта на тиждень.
    password_reset_ttl_minutes: int = 60

    # Власне вікно, як у контактної форми. Ділити лічильник із нею не
    # можна: спам у форму не має закривати людині вхід до акаунта.
    # Рахується і за адресою запиту, і за IP — інакше один IP перебирає
    # чужі адреси, а один відправник глушить власну скриньку.
    recovery_rate_limit: int = 5
    recovery_rate_window_seconds: int = 3600
    # Вхід і створення акаунта за IP. Замикання після десяти невдач
    # тримає підбір ОДНОГО пароля, але не перебір одного пароля по
    # тисячі акаунтів і не навмисне замикання чужих. Кожна спроба ще й
    # рахує argon2 — дорогу за памʼяттю операцію.
    login_rate_limit: int = 30
    login_rate_window_seconds: int = 900
    signup_rate_limit: int = 20
    signup_rate_window_seconds: int = 3600

    # Пошта для листів КОРИСТУВАЧЕВІ. Окрема від `contact_*` навмисно:
    # там одержувач зашитий у налаштування й завжди один (ми самі), а
    # тут адреса різна для кожного листа. Спільним лишається тільки
    # протокол, і об'єднувати їх означало б зробити доставку звернень
    # залежною від конфігурації відновлення пароля.
    mail_sender: str | None = None
    # Куди піде відповідь, якщо людина натисне «відповісти». Порожньо —
    # заголовка немає взагалі, і відповідь піде на `mail_sender`.
    mail_reply_to: str | None = None
    mail_smtp_host: str | None = None
    mail_smtp_port: int = 587
    mail_smtp_username: str | None = None
    mail_smtp_password: str | None = None
    mail_smtp_tls: bool = True

    # Куди складати перехоплені листи локально. Порожньо — тільки в
    # памʼять процесу. Задано — ще й файлом `.eml`, який відкривається
    # поштовим клієнтом: розробник бачить справжній лист, а не здогад.
    mail_capture_dir: str | None = None

    @field_validator(
        "paddle_api_key",
        "paddle_client_token",
        "paddle_webhook_secret",
        "psi_api_key",
        "anthropic_api_key",
        "openai_api_key",
        "perplexity_api_key",
        "google_api_key",
        "turnstile_site_key",
        "turnstile_secret_key",
        "contact_recipient",
        "contact_sender",
        "contact_smtp_host",
        "contact_smtp_username",
        "contact_smtp_password",
        "mail_sender",
        "mail_reply_to",
        "mail_smtp_host",
        "mail_smtp_username",
        "mail_smtp_password",
        "mail_capture_dir",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, v: object) -> object:
        """Порожній рядок — це «не задано», а не секрет нульової довжини.

        `.env` з `PADDLE_API_KEY=` і оточення без змінної описують той
        самий стан, і поводитись вони мусять однаково. Інакше перевірки
        виду «ключ є?» відповідали б «так» на порожнечу.
        """
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="after")
    def _production_mail_is_configured(self) -> "Settings":
        """У проді пошта мусить бути налаштована ЯВНО.

        Мовчазне прийняття запиту на відновлення при непрацездатній
        доставці — найгірший із можливих станів: людина чекає листа,
        якого ніхто не надсилав, і жоден лічильник цього не показує.
        Тому конфігурація перевіряється на старті, а не на першому
        запиті.

        Запасної адреси відправника немає навмисно: `no-reply@` з
        чужого домену не пройде SPF і тихо осяде в спамі.
        """
        if self.app_env != "prod":
            return self
        missing = [
            name
            for name, value in (
                ("MAIL_SMTP_HOST", self.mail_smtp_host),
                ("MAIL_SENDER", self.mail_sender),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "у проді обовʼязкові: " + ", ".join(missing)
            )
        if not self.public_app_url.lower().startswith("https://"):
            raise ValueError("PUBLIC_APP_URL у проді мусить бути https://")
        return self

    @model_validator(mode="after")
    def _production_service_keys_are_secret(self) -> "Settings":
        """Ключ із `.env.example` у проді — це пароль, надрукований у README."""
        if self.app_env != "prod":
            return self
        weak = [k for k in self.api_keys if k in PUBLIC_EXAMPLE_KEYS or len(k) < 24]
        if weak:
            raise ValueError(
                "API_KEYS у проді містить ключ із прикладу або коротший за 24 символи"
            )
        return self

    @field_validator("api_keys", "cors_origins", mode="before")
    @classmethod
    def _split_keys(cls, v: object) -> object:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
