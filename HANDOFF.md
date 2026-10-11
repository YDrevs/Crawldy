# Crawldy — complete product handoff

Everything needed to run Crawldy on another machine: the public website, the customer cabinet,
the admin cabinet, the API, the worker, the full analysis engine, its tests, migrations,
localizations, legal pages, brand assets and the benchmark data the engine's tooling depends on.

This archive contains **no credentials, no database, no customer data, no Git history and no
dependency caches**. Section 18 states that precisely.

---

## 1. What the product is, and its agreed scope

Crawldy takes a URL and returns a score from 0 to 100 across six dimensions, each finding backed
by evidence and a recommendation:

| Dimension | What it judges |
|---|---|
| Speed / UX | LCP, INP, CLS, TTFB, render-blocking, images, third-party impact |
| Basic SEO | title, meta description, headings, canonical, robots.txt, sitemap, indexability, internal links |
| AI-ready / LLMO | llms.txt, JSON-LD, entity signals, schema coverage, the `@id` graph, OG and Twitter cards |
| Suitability for citation | content structure, a direct answer, About/Contact/Brand, authorship |
| Protection and analytics | security headers, counters, form protection, caching, 404s, redirects, contact consistency |
| Accessibility | what breaks use, separately from what merely makes it harder |

The fourth dimension measures **suitability** for citation, not the fact of being cited. No
prompt is sent to any assistant to check whether it mentions a brand; the product does not claim
otherwise anywhere in its wording.

Alongside the audit, **Actual AI Presence** measures whether configured AI providers mention a
brand in their answers. It is a separate product with its own methodology and its own documents.

Scope as handed over: phases 0–4 are complete — reports (JSON and Word, in two views for two
readers, six languages), multiple URLs per audit, public report links, the customer cabinet, the
admin cabinet, Playwright rendering, authentication, password recovery, billing through a
provider adapter, scheduled audits and score history. PDF export was deliberately deferred.

## 2. Architecture

Five services. Nothing else is required to run the product.

```
   browser ──▶ frontend (Next.js 15)  ──▶ API (FastAPI)  ──▶ PostgreSQL 16
                                              │
                                              └──▶ Redis ──▶ worker (ARQ)
                                                               │
                                                               └──▶ the analysis engine
```

- **frontend** — the public site in six languages, the customer cabinet and the admin cabinet.
- **API** — thin HTTP layer. It never performs an audit itself: it queues work and reads results,
  which is why its p99 stays under 100 ms.
- **worker** — ARQ. Runs audits, AI Presence runs, enrichment and password-recovery delivery,
  plus two cron jobs (a scheduler tick each minute, a retention sweep at 03:00).
- **PostgreSQL** — the only durable store.
- **Redis** — the queue and the rate-limit counters.

Two architectural rules are worth knowing before changing anything. `backend/app/audit/` imports
neither FastAPI nor SQLAlchemy — it is a pure core that takes a URL and returns an outcome, which
is why its checks are testable without a database or a network. And the API process makes no
outbound network call for an audit; all of that belongs to the worker.

## 3. Directory structure

```
source/
├── backend/
│   ├── app/
│   │   ├── api/            HTTP routes, authentication by session cookie or X-API-Key
│   │   ├── audit/          the engine: crawler, extractor, checks, scoring, render
│   │   │   ├── checks/     80 checks across six modules
│   │   │   ├── standards/  reference data with a source and a checked-on date
│   │   │   ├── render/     Playwright renderer
│   │   │   └── performance/ PSI or Lighthouse provider
│   │   ├── report/         JSON and Word report building
│   │   ├── presence/       Actual AI Presence
│   │   ├── enrich/         AI enrichment, after the deterministic truth, disabled by default
│   │   ├── billing/        payment provider adapters
│   │   ├── identity/       users, sessions, passwords, recovery
│   │   ├── worker/         ARQ tasks and the queue
│   │   └── models/         SQLAlchemy models
│   ├── alembic/versions/   54 migrations, head 0054
│   ├── scripts/            operational and calibration tooling
│   ├── tests/              unit and PostgreSQL integration tests
│   ├── benchmark/          calibration and regression data used by tests and tooling
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── (product)/      login, forgot, reset, checkout, buy, result, report, app/, admin/
│   │   ├── content/        the six-language site, including the four legal documents
│   │   ├── components/     shared UI
│   │   └── lib/            API client, i18n, contracts
│   ├── package.json
│   └── package-lock.json
├── brand-assets/           brand sources
├── docs/                   canonical documentation
└── docker-compose.yml
```

