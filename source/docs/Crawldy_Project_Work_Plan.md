# Crawldy — Operational Working Plan

**Snapshot date:** 2026-09-02 · **HEAD:** `24bb76f` · **branch:** `main` (tree clean)

**What this document is.** The operational continuity plan: what is verifiably
done, what is in progress, what remains, and in what order. It exists so a new
engineer or Claude session can resume work without chat history. It is **not**
the final Architecture & Handoff and **not** the final Product & Technology
Roadmap — both of those are produced later, at the documentation gate (§5).

**Reference hierarchy.**
1. Current repository, migrations and tests — implementation source of truth.
2. This working plan — current stage, order and gates.
3. `docs/Crawldy_Coverage_Reconciliation_2026-08-25.md` — accepted coverage
   reconciliation (historical baseline; its commit/test counts are stale).
4. `Crawldy_Master_Plan_Current_and_Future_2026-08-25.docx` (OneDrive:
   `Desktop/Проекти/Crawldy/`) — historical continuity source. Its "current
   task" (Response HTML vs Rendered DOM), its test snapshot (1,393) and its
   "Presence not implemented" status are **obsolete**; see §2.
5. `Конкуренти_стратегія.docx` (same OneDrive folder) — **primary positioning
   source for the current website block** (§3).

---

## 1. Current verified baseline (2026-09-02)

Verified against the repository at `24bb76f`, not inherited from old reports:

- Backend: **2336 tests passed, 3 skipped**; `ruff` clean; `mypy --strict`
  clean on the configured set. Frontend: focused unit tests
  (`ProviderMark.test.ts`, `payment.test.ts`) + `tsc`/production build green
  as of the provider-identity block.
- Migration head: `0043` (presence attempts ledger).
- Fingerprints: detector `e3f7e1172d70`, scoring `7b16db310137`, prompt
  registry `p0-1`, pricing catalog `da171ea96e25`.
- Presence engine status: **`ACTUAL_AI_PRESENCE_ENGINE_COMPLETE`** (green
  live Vertex smoke 2026-09-02, actual cost $0.036911 vs reserved $0.353323).
- Final live benchmark: **frozen and accepted** (final1, 2026-09-01:
  1,000-site corpus, 957 OK / 43 documented failures, drift median 1,
  `ACCEPTED_WITH_DOCUMENTED_LIMITATIONS`; artifacts on `<WORK_DIR>`).
- Scoring: **frozen** (2026-08-22, commit `7586487`; hreflang family shipped
  later as INFO/weight-0 precisely to honor the freeze).
- Working evidence packet: `backend/benchmark/detector_sweep_packet.json`
  (untracked by design; holds benchmark, commercial, presence and Vertex
  closure records).

## 2. Completed work (historical; do not re-verify from old labels)

Each block below is DONE and verified by tests/commits in this repository.
Old planning documents describing these as "current" or "planned" are stale.

**Audit engine (frozen).**
- Crawler & coverage model: wave-based BFS with a single frontier for all URL
  sources, prefetched entry, uniform sitemap sampling, coverage summary
  (read / fetched / failed / known) next to the score.
- Response/render semantics: `render_diff.py` — field-by-field server-response
  vs rendered-DOM differential with honest "not compared" states; render
  budget doubles as wave fuel for JS-only discovery.
- hreflang & JS-related discovery: `hreflang.py` model + check family
  (INFO/weight-0 under the freeze), JS-only link discovery through render
  waves within `max_pages`.
- Detector calibration: closed via the final1 benchmark; 79+ checks across 6
  modules; per-detector activation analysis and human validation done.
- Passed-check architecture: `app/report/passed.py`, wired through builder,
  DOCX and web serialization.
- Report surfaces: JSON/API + three DOCX variants; **six report locales**
  (`COMPLETE_LOCALES`: EN, DE, ES, FR, RU, UK) with parity tests; 12 UI
  locales for the website (separate authority, unchanged rule).
- Global scoring weights and mechanics: frozen (see §1); the freeze is about
  behavior, not files — weighted checks are also frozen.

**Actual AI Presence (complete — do not reopen).**
- Four providers: OpenAI (Responses API), Anthropic (Messages + web_search),
  Perplexity (Agent API), Google (**Vertex AI**, `gemini-2.5-flash`,
  generateContent, global endpoint; explicit `vertex_ai` / `developer_api`
  backend, no silent fallback).
