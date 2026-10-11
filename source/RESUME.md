# RESUME — handoff for a fresh or scheduled session

**Read this whole file before touching the tree or `git stash`.**

## Current authorized work: Paddle sandbox integration

The overnight technical cleanup sweep is **closed** (its results are at the
bottom of this file, for history). Since then the user explicitly
authorized, in a 41-section written specification, the implementation of a
**provider-neutral one-off payment flow plus a Paddle sandbox adapter**.

**Uncommitted Paddle code in the working tree is expected and authorized.**
Do not stash, revert, or quarantine it. An earlier scheduled continuation
read the old boundary list below, concluded the in-progress Paddle work was
unauthorized, and stashed it mid-session; the work was recovered, but the
cost of repeating that mistake is a lost session.

What is authorized: the adapter, the pending-purchase lifecycle, config
placeholders, tests, docs, frontend checkout wiring.

What is still forbidden, per the same specification:

- executing a real Paddle checkout or submitting a sandbox card payment;
- creating, refunding, or canceling sandbox transactions;
- creating notification destinations in the Paddle dashboard;
- enabling the live environment or implementing production routing;
- adding subscriptions, changing Crawldy pricing, implementing Stripe/Dodo.

Read-only sandbox GETs are permitted only if credentials are already
present. Secrets are never printed and never committed.

## Boundaries that remain in force from the sweep

- `backend/benchmark/` is **frozen historical evidence**. Do not resume the
  benchmark, rerun cells, or change budgets/routing/prompts/schemas
  because of its results.
- No changes to deterministic scoring, severity, detectors, the free/paid
  boundary, or the guest purchase invariants beyond what the payment
  specification requires.
- No paid or live external calls: Anthropic, OpenAI, live Paddle, email,
  deployment. No secrets printed.
- The repository has **no git remote**. Nothing can be pushed.

## Verification commands

```
cd backend
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m mypy --strict app/audit app/core app/identity app/sites app/billing app/scheduling app/enrich
cd ../frontend
npx tsc --noEmit
npm run build
```

`tests/integration` needs PostgreSQL (`docker compose up -d postgres`);
without it they skip rather than fail.

`npm run lint` is broken — `next lint` is deprecated and no ESLint config
exists. Known; setting one up is a decision, not a fix.

Windows console is cp1251 and breaks on Cyrillic; reconfigure stdout to
UTF-8 in Python one-liners.

---

## History: overnight cleanup sweep (complete)

| Thing | Start | End |
|---|---|---|
| commit | `9703b51` | `490a535` |
| backend tests | 1254 | 1267 |
| ruff | clean | clean |
| mypy --strict | clean | clean (now also `app/enrich`) |
| frontend tsc / build | clean | clean |
| migration head | `0035` | `0035` |

| § | Area | Result |
|---|---|---|
| 1 | Baseline | recorded |
| 2 | TODO/FIXME/HACK | zero markers in own code; 1 stale docstring fixed |
| 3 | Version consistency | manifest matches code; CLAUDE.md fixed |
| 4 | AI provider independence | CLEAN |
| 5 | Legacy LLM isolation | CLEAN, 5 regression tests added |
| 6 | Failed-attempt / cost accounting | 1 real defect fixed, 2 tests added |
| 7 | Idempotency / resume | CLEAN |
| 8 | DB / migrations | CLEAN — 35 revisions, single head, reversible |
| 9 | Guest purchase invariants | CLEAN — 3 tests added |
| 10 | Paddle readiness | analysis written; 2 real gaps found |
| 11 | Frontend contract | CLEAN |
| 12 | Free/paid boundary | CLEAN |
| 13 | Report / DOCX / localization | CLEAN — parity across six locales |
| 14 | Public route / SEO | CLEAN |
| 15 | Security | CLEAN |
| 16 | Config / env | 22 undocumented settings fixed, parity test added |
| 17 | Dead code | 2 items removed |
| 18 | Test quality | no rewrites needed |
| 19 | Full verification | green |