## 4. Prerequisites

| | |
|---|---|
| Python | 3.12 or newer (`requires-python = ">=3.12"`) |
| Node.js | 22 (the compose file builds the frontend on `node:22-alpine`) |
| PostgreSQL | 16 |
| Redis | 7 |
| Docker | only if you use `docker compose`; running the services directly does not need it |

Playwright's Chromium is needed for JS rendering. Without it the product still runs: audits
become `partial` and say so rather than inventing numbers.

## 5. Installation and startup

### With Docker Compose

```bash
cd source
cp backend/.env.example backend/.env     # then fill it in, see section 11
docker compose up --build
```

This starts PostgreSQL, Redis, the API on `:8000`, the worker and the frontend on `:3000`.

### Directly

```bash
cd source/backend
python -m venv .venv
. .venv/bin/activate                     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install --with-deps chromium  # optional; without it audits are partial

cd ../frontend
npm ci
```

## 6. A clean PostgreSQL, migrations and bootstrap data

```bash
createdb crawldy                          # or CREATE DATABASE crawldy;
cd source/backend
export DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/crawldy
alembic upgrade head
```

`alembic upgrade head` reaches migration `0054` and creates 42 tables. **The migrations create
the required non-personal bootstrap themselves**: four plan definitions with their entitlement
sets (`free`, `starter`, `pro`, `agency`) and one system organization. There is no seed file to
run and none is needed.

Commercial configuration — which plans are public, what they cost, which one-off offers exist —
is **not** included in this archive and is not seeded. Those were the previous owner's decisions
and carried identifiers from their own payment-provider account. You create your own in the
admin cabinet (section 7), and the cabinet publishes your prices to your own provider.

On a database with no commercial rows the product runs normally: `/v1/plans` and `/v1/offers`
return empty lists with `200`, the pricing page renders its cards with no price, and checkout
answers `503 checkout.unavailable` rather than failing.

## 7. Creating the first administrator

There is no default administrator and no built-in password. The procedure is two steps, and the
password never leaves the person who chooses it.

```bash
# 1. Register normally, through the product's own sign-up form, at /login.

# 2. Raise that person's platform role, once, from the command line:
cd source/backend
python scripts/grant_platform_role.py --email you@example.com --role admin
```

`staff` can view and assist; `admin` can additionally change individual terms and replay billing
events. `admin` covers `staff`. Running the command twice changes nothing and says so.

```bash
python scripts/grant_platform_role.py --email you@example.com --show
python scripts/grant_platform_role.py --email you@example.com --revoke
```

The script refuses an address that has not registered rather than creating it, does not set or
generate a password, and has no HTTP route — promotion to staff is needed once in the life of an
installation, and an endpoint for it would be an attack surface for ever.

The admin cabinet is then at `/admin`.

## 8. Running API, worker, frontend, Redis and PostgreSQL

```bash
# PostgreSQL and Redis (compose provides both)
docker compose up -d postgres redis

# API
cd source/backend
uvicorn app.main:app --reload            # development
uvicorn app.main:app --host 0.0.0.0 --port 8000

# worker — it has no hot reload; restart it after changing the pipeline or a check
arq app.worker.main.WorkerSettings

# frontend
cd source/frontend
npm run dev                              # development, :3000
npm run build && npm run start           # production
```

