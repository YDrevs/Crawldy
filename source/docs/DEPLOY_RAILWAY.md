# Деплой Crawldy на Railway

Покрокова інструкція: як розгорнути проєкт на Railway і підключити домен
`crawldy.ai`. Загальний чекліст безпеки для проду описано в
[SECURITY_HARDENING_2026-11.md](SECURITY_HARDENING_2026-11.md), §7.

## 1. Склад проєкту

В одному проєкті Railway працюють п'ять сервісів. Config-as-code
(`railway.json`) Railway визнав застарілим і для нових сервісів не
приймає, тому все задається в **Settings** кожного сервісу.

| Сервіс | Root Directory | Builder | Watch Paths | Pre-deploy | Healthcheck | Порт |
|---|---|---|---|---|---|---|
| `api` | `/source/backend` | Dockerfile | `/source/backend/**` | `alembic upgrade head` | `/health` | `PORT=8000` |
| `worker` | `/source/backend` | Dockerfile | `/source/backend/**` | — | — | — |
| `web` | `/source/frontend` | Dockerfile | `/source/frontend/**` | — | `/` | `PORT=3000` |
| `Postgres` | шаблон Railway | | | | | |
| `Redis` | шаблон Railway (одразу з паролем) | | | | | |

Що вже налаштовано в репозиторії:
- API і воркер збираються з одного `backend/Dockerfile`. Який образ збирати,
  визначає змінна `CRAWLDY_IMAGE` (`api` за замовчуванням, `worker` для
  воркера), бо обрати ціль збірки Railway не вміє. Лише образ воркера
  містить Chromium.
- `web` будується з `frontend/Dockerfile`. Без `NEXT_PUBLIC_API_URL`
  збірка зупиняється з помилкою.
- Адресу бази у форматі `postgres://…`, як її віддає Railway, застосунок
  сам переводить на `postgresql+asyncpg://…`.
- Автодеплой відбувається з гілки `main`. Watch paths налаштовані так, що зміни
  лише у фронті не перезбирають бекенд, і навпаки.

## 2. Створення сервісів

1. **Add → Database → PostgreSQL**, потім **Add → Database → Redis**.
2. Сервіс, підключений до репозиторію, перейменувати на `api` і задати
   налаштування з таблиці §1. Гілка `main`.
3. `worker` і `web` створити через **Duplicate** у контекстному меню `api`:
   налаштування й джерело копіюються. Потім виправити їх за таблицею.
   Якщо GitHub-застосунок Railway має доступ до репозиторію, можна й через
   **Add → GitHub Repository**.
4. Для `api` і `web` у **Settings → Networking → Generate Domain** створити
   тимчасові адреси `*.up.railway.app`. Для `api` вказати порт 8000.
   `worker` публічна адреса не потрібна.
5. **Project Settings → Usage:** поставити ліміт витрат.

Якщо в налаштуваннях сервісу видно «Could not load branches», значить
GitHub-застосунок Railway не має доступу до `YevhenDrevs/Crawldy`. Видати
доступ: GitHub → Settings → Applications → Railway → Configure.

## 3. Змінні

`${{…}}` — це посилання Railway на змінні іншого сервісу. Їх вставляють
так, як написано. Найзручніше — через **Variables → Raw Editor**.

### 3.1 `api` (тут живуть усі секрети)

| Змінна | Значення |
|---|---|
| `APP_ENV` | `prod` (див. примітку нижче) |
| `PORT` | `8000` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `PUBLIC_APP_URL` | `https://${{web.RAILWAY_PUBLIC_DOMAIN}}`; після підключення домену — `https://crawldy.ai` |
| `CORS_ORIGINS` | так само, як `PUBLIC_APP_URL` |
| `API_KEYS` | `""` (порожньо), або власний ключ, якщо потрібен глобальний доступ |
| `TRUSTED_PROXY_COUNT` | `1` (перевірити після деплою, див. §5) |
| `BILLING_PROVIDER` | `paddle` |
| `PADDLE_ENV` | спершу `sandbox`, потім `live` |
| **Секрети, вводить власник:** | |
| `IP_HASH_SALT` | випадковий рядок ≥16 символів |
| `SECRETS_KEY` | ключ Fernet (команда нижче) |
| `MAIL_SMTP_HOST`, `MAIL_SMTP_USERNAME`, `MAIL_SMTP_PASSWORD`, `MAIL_SENDER` (+ `MAIL_SMTP_PORT`, якщо не 587) | дані SMTP |
| `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET` | з кабінету Paddle |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | з Cloudflare Turnstile |
| `CONTACT_*` | пошта для форми контактів (як у `.env.example`) |
| `LLM_ENABLED`, `ANTHROPIC_API_KEY` та інші ключі ШІ | за потреби |
| `PSI_API_KEY` | ключ PageSpeed Insights |

Генерувати секрети локально, у `source/backend`:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"      # IP_HASH_SALT
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # SECRETS_KEY
```

> **`APP_ENV`.** Прод не стартує без `MAIL_SMTP_HOST`, `MAIL_SENDER`,
> `IP_HASH_SALT` і `PUBLIC_APP_URL` на `https://`. Якщо SMTP ще немає, для
> першого запуску можна поставити `staging`. Тоді `/docs` відкриті, а
> `/health/ready` повертає 503 через пошту. Перед відкриттям для людей
> обов'язково повернути `prod`.

### 3.2 `worker`

Воркер посилається на змінні `api`, тому секрети вводяться один раз.

