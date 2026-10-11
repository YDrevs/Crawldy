# Crawldy

Crawldy audits a website and returns a score from 0 to 100 with findings, evidence and
recommendations. Every finding carries what was expected and what was actually observed.

The product answers three **different** questions, and keeps them apart deliberately:

| Question | What it means | Where it lives |
|---|---|---|
| **Search visibility / technical SEO** | Can search engines reach, index and understand the site? | engine modules `seo`, `tech`, `performance` |
| **AI readiness** | Can AI systems retrieve the pages, understand the business and use the site as a source? | engine modules `ai_ready`, `llm_visibility` |
| **Actual AI presence** | Do assistants actually mention the brand in their answers? | `backend/app/presence` — a separate measurement, not an inference |

AI readiness is **not** evidence of actual AI presence. A site can be perfectly readable by AI
systems and never be mentioned by them. Documentation and product copy must not conflate the
two.

## Current implemented scope

`IMPLEMENTED` — audit engine (6 modules, 80 registered checks), report generation (JSON and
Word), a six-locale public website, a customer cabinet, an admin area, authentication,
commercial offers and credits, Paddle-backed payments, and an AI Presence subsystem.

`OUT OF CURRENT SCOPE` — hosting, deployment, a public domain, HTTPS, HSTS, a production
Content-Security-Policy and analytics. Nothing in this repository is served publicly: the
verification stage behind the current state was carried out entirely against a local build.
See [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Repository map

| Path | Contents |
|---|---|
| `backend/app/audit/` | The engine. Pure core: no FastAPI, no ORM. |
| `backend/app/report/` | Findings to report documents (JSON, `.docx`). |
| `backend/app/presence/` | AI Presence: asks assistants and records what they answered. |
| `backend/app/enrich/` | Optional AI reasoning applied **after** deterministic results. |
| `backend/app/api/`, `services/`, `models/`, `schemas/` | HTTP layer, services, persistence. |
| `backend/app/billing/`, `identity/`, `sites/`, `scheduling/` | Commerce, accounts, sites, schedules. |
| `backend/alembic/` | Database migrations. |
| `backend/scripts/` | Operational scripts, including `audit_cli.py`. |
| `backend/tests/` | Backend test suite. |
| `frontend/app/content/` | Public page content, one file per page per locale. |
| `frontend/app/(product)/` | Cabinet and admin screens. |
| `frontend/app/components/`, `lib/` | Shared components and logic. |
| `docs/` | The canonical documentation below, plus earlier planning notes. |
| `design-review/` | Reference screenshots of the site at desktop and mobile widths. |
| `brand-assets/` | Brand sources and social assets. Not served by the site — the web versions the components render live in `frontend/public/brand/`. |
| `scripts/` | `start.ps1` and `stop.ps1`, for bringing the local stack up and down. |

## Documentation

**Canonical — start here.**

| Document | Subject |
|---|---|
| [docs/APPLICATION.md](docs/APPLICATION.md) | Website, cabinet, admin and backend boundaries; routes; locales; commerce as implemented. |
| [docs/ENGINE.md](docs/ENGINE.md) | Crawl and analysis pipeline, modules, rule registry, scoring, localization. |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Prerequisites, local start, tests, type checks, builds. |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | Verified current state, what was and was not exercised, accepted decisions. |

**Deeper and historical references.** These remain useful and are not superseded in substance,
but they are longer, partly in Ukrainian, and record how decisions were reached rather than
the current state: [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md),
[VALIDATION.md](VALIDATION.md), [PHASE4_ARCHITECTURE.md](PHASE4_ARCHITECTURE.md).
[CLAUDE.md](CLAUDE.md) holds working conventions and the record of traps already hit.

## Prerequisites

- Python `>=3.12` (`backend/pyproject.toml`)
- Node.js with npm, for the Next.js frontend
- PostgreSQL 16 and Redis — required for the API, the worker and integration tests; **not**
  required to run an audit from the CLI
- Docker, if you prefer to bring up PostgreSQL and Redis with `docker-compose.yml`

## Shortest path to a result

An audit needs neither the database nor the queue:

```bash
cd backend
pip install -e ".[dev]"
python scripts/audit_cli.py https://example.com --max-pages 10 --no-perf
```

For the full stack, the frontend, the test suites and the type checks, see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