## 9. Running the engine

The engine runs standalone, without a database or a queue. This is the fastest way to see what
the product actually does.

```bash
cd source/backend
python scripts/audit_cli.py https://example.com --max-pages 10 --no-perf
python scripts/audit_cli.py https://example.com --json          # raw findings
python scripts/audit_cli.py https://example.com --report        # full JSON report
python scripts/audit_cli.py https://example.com --report --lang en
python scripts/audit_cli.py https://example.com --docx out.docx --lang uk

# capture an audit, then re-score it later without touching the network
python scripts/audit_cli.py https://example.com --save-snapshot snap.json --json
python scripts/audit_cli.py --from-snapshot snap.json --json

# calibration: run a sample, then sweep parameters over its results
python scripts/calibrate.py --sites scripts/samples/calibration.txt --snapshots snaps/
python scripts/score_sweep.py calibration.json

# judge a rule change: before and after, on identical data
python scripts/rescore_dir.py snaps/
```

Two engine rules matter when interpreting results. A rule change is judged by re-scoring the
same snapshots, never by comparing two live runs — the run-to-run spread is larger than most
changes being measured. And when a provider does not answer, the module is excluded from the
score and the audit becomes `partial`; no plausible-looking number is ever invented.

## 10. Lint, type-check, test, build, migrate

```bash
# backend — run from source/backend, not from the archive root
cd source/backend
pytest -q                                # needs PostgreSQL for tests/integration
ruff check app tests scripts
mypy --strict app/audit app/core app/identity app/sites app/billing app/scheduling app/enrich

# frontend — this order matters, see below
cd source/frontend
npx tsc --noEmit
npm run build
npx vitest run

# migrations
cd source/backend
alembic upgrade head
alembic revision --autogenerate -m "description"
alembic heads
alembic check

# docker
docker compose up --build
docker compose restart worker            # after changing the pipeline or a check
docker compose restart frontend          # bind mounts do not reach inotify on Windows
```

**Run the backend tests from `source/backend`.** The benchmark paths inside the engine tests are
relative to that directory. Run them from anywhere else and four tests fail with
`StopIteration` while eleven more pass without asserting anything.

**Run the frontend build before the frontend tests.** Twenty-three tests are gated on
`.next/BUILD_ID` and that gate is evaluated when the file is collected. After a build they start
a real `next start` on `127.0.0.1:3477` and assert the security headers across nine routes;
without one they skip. `next dev` removes `BUILD_ID`, so build again before testing.

## 11. Environment variables

Copy `backend/.env.example` to `backend/.env` and fill it in. The example file ships with every
value blank — there are no real values anywhere in this archive.