- Natural/explicit modes in observation identity; strict-majority
  deliverability (4 enabled → any 3 metric-deliverable providers suffice).
- Durable paid-call budget: `presence_attempts` ledger, reservation committed
  before dispatch, defensible per-attempt maxima from documented pricing
  ceilings only, crash/retry/two-process proofs, `COST_BOUND_VIOLATED` halt,
  pricing-version fail-closed.
- Entitlements: subscription→credit order, settle-exactly-once, budget-blocked
  non-deliverable runs release the entitlement.
- Six-locale Presence DOCX; text-only `ProviderMark` treatment with
  non-endorsement notice (official logo assets pending approvals — §9).

**Commercial P0 (implemented).**
- One product — WEBSITE ANALYSIS — accessed as **Free Preview / Single /
  Pack / Monthly** (owner decision, §10).
- `CommercialOffer` (single|pack) with admin configuration; typed credits;
  **Pack credits never expire** (structural: no expiry column);
  **promocodes are Pack-only** (enforced at the admin API).
- Customer billing UI (`app/(product)/app/plan`), checkout, guest free-preview
  → locked result → payment flow.
- Monthly: `Plan`/`Subscription`/entitlement machinery (billing models).
- Paddle: **sandbox integration closed end-to-end** (checkout → webhook →
  entitlement → refund → revocation). **Production Paddle deliberately NOT
  configured** — no live products, prices or credentials exist (§7).

**Public website (exists; current block reviews it — §3).**
- Marketing site: localized catch-all router with ~17 page groups (home,
  about, contact, methodology, website-audit, seo-audit, technical-seo-audit,
  geo-audit, ai-visibility, developers + six `dev-*` deep pages), sitemap,
  robots, metadata plumbing.
- Product app: audits, sites, presence, plan; login/register; result page.

## 3. Current active block

> **PUBLIC WEBSITE COMPLETION + COMPETITIVE POSITIONING + SEARCH/AI
> VISIBILITY** — *awaiting owner approval of this plan before starting.*

Ground rules already decided:
- The website **already exists and is reviewed/improved, not rebuilt**.
- `Конкуренти_стратегія.docx` is the **primary positioning source**: sell the
  outcome ("See where your website is losing visibility — in Search and AI" /
  "Be Seen in Search. Be Found by AI."), progressive disclosure (owner-simple
  first screen, developer drill-down), three clearly separated notions
  (Search Visibility / AI Readiness / Actual AI Presence), pay-per-audit as a
  differentiator against subscription-first competitors, data-backed content
  from the 1,000-site benchmark, honest comparison pages. Supporting files in
  the same folder: `CRAWLDY_VISIBILITY_STRATEGY.md`,
  `CRAWLDY_KEYWORD_INTENT_MATRIX.md`, `CRAWLDY_LOCALIZATION_STRATEGY.md`.