| Змінна | Значення |
|---|---|
| `CRAWLDY_IMAGE` | `worker` |
| `RENDER_CHROMIUM_SANDBOX` | `false` |
| `APP_ENV`, `LOG_LEVEL`, `DATABASE_URL`, `REDIS_URL`, `PUBLIC_APP_URL`, `CORS_ORIGINS`, `API_KEYS`, `TRUSTED_PROXY_COUNT`, `BILLING_PROVIDER`, `PADDLE_ENV`, `IP_HASH_SALT`, `SECRETS_KEY`, `MAIL_SENDER`, `MAIL_REPLY_TO`, `MAIL_SMTP_HOST`, `MAIL_SMTP_USERNAME`, `MAIL_SMTP_PASSWORD`, `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PSI_API_KEY`, `ANTHROPIC_API_KEY` | кожна як `${{api.<ІМʼЯ>}}` |

Нова змінна, потрібна воркеру, додається в `api` і посиланням сюди.

На Railway не можна підключити seccomp-профіль `deploy/seccomp/chromium.json`,
тож sandbox Chromium не стартує. Захист від SSRF у браузері (`_RouteGuard`)
від цього не залежить. Що це означає для безпеки, описано в §6.

### 3.3 `web`

| Змінна | Значення |
|---|---|
| `PORT` | `3000` |
| `NEXT_PUBLIC_API_URL` | `https://${{api.RAILWAY_PUBLIC_DOMAIN}}`; після підключення домену — `https://api.crawldy.ai` |
| `HSTS_ENABLED` | `false` до підключення домену, потім `true` |
| `TRUSTED_PROXY_COUNT` | `1` |

`NEXT_PUBLIC_API_URL` і `HSTS_ENABLED` вшиваються в бандл під час збірки. Тому
якщо змінити будь-яку з них, `web` треба перезібрати (**Redeploy**).

## 4. Перший деплой і перевірка

1. Запустити **Deploy** для `api`, `worker` і `web`. У логах `api` на етапі
   pre-deploy має бути видно міграції `alembic`.
2. `https://<api-домен>/health` повертає `{"status":"ok"}`.
   `/health/ready` перевіряє базу й пошту.
3. У логах `worker` має бути старт `arq` без помилок підключення до Redis.
4. `https://<web-домен>/` відкривається. Можна запустити анонімний аудит
   будь-якого сайту, а потім перевірити в логах `worker`, що він
   завершився і рендер Chromium працює.

**Вхід в акаунт на доменах `*.up.railway.app` не працює.** `up.railway.app`
є у Public Suffix List, тож для браузера фронт і API — це різні сайти.
Сесійна cookie `SameSite=Lax` у запитах фронту до API не надсилається. На
`crawldy.ai` / `api.crawldy.ai` це один сайт, і вхід працює. Тому домен
підключають одразу після першого деплою.

## 5. Домен `crawldy.ai`

Railway підключає домен через CNAME, а для кореня домену (`crawldy.ai` без
піддомену) звичайна DNS-зона CNAME не дозволяє. Рішення: перенести DNS на
Cloudflare (безкоштовний план). Реєстрація домену лишається в hostiq.ua.

1. На Cloudflare додати сайт `crawldy.ai` і отримати два NS-сервери.
2. У hostiq.ua, в налаштуваннях домену, замінити NS на сервери Cloudflare.
   Перед цим перенести в Cloudflare записи пошти (MX, SPF, DKIM), якщо вони є.
3. У Railway:
   - `web` → **Custom Domain** → `crawldy.ai` і `www.crawldy.ai`;
   - `api` → **Custom Domain** → `api.crawldy.ai`.

   Railway покаже, які записи прописати: CNAME, а для перевірки ще TXT.
4. У Cloudflare додати ці записи з режимом **DNS only** (сіра хмаринка), щоб
   Railway сам видав сертифікат. Якщо ввімкнути проксі Cloudflare, перед
   API з'явиться ще один проксі, і тоді треба змінити `TRUSTED_PROXY_COUNT`.
5. Коли сертифікати видано, змінити змінні:
   - `PUBLIC_APP_URL` і `CORS_ORIGINS` поставити `https://crawldy.ai`;
   - `NEXT_PUBLIC_API_URL` поставити `https://api.crawldy.ai`;
   - `HSTS_ENABLED` поставити `true`.

   Після цього перезібрати `web`, а `api` і `worker` перезапустити.
6. Вебхук Paddle налаштувати на `https://api.crawldy.ai/…` (шлях — у
   документації білінгу).
7. **Перевірити `TRUSTED_PROXY_COUNT`.** Надіслати запит до API із
   заголовком `X-Forwarded-For: 1.1.1.1` і переконатися, що лімітер і логи
   бачать справжню адресу клієнта, а не `1.1.1.1`.
8. Пройти вхід, касу Paddle (sandbox) і Turnstile. У консолі браузера не
   має бути порушень `Content-Security-Policy-Report-Only`. Якщо їх немає,
   повну CSP можна переводити в примусову.

`www.crawldy.ai` і `crawldy.com` перенаправляє сам застосунок
(`next.config.mjs`, 308 на `https://crawldy.ai`).

## 6. Що слабше, ніж на власному сервері

- **Sandbox Chromium вимкнено.** Від запитів браузера на внутрішні адреси
  захищає код, а не sandbox. Але якщо експлойт самого Chromium спрацює на
  чужому сайті, він виконується прямо в контейнері воркера, де лежать
  змінні з паролями бази й Redis. Як посилити пізніше: винести `worker` на
  VPS із seccomp-профілем, а решту лишити на Railway.
- **Немає egress-фільтра.** Обмежити, куди воркер ходить у мережу, Railway
  не дозволяє. Лишаються перевірки в коді: кожна адреса проходить
  `_is_forbidden`, а зʼєднання прив'язується до перевіреного IP.