| Variable | Meaning |
|---|---|
| `APP_ENV` | `local`, `staging` or `prod`. Production refuses to start without mail configuration. |
| `LOG_LEVEL` | standard Python level name |
| `API_KEYS` | comma-separated keys for integration access |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@host:5432/db` |
| `REDIS_URL` | queue and rate-limit counters |
| `PERF_PROVIDER` | `psi`, `lighthouse` or `auto` |
| `PSI_API_KEY` | free Google key. Without it Core Web Vitals are unavailable and the speed module becomes `partial`. |
| `LIGHTHOUSE_URL` | address of a Lighthouse sidecar, if used |
| `CRAWL_MAX_PAGES`, `CRAWL_MAX_DEPTH`, `CRAWL_CONCURRENCY` | crawl budget |
| `HTTP_TIMEOUT_S`, `MAX_RESPONSE_BYTES`, `AUDIT_TIMEOUT_S` | fetch and audit limits |
| `USER_AGENT` | must be a real address or none at all; a placeholder URL is treated as a scraper by some WAFs |
| `ALLOW_PRIVATE_HOSTS` | keep `false`; the SSRF guard depends on it |
| `CRAWLER_CONTACT` | contact address for the corpus-harvesting scripts in `scripts/samples/`. Empty by default; those scripts refuse to run without it. Unrelated to the audit `USER_AGENT`. |
| `CORS_ORIGINS` | empty means local development origins only |
| `PUBLIC_RATE_LIMIT`, `PUBLIC_RATE_WINDOW_SECONDS` | anonymous audits per address per window |
| `CHECKOUT_RATE_LIMIT` | reopening one's own checkout, counted separately |
| `IP_HASH_SALT` | set to something random in production, or the anonymous counter stops being anonymous |
| `TRUST_PROXY_HEADERS` | only behind a real proxy, otherwise a client assigns itself an address |
| `RENDER_ENABLED`, `RENDER_MAX_PAGES`, `RENDER_TIMEOUT_S` | Playwright rendering |
| `BILLING_PROVIDER` | `fake` or `paddle`. `fake` is never registered when `APP_ENV=prod`. |
| `BILLING_PAST_DUE_GRACE_DAYS`, `BILLING_REFUNDABLE_FAILURES` | entitlement policy after a failed charge |
| `SECRETS_KEY` | encrypts secrets an administrator saves from the cabinet |
| `PADDLE_ENV`, `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET` | payment provider. The API key never reaches the frontend; the client token is public by Paddle's design. Without the webhook secret the webhook rejects everything, because there is nothing to verify a signature with. |
| `PADDLE_TIMEOUT_S`, `PADDLE_SIGNATURE_TOLERANCE_S` | provider call limits |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | contact-form anti-bot. Without the secret there is no verification, and in production the form refuses rather than accepting unprotected messages. |
| `CONTACT_RECIPIENT`, `CONTACT_SENDER`, `CONTACT_SMTP_*` | delivery of contact messages. Separate from `MAIL_*`: here the recipient is always you. |
| `CONTACT_RATE_LIMIT`, `CONTACT_RATE_WINDOW_SECONDS` | contact-form abuse limits |
| `PUBLIC_APP_URL` | the **site** address a recovery link points to, not the API address. Must be `https://` in production. |
| `PASSWORD_RESET_TTL_MINUTES` | how long a recovery link lives |
| `RECOVERY_RATE_LIMIT`, `RECOVERY_RATE_WINDOW_SECONDS` | recovery limits, separate from the contact form |
| `MAIL_SENDER`, `MAIL_REPLY_TO`, `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT`, `MAIL_SMTP_USERNAME`, `MAIL_SMTP_PASSWORD`, `MAIL_SMTP_TLS` | mail to the **customer**. STARTTLS on 587. Production refuses to start without host and sender. |
| `MAIL_CAPTURE_DIR` | local only: write `.eml` files instead of sending. Ignored outside `APP_ENV=local`. |
| `LLM_ENABLED`, `ANTHROPIC_API_KEY`, `LLM_MODEL`, `LLM_MAX_PAGES`, `LLM_MAX_TOKENS`, `LLM_EFFORT` | the legacy semantic layer. It runs **before** scoring and can change a score. Disabled; do not enable without a deliberate decision. |
| `ENRICH_ENABLED`, `OPENAI_API_KEY`, `ENRICH_*` | AI enrichment. Runs **after** the deterministic truth and cannot change a score. Disabled. |
| `PERPLEXITY_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_VERTEX_PROJECT`, `GOOGLE_VERTEX_LOCATION` | AI Presence providers. Vertex authenticates through ADC or workload identity, not through a key. |

### A note on the benchmark corpus

`backend/benchmark/` is 122 files of calibration and regression data that eight test modules and
two tooling scripts depend on. Almost all of it is ignored by Git, so a copy made with
`git archive` or a fresh clone would not contain it and the suite would not be green. It is
included here in full, with one deliberate exception described in section 18.

## 12. Languages