- Audit/scoring/Presence engines are **frozen and outside** this block.
- Actual AI Presence is complete → remove any residual "coming soon"/"we
  intend to build" treatment. Known stale copy found during reconciliation:
  `frontend/app/content/geo-audit/*` ("external mention monitoring is
  something we intend to build") and `frontend/app/content/about/*`
  (mentions "scheduled audits" among things being finished).
- Live offers resolve from the backend commercial API; no retail prices, Pack
  sizes or launch offers are finalized or hard-coded anywhere.
- Provider names stay descriptive text (`ProviderMark`) until official brand
  assets/approvals exist.

**Scheduled-audit conflict (recorded).** `app/scheduling/` and
`app/api/routes/schedules.py` exist historically (phase-4 work). Scheduled
monitoring is **not part of the approved initial product**: it must not be
marketed or exposed as an active subscription benefit unless separately
approved. Do not remove and do not expand it in the website block; the
`about` page wording above must stop implying it as a coming benefit.

## 4. Remaining pre-documentation work (after §3)

Owner-approved order — do not resequence silently:

1. ~~Website completion + competitive positioning~~ → this is §3.
2. **Final product/customer-journey completion review** — one pass over the
   whole funnel (entry → free preview → purchase → report → presence) against
   the reconciliation matrix produced in §3.
3. **Launch commercial decisions** — retail prices, Pack sizes, refund-policy
   wording, launch offer (10 free + 50 at −50% is strategy input, not yet an
   approved offer). Prices are Serhii's decision; nothing is derived.
4. **Production-readiness verification without configuring live Paddle** —
   env/secret audit (key rotation noted in Master Plan §11 remains prudent),
   deployment checklist, live-domain and webhook plans.

*Timing note surfaced, not a resequencing:* Vertex retires
`gemini-2.5-flash` on **2026-10-20** (§9). If launch work extends past that
date without a bounded successor, Google Presence reverts to fail-closed —
plan the launch window with this in mind.

## 5. Final documentation gate

Only after §3–§4 are complete: produce
`docs/Crawldy_Architecture_and_Handoff.md` and
`docs/Crawldy_Product_and_Technology_Roadmap.md` (contents per Master Plan
§16, which remains the accepted specification), plus a `docs/README.md`
index. These two files are not edited before this gate.

## 6. Security-review gate

After documentation: the product goes through an **independent
security/technical review**; approved findings are remediated before any
production launch. Generic vulnerability scanning stays outside the *product*
scope (it is about Crawldy itself, not a customer feature).

## 7. Production-launch gate

Only at this gate: production infrastructure, live Paddle products/prices/
credentials, live checkout domain, live webhook destination/secret, launch
settings. Nothing production-Paddle-related is configured earlier, and no
paid action may become reachable merely because marketing CTAs exist.

## 8. Deferred roadmap (explicitly not now)

Presence P1 (first-party telemetry), recurring monitoring/scheduled audits as
a *product*, alerts, rank tracking, projects-as-product, competitive
tracking/competitor Presence, GSC/Bing external evidence, backlinks,
agentic/WebMCP/UCP, Gemini-successor work, PDF export. Promotion follows the
Master Plan §15 rule (evidence + customer value, not technical possibility).

## 9. Provider/standards watchlist

- **Vertex `gemini-2.5-flash` retirement: 2026-10-20** — provider-lifecycle
  item, *not* unfinished engine work. Rule already in code: if no successor
  with a bounded grounding billing unit exists by then, Google **fails
  closed** (uncomputable attempt maximum opens no paid path). Check monthly.
- Gemini 3.x: per-query grounding billing with no documented query cap —
  stays out of the hard-budget customer path until Google bounds it.
- Provider brand assets: Perplexity/Anthropic/Google require consent or
  approval; OpenAI badge portal was bot-blocked. Until approvals exist, the
  text `ProviderMark` + non-endorsement notice is the shipped treatment.
- AI crawler registry: refresh only from primary vendor sources via releases
  (Master Plan §8 policy unchanged).

## 10. "Do not reopen" decisions

- Scoring weights, half-scales, ceilings, severity multipliers, bands —
  frozen (behavioral freeze, not file freeze).
- Detector set/methodology as accepted by final1; new checks would raise
  `detector` version and require their own evidence pass — none planned now.
- Presence engine: prompts `p0-1`, exactly four providers, modes, metrics,
  strict-majority deliverability, durable ledger, entitlement lifecycle.
- Commercial primitives: Single/Pack/Monthly architecture, permanent Pack
  credits, Pack-only promos, entitlement-gated paid actions.
- One product: WEBSITE ANALYSIS; access forms are not separate products; no
  subscription-only monitoring/alerts/projects/rank tracking in the initial
  release.
- Paddle lessons (checkout.url is the checkout address; default-payment-link
  page initializes on load; fake provider never registers in prod).
- Frozen Search+AI Readiness engine never changes inside product blocks.

## 11. Exact next-task handoff

**Task:** the PUBLIC WEBSITE block (§3), per the owner directive of
2026-09-02 — Part 0 route-by-route reconciliation matrix first, then
competitive review against `Конкуренти_стратегія.docx`, then high-confidence
implementation, visual QA (desktop/tablet/mobile × EN/UK × anon/auth ×
offer/error states), focused tests, full validation, separate commit,
19-point report. **Blocked on:** owner approval of this updated plan.

Start from `main` @ `24bb76f` (or its descendant), clean tree. The engines,
budgets and commercial primitives listed in §10 are read-only context. The
two final documentation files are not to be touched. Working packet
(`backend/benchmark/detector_sweep_packet.json`) stays untracked.
