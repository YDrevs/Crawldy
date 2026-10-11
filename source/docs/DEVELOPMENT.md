# Local development and verification

Every command below was checked against the current repository. Nothing here describes
hosting or deployment.

## Prerequisites

| Requirement | Source | Needed for |
|---|---|---|
| Python `>=3.12` | `backend/pyproject.toml` | backend and engine |
| Node.js + npm | `frontend/package.json` | website and cabinet |
| PostgreSQL 16 | `docker-compose.yml` | API, worker, integration tests |
| Redis | `docker-compose.yml` | task queue |
| Docker (optional) | `docker-compose.yml` | the quickest way to get PostgreSQL and Redis |

`docker-compose.yml` defines `postgres`, `redis`, `api`, `worker` and `frontend`.

## Environment variables

Names only — never commit values. The authoritative list is `backend/.env.example`
(61 names); the frontend reads exactly one, `NEXT_PUBLIC_API_URL`.

The ones that matter for a local start:

| Name | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | queue |
| `API_KEYS` | API authentication (`X-API-Key`) |
| `APP_ENV` | environment; the fake billing provider is not registered in production |
| `PSI_API_KEY` | PageSpeed Insights; optional, see below |
| `ALLOW_PRIVATE_HOSTS` | **process-level only**; see "Auditing a local target" |
| `LLM_ENABLED`, `ENRICH_ENABLED` | AI layers, both off by default |

`API_KEYS` needs `NoDecode` handling in settings — pydantic-settings tries `json.loads` on a
`list[str]` before validators run, which used to break startup.

## Backend

```bash
cd backend
pip install -e ".[dev]"
```

Optional dev dependencies are `pytest`, `pytest-asyncio`, `ruff`, `mypy` and `respx`.

Run the API and the worker (both need PostgreSQL and Redis):

```bash
uvicorn app.main:app --reload
arq app.worker.main.WorkerSettings
```

The worker has **no hot reload**. After changing the pipeline or a check, restart it —
otherwise it silently keeps running the previous version.

Migrations:

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

There are 53 migration files in `backend/alembic/versions/`.

## Running an audit without the database or the queue

This is the fastest way to exercise the engine:

```bash
cd backend
python scripts/audit_cli.py https://example.com --max-pages 10 --no-perf
python scripts/audit_cli.py https://example.com --json            # raw findings
python scripts/audit_cli.py https://example.com --report           # full JSON report
python scripts/audit_cli.py https://example.com --report --lang en
python scripts/audit_cli.py https://example.com --docx out.docx --lang uk
```

Re-score a stored audit against new rules, with no network:

```bash
python scripts/audit_cli.py https://example.com --save-snapshot snap.json --json
python scripts/audit_cli.py --from-snapshot snap.json --json
```

### Performance module

Without `PSI_API_KEY`, requests go to a shared anonymous quota and hit HTTP 429. The module
still works from static heuristics and the crawler's own TTFB measurements, and the audit is
then reported as `partial` rather than silently complete.

### Auditing a local target

The SSRF guard blocks private hosts by default, which also blocks `127.0.0.1`. Enabling
`ALLOW_PRIVATE_HOSTS` is an **owner decision**, and when it is taken it belongs in the process
environment of a disposable run only — never in a tracked file, never as a changed default,
and never by weakening `assert_public_host`.

## Frontend

```bash
cd frontend
npm install
npm run dev        # next dev
npm run build      # next build
npm run start      # next start, serves the production build
npm run lint       # next lint
npm run test       # vitest run
```

## Verification commands

Before a backend change is considered done:

```bash
cd backend
pytest -q
ruff check app tests scripts
mypy --strict app/audit app/core app/identity app/sites app/billing app/scheduling app/enrich
```

Before a frontend change is considered done:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

Both must be green. `next build` is not optional — a change can type-check and still fail the
build.

## Known behaviour worth knowing before debugging

- **Integration tests skip without PostgreSQL.** A run reporting hundreds of skips is not a
  complete run. Start PostgreSQL (`docker compose up -d postgres`) and re-run.
- **Vitest collects `app/**/*.test.ts` only** (`frontend/vitest.config.ts`), in a `node`
  environment. Components are rendered with `react-dom/server`, not a DOM emulator.
- **Rebuilding under a live `next start` breaks the page silently.** The running server holds
  the build manifest from when it started while the chunk files on disk are replaced; the
  browser then requests a name that no longer exists. Restart the server after every build.
- **A responding port does not prove your process is answering.** A stale server from an
  earlier session can hold the port while your new one failed to bind. Check the PID.
- **Two builds of identical source are not byte-identical.** Next mints a fresh build id into
  every HTML document and `frontend/app/sitemap.ts` stamps `lastModified: new Date()`. Compare rendered
  DOM and pixels, not raw HTML.
- **`next.config.mjs` changes require a rebuild.** `headers()` and `redirects()` are evaluated
  at build time and baked into the route manifest; editing them without rebuilding produces no
  effect at all.
- **A Windows console in cp1251 breaks Ukrainian output.** The CLI and `conftest.py` force
  stdout to UTF-8.