Six launch languages, complete across the public site, the cabinet, the reports and the
recovery email: **`uk`, `en`, `de`, `es`, `fr`, `ru`**.

The public site uses localized paths (`/uk/tsiny`, `/de/preise`); English has no prefix. Product
screens such as `/login`, `/forgot` and `/reset` carry the language as `?lang=`, again with
English unprefixed. Tests enforce that every catalogue key exists in all six and that no language
silently falls back to English.

## 13. External integrations actually used

| Service | Used for | Without it |
|---|---|---|
| Google PageSpeed Insights | Core Web Vitals | speed module becomes `partial`, measured TTFB still reported |
| Lighthouse | alternative performance provider | optional |
| Paddle | payments, checkout, webhooks | `fake` provider for development; no checkout in production |
| Cloudflare Turnstile | contact-form anti-bot | in production the form refuses to accept messages |
| SMTP (any provider) | password-recovery and contact mail | production refuses to start; locally mail is captured |
| Anthropic, OpenAI, Perplexity, Google Vertex AI | AI Presence and the optional AI layers | those features are unavailable; the audit is unaffected |

## 14. Backup, restore, deployment, rollback

What the project supports today, and nothing beyond it.

```bash
# backup — PostgreSQL is the only durable store; Redis holds only the queue
pg_dump -Fc "$DATABASE_URL" > crawldy-$(date +%F).dump

# restore
createdb crawldy_restored
pg_restore -d crawldy_restored crawldy-YYYY-MM-DD.dump

# deploy: bring code forward, migrate, restart
alembic upgrade head
docker compose up -d --build

# rollback of a schema change — one migration at a time
alembic downgrade -1
```

Every migration in this archive defines a working `downgrade`. Roll back code and schema
together: a newer schema with older code is untested.

There is no managed hosting, no CI pipeline and no infrastructure-as-code in this project. The
compose file is the deployment description.

## 15. Canonical documents

Under `source/docs/`:

| File | What it holds |
|---|---|
| `VERIFICATION.md` | the verification record: what was checked, how, and what was deliberately not |
| `APPLICATION.md` | the SaaS layer — accounts, billing, entitlements |
| `ENGINE.md` | the analysis engine |
| `DEVELOPMENT.md` | working practices |
| `Crawldy_Project_Work_Plan.md` | the plan as agreed |
| `Crawldy_Coverage_Reconciliation_2026-08-25.md` | a coverage reconciliation |

At the repository root, `CLAUDE.md` is the densest single document in the project: the
architectural invariants, the scoring rules, and a long list of traps already fallen into, each
with the evidence that produced it. Read it before changing the engine. `ARCHITECTURE.md`,
`ROADMAP.md` and `VALIDATION.md` sit beside it.

## 16. Verified status at handoff

| | |
|---|---|
| Backend suite | 3423 passed, 3 skipped, 0 failed |
| Frontend suite | 39 files, 756 passed, 0 skipped, 0 failed |
| Ruff | all checks passed |
| mypy `--strict` | no issues in 136 source files |
| Frontend build | compiled |
| Migration head | `0054`, reached from an empty database |
| Engine detector version | `3b9a556ab798`, 14 accepted rules |
| Engine scoring version | `aa4ecc62a5a3`, 5 accepted rules |
| Crawler version | `4` |
| Check registry | 80 checks — SEO 32, tech 14, ai_ready 12, performance 11, llm_visibility 9, accessibility 2 |

The three skipped backend tests are parametrized cases whose URL is neither `http` nor `https`;
the extractor filters those schemes earlier, so the assertion does not apply. They need no
credentials and no database.

## 17. What you still have to supply

None of this is in the archive, and the product will tell you plainly when it is missing rather
than pretending to work.

1. **Corporate SMTP** — `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT`, `MAIL_SMTP_USERNAME`,
   `MAIL_SMTP_PASSWORD`.
2. **`MAIL_SENDER`** on a domain you control, optional `MAIL_REPLY_TO`, and `PUBLIC_APP_URL` as a
   real `https://` origin. Production refuses to start without the first two and the https URL.
3. **SPF, DKIM and DMARC** for that domain, aligned with the relay you use.
4. **Real email and deliverability testing.** Delivery has never been exercised against a real
   relay — every run used the local capture transport. Whether a provider files your mail as spam
   cannot be known until you test it.
5. **Production Paddle configuration** — account, API key, client token, webhook destination and
   its secret, and your own prices published from the admin cabinet.
6. **Turnstile** site and secret keys, or the contact form will refuse messages in production.
7. **Model provider credentials** for AI Presence: Perplexity, Anthropic, OpenAI, and a Google
   Cloud project with Vertex AI enabled.
8. **Production performance and accessibility checks** against the deployed site, which is not
   the same thing as the local suite.
9. **A final audit of your published site with this engine** — the product's own standard,
   applied to itself.

## 18. What this archive does not contain

No credentials of any kind: no API keys, SMTP passwords, payment-provider secrets, webhook
secrets, cookies, access tokens or reset tokens. No `.env` — only `.env.example`, whose values
are all blank.

No database and no customer data: no PostgreSQL or Redis dump, no Docker volume, and none of the
previous owner's users, organizations, audits, pages, issues, payments, balances, sessions or
password-reset records.

No Git history, no `.next`, `node_modules`, `.venv`, `__pycache__`, `.pytest_cache`, coverage or
compiled output, no Docker images or build cache, no logs of a running system, no captured `.eml`
files or mailboxes, no browser profiles, and no previous archives or working directories.

Dependencies are declared, not vendored: `backend/pyproject.toml` and
`frontend/package-lock.json` with the commands in section 5 are sufficient to reproduce them.

**Build your own virtual environment.** Do not copy one. The previous environment contained an
editable install whose finder mapped the package name `app` to the original machine's worktree;
an extracted copy using it would silently import the wrong tree.

### The calibration corpus is privacy-clean at source

This archive is a byte-faithful copy of the repository. Nothing was transformed while packaging —
the corrections below were made to the product itself, and `docs/VERIFICATION.md` §11 records
them in full:

1. **A bulk personal dataset was removed** from both of its carriers — a snapshot holding tens of
   thousands of real consumer addresses crawled from a compromised site's spam comments, and the
   byte-identical copy inside `snapshots-auditlens-set.tar.gz`. The site was also removed from
   `scripts/samples/calibration.txt` and `benchmark/corpus.py`, so an ordinary `calibrate.py` run
   cannot import it again.
2. **Every remaining third-party address is a deterministic synthetic** under the reserved
   `.invalid` domain. Duplicates stay duplicates, role mailboxes stay role mailboxes, and no
   reverse mapping exists because none was built.
3. **Captured cookie values and third-party API keys are redacted**, with cookie names and
   attributes preserved. They belonged to the audited sites, not to Crawldy.
4. **Machine-specific paths are replaced** by `<PROJECT_ROOT>`, `<HOME>` and `<WORK_DIR>`.
5. **The crawler's contact is a setting**, `CRAWLER_CONTACT`, empty by default. The two
   corpus-harvesting scripts refuse to run without it rather than sending a plausible-looking
   address that reaches nobody. The engine's own `USER_AGENT` is unchanged and still carries no
   contact at all, for the reason given in section 11.

`backend/tests/test_benchmark_privacy.py` keeps it that way: it scans the corpus and its nested
archives and fails on any of six classes. Each class was mutation-tested. Cleaning once would not
have been enough — the next calibration run writes fresh third-party evidence into the corpus.

**Effect on the engine: one score moved.** `smartkp.com.ua` went from 57 to 58 because one
replaced address had itself been a `tech.demo_content` signal. The detector is unchanged:
`3b9a556ab798`, 14 accepted rules, 80 checks.
