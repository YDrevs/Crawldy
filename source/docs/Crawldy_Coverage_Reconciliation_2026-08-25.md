# Crawldy Coverage Reconciliation — 2026-08-25

**Status:** accepted. This is the durable reference for subsequent implementation
tasks in the Search + AI Visibility area.

**Baseline document:** `Crawldy_Coverage_Review_2026.docx` (25 Aug 2026).
**Codebase reconciled:** commit `fb71a21` — 68 detectors across 6 modules,
1335 backend tests, 33 frontend tests.

**Why this document exists.** The Coverage Review was written without repository
access; its own §2 says so and asks for exactly this pass. Where the review and
the code disagree, **the code decides implementation status** — but the review is
not discarded: every changed status is explained.

Evidence markers used throughout:

| Marker | Meaning |
|---|---|
| **[code]** | Verified by reading this repository at `fb71a21` |
| **[report]** | Claim carried from the Coverage Review |
| **[ext]** | Externally verified against a primary source on 2026-08-25 |

---

## 0. Accepted clarifications (normative)

These were accepted after the reconciliation and **govern everything below**.
Where an earlier section of the original reconciliation conflicted, it has been
rewritten here.

### 0.1 Actual AI Presence is a core product track

Actual AI Presence — whether a business is genuinely mentioned, cited, linked or
represented in AI-generated answers — is **part of the committed Crawldy
proposition**, not an experimental curiosity. It is not currently implemented
(see §D-5), and that is a real product gap rather than an optional extra.

What remains legitimately experimental is **how presence is measured**: which
providers, which query sets, what sampling, what refresh cadence, and how
uncertainty is expressed. A specific methodology may be swapped or abandoned;
the track may not.

Consequence for planning: AI Presence appears in the committed priority order
(§G), and only measurement methodology appears in the experimental backlog (§H).

### 0.2 Readiness is never proof of presence

**AI crawler accessibility and AI readiness must never be presented, scored or
worded as evidence that a site is actually cited or present in AI answers.**

This is an invariant, not a preference. A site can be perfectly readable and
never cited; a site can be cited despite weak markup. The two are separate
claims with separate evidence:

| Claim | Evidence class | Where it may come from |
|---|---|---|
| "AI crawlers can read this site" | deterministic, anonymous crawl | current engine |
| "This site is cited by AI systems" | observed answers or owner data | AI Presence track, GSC |

The existing engine already respects this — `llm_visibility` findings are worded
as suitability, and the one categorical statement (`llm.crawler_blocked`) is
licensed because a `Disallow` directive was read directly **[code]**. Any new
work must preserve it. Tests already guard the wording
(`test_consequence_does_not_promise_what_we_never_measured`).

### 0.3 The AI crawler registry relies on primary vendor sources

Production entries in the AI crawler registry **must** be sourced from the
vendor that operates the crawler — OpenAI, Anthropic, Perplexity, Google,
Microsoft — and each entry must record the source URL and a verification date.

Third-party aggregators (Cloudflare's bot list, community tables, competitor
documentation) may be used to **discover** that an entry might be missing or
stale. They must not be the recorded source of truth for a production entry,
because they lag, disagree, and cannot be held to the vendor's own semantics.

### 0.4 robots.txt evaluation follows RFC 9309

Robots evaluation targets **RFC 9309** semantics **[ext]**, not ad-hoc string
matching. The rules that matter here, quoted from the RFC:

- **Group selection:** *"Crawlers MUST use case-insensitive matching to find the
  group that matches the product token."* Multiple matching groups *"MUST be
  combined into one group."* With no match, the `*` group applies; with neither,
  no rules apply.
- **Rule precedence:** *"The most specific match found MUST be used. The most
  specific match is the match that has the most octets."* If an `allow` and a
  `disallow` are equivalent, *"the 'allow' rule SHOULD be used."*
- **Special characters:** crawlers MUST support `#`, `$` and `*`.
- **Unreachability:** 4xx ⇒ the crawler MAY access anything; 5xx or network
  failure ⇒ *"the crawler MUST assume complete disallow."* Redirects SHOULD be
  followed at least five hops.

The current parser is materially below this (§D-2). It was built for reporting a
few site-level facts, not for evaluating access, and the gap is now explicit.

### 0.5 `seo.click_depth` is reconciled against graph semantics, not copy

The defect in §D-1 is a **semantic** mismatch, not a wording slip. It must be
resolved by first deciding what the check is meant to assert — and the link
graph already exposes both candidate facts — rather than by rewriting the
customer-facing string to match whatever the code happens to do.

Note the constraint: `code` is an identifier that scoring ceilings and
recommendation grouping key on, and the scoring baseline is frozen since
`7586487`. Changing what the check measures changes findings; renaming it
changes `issue_key`. Both are scoring-visible and need the documented A/B on
snapshots (`rescore_dir.py` before and after).

---

## A. Executive conclusion

- **The review's central verdict holds: Crawldy has no fundamental product gap.**
  Evidence discipline, coverage honesty, page-type applicability and field/lab
  separation are confirmed in code, not merely claimed.
- **About a third of the review's `PARTIAL / VERIFY` entries resolve upward** —
  already implemented — and a few resolve **downward** to genuinely absent.
- **Largest correction upward: internal linking.** A real graph exists with
  incoming/outgoing counts, depth, orphans, links-to-noindex, and a page
  importance score that drives recommendation ordering **[code]**.
- **Largest correction downward: international SEO.** `hreflang` appears nowhere
  in the audit engine. The review saw strong hreflang on Crawldy's own marketing
  site and inferred engine coverage. Real status: **MISSING**.
- **The AI-bot finding is real and demonstrable.** The registry is a flat
  hardcoded tuple with no purpose model, and **[ext]** it is missing
  `Claude-SearchBot`. Anthropic states that disabling it prevents indexing of
  the content for search, which **may reduce visibility and accuracy** in
  Claude's search results — the vendor supports no stronger claim, and neither
  do we. A site blocking it received **no finding at all**: a false negative on
  the flagship claim.
- **Response-vs-render is PARTIAL and cheaper to close than assumed** — both
  parses already coexist per URL; only a text-volume delta is consumed.
- **A gap the review missed entirely: JS-only links are never discovered.**
  Render runs after crawl and the frontier reads static links only.
- **The review's flagship governance example is a false alarm.** Google's FAQ
  retirement does not misfire in Crawldy, because `ai.schema.faq` is framed as
  LLM citability, never as a Google rich result. The registry gap is real in
  principle; this instance is not evidence of it.
- **Actual AI Presence is absent and is a committed gap** (§0.1). Nothing in the
  product currently overstates it — no subsystem exists and the enrichment layer
  makes no presence claims **[code]**.
- **One genuine P0, not on the review's list:** `seo.click_depth` measures
  *outgoing* links while telling the customer *"Almost nothing links to this
  page."*

---

## B. Reconciliation matrix

Statuses: **IMPLEMENTED**, **PARTIAL**, **MISSING**, **OBSOLETE**,
**EXPERIMENTAL/DEFER**, **OUT OF SCOPE**.

| Area | Report finding | Status | Code/test evidence | What remains |
|---|---|---|---|---|
| Crawlability / status / robots | FULL | **IMPLEMENTED** | `crawler.py`; `fetcher.py`; `site_context.collect_robots`; `seo.robots_txt`; `tech.crawler_blocked` (reads `ctx.pages`, survives blind crawls) | — |
| URL normalization | FULL | **IMPLEMENTED** | `logical_pages.normalize`; `page_kinds.path_words`; facet-param folding | — |
| Redirect chains / loops | PARTIAL / VERIFY | **MISSING (detector)** | `RedirectHop`, `PageSignals.redirect_chain` (`types.py:204`), `fetcher.py:181–208`, `max_redirects=5`. **No check reads either** | Detector only; data ready |
| Canonicalization | FULL / VERIFY edges | **IMPLEMENTED**; pre/post-render **MISSING** | `seo.canonical` (missing, mismatch); `tech.host_canonical`; `logical_pages` | Canonical compared across render |
| robots vs noindex contradiction | FULL / VERIFY | **PARTIAL** | `seo.noindex` page-type aware, `Confidence.MEDIUM`; `seo.links_to_noindex` | Sitemap-URL vs robots-disallow contradiction |
| Sitemaps | PARTIAL | **PARTIAL** | `seo.sitemap` (missing, invalid, empty, coverage); `seo.sitemap.lastmod` | Cross-check vs noindex / redirect / status |
| Image, video, news sitemaps | LIKELY MISSING | **MISSING** | No `image:image` / `video:video` / `news:news` handling | Vertical-specific; low value |
| Internal link graph | PARTIAL / VERIFY | **IMPLEMENTED** | `link_graph.py` — incoming, outgoing, depth, orphans, to_noindex; `importance()` → `builder.py:244`; `orchestrator.py:196,204`; 16 tests | Anchor text captured (`LinkRef.anchor`) but unanalyzed |
| Orphan pages | REQUIRES OWNER DATA | **IMPLEMENTED** | `seo.orphan_pages`; sitemap as independent source; gate `SITEMAP_COVERAGE_FOR_ORPHANS = 0.5` (`seo.py:664`) | Review understated: sitemap *is* a second source |
| Broken internal links | PARTIAL | **PARTIAL** | `seo.broken_links` (`seo.py:446`) lists 4xx/5xx URLs | Not attributed to the linking page; only crawled URLs |
| Crawl waste / parameter traps | PARTIAL / VERIFY | **PARTIAL** | `logical_pages` folds facet params | No dedicated trap diagnostics |
| **Raw HTML vs rendered DOM** | PARTIAL / LIKELY GAP | **IMPLEMENTED** (`3586e9c`) | `render_diff.py` compares meta_robots, canonical, title, h1, meta_description, JSON-LD and internal-link sets semantically; `seo.render_delta` reports it (INFO, weight 0); shared with `llm.client_rendered` | Scored severity — deferred, see §I-7 |
| Rendering failures / resources | PARTIAL | **IMPLEMENTED** | `render/base.NullRenderer`; `LAYER_DISABLED` vs `PROVIDER_UNAVAILABLE`; `asyncio.wait_for`; 10 tests | — |
| **JS-only link discovery** | *not raised* | **MISSING** | Crawl `orchestrator.py:183` → render `:190`; frontier uses static `page.links` (`crawler.py:90,122`) | Real gap |
| Mobile / device behaviour | PARTIAL | **PARTIAL** | `perf.mobile_gap`; PSI strategy in evidence | No structural mobile-vs-desktop comparison |
| Titles / meta / H1 | FULL | **IMPLEMENTED** | `seo.title`, `seo.meta_description`, `seo.h1`, `seo.heading_hierarchy`; page-type aware | — |
| Duplicate / near-duplicate | PARTIAL | **PARTIAL** | `seo.title.duplicate` (exact titles); `logical_pages` variant folding | No similarity engine |
| Helpful / people-first content | NON-DETERMINISTIC | **OUT OF SCOPE** (correct) | `app/enrich/` qualitative only, disabled by default | — |
| Structured-data syntax | FULL | **IMPLEMENTED** | `ai.jsonld.invalid` + `no_type`; `jsonld_errors` | JSON-LD only; no Microdata/RDFa |
| Structured-data semantic truth | PARTIAL | **PARTIAL (narrow)** | `tech.nap.schema_mismatch` — JSON-LD `telephone` vs `tel:` links; one property | General visible-content consistency |
| Google rich-result eligibility | PARTIAL / RISK | **MISSING (by design)** | No feature-eligibility tier; schema framed as AI citability | Product decision — see §I-1 |
| Schema.org entity graph | PARTIAL-STRONG | **IMPLEMENTED** | `ai.schema.organization`, `ai.entity.sameas`, `ai.schema.graph`, `site_facts.py` | — |
| **hreflang** | PARTIAL / VERIFY | ~~MISSING~~ **IMPLEMENTED** | `standards/language_tags.py` + `hreflang.py` + 5 detectors; HTML, `Link` header and sitemap all collected | Closed — see D-6 |
| Language declaration / detection | PARTIAL / VERIFY | **PARTIAL** | `extractor.py:168` reads `lang`; `ai.lang` checks presence | Declared-vs-detected conflict |
| Field Core Web Vitals | FULL | **IMPLEMENTED** | `result.field_data`; evidence `"source": "field"`; `Confidence.HIGH` | — |
| Lab performance | FULL | **IMPLEMENTED** | Lighthouse/PSI; `Confidence.MEDIUM` for lab | — |
| Field vs lab separation | FULL | **IMPLEMENTED** | `performance.py:70` suppresses lab TBT when field INP exists; `:93–100` | Exemplary; preserve |
| Resource weight / third-party | PARTIAL-STRONG | **IMPLEMENTED** | `perf.third_party`, `perf.page_weight`, `ResourceLoad.is_third_party` | — |
| Caching / compression / protocol | PARTIAL | **PARTIAL** | `tech.caching` | No compression or HTTP-version findings |
| Accessibility (automated subset) | FULL for subset | **IMPLEMENTED** | `a11y.blocking` / `a11y.failures`; axe via Lighthouse; contrast excluded with recorded rationale | — |
| "Never claim WCAG conformance" | P0 wording | **IMPLEMENTED** | `a11y.failures` description: *"Nobody verifies full standard compliance automatically"* | Already correct |
| ACT Rules mapping | MISSING | **MISSING** | No WCAG/ACT identifiers; axe IDs present in evidence | Mapping table only |
| Keyboard / manual a11y | OUT OF SCOPE | **OUT OF SCOPE** (correct) | Limitation stated in copy | — |
| TLS / HTTPS | FULL / VERIFY | **IMPLEMENTED** | `seo.https` (missing, invalid_cert, no_hsts); `ctx.tls_error`; `reads_content=False` | — |
| Security headers | FULL-STRONG | **IMPLEMENTED** | `SECURITY_HEADERS` (`tech.py:26`): CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy | Hardcoded tuple → registry |
| Mixed content | PARTIAL / VERIFY | **MISSING** | No detection | Small, cheap |
| Security beyond basics | OUT OF SCOPE | **OUT OF SCOPE** (correct) | — | Keep boundary |
| **AI search crawler access** | PARTIAL / VERIFY BOT LIST | **IMPLEMENTED** (`11f865e`) | `standards/ai_crawlers.py` — 12 entries with vendor/purpose/source/`last_verified_at`; `robots.py` RFC 9309 evaluator; purpose-aware `llm.crawler_blocked.*`; 53 tests | Severity by purpose — deferred, see §I-3 |
| AI training crawler control | STRATEGY EXISTS | **IMPLEMENTED** (`11f865e`) | `CrawlerPurpose.TRAINING`; wording states refusal is a legitimate choice, not a defect | Same severity note |
| WAF / CDN AI-bot blocking | PARTIAL / HARD TO PROVE | **MISSING** | No UA-varied probing | Requires explicit uncertainty labelling |
| AI citability / readability | FULL-STRONG | **IMPLEMENTED** | `llm_visibility` (10 checks); reads static HTML by design | — |
| llms.txt | INFO ONLY | **IMPLEMENTED** | `ai.llms_txt`; LOW severity, weight 1 | Correct weight |
| **Actual AI presence** | FUTURE PROVIDER | **MISSING — committed track** (§0.1) | No subsystem; enrichment = 3 tasks, none about presence | Build the track; methodology experimental |
| Google AI visibility (GSC) | REQUIRES OWNER DATA | **MISSING** | Only `google-site-verification` meta (`extractor.py:97`) | Owner-data evidence tier |
| Bing / Copilot grounding | REQUIRES OWNER DATA | **MISSING** | — | After GSC |
| AI referral traffic | REQUIRES ANALYTICS | **MISSING** | — | Analytics tier |
| Agentic browsing / WebMCP | MISSING / NEW | **MISSING** | No agentic, WebMCP or accessibility-tree handling | Experimental (§H) |
| IndexNow | NOT DETECTABLE | **MISSING** | — | Contextual only |
| Search Console integration | MISSING | **MISSING** | — | Separate evidence tier |
| Backlinks / rankings | OUT OF SCOPE | **OUT OF SCOPE** (correct) | — | External provider if ever |
| Coverage honesty | FULL after v2 | **IMPLEMENTED** | `builder._coverage` (`:497`); `_temper_by_coverage`; `_only_what_we_saw` (`:55`) | — |
| Page/site-type applicability | FULL-STRONG | **IMPLEMENTED** | `page_kinds.type_of`; `NOT_FOR_SEARCH`; `PageType.DOCS` | — |
| **Standards freshness registry** | PARTIAL / KEY GAP | **MISSING** | `versions.py` versions the *engine* (`detector_version`, `SCORING_RULES`, `config_version`) — history comparison, not capability governance | Real gap; cited example is a false alarm |

---

## C. Report findings now obsolete

1. **"Internal-link graph metrics not confirmed."** Superseded — full graph plus
   importance-weighted prioritization.
2. **"Orphan detection requires owner data for a strong result."** Superseded —
   the sitemap is the independent source, with a 50 % coverage gate so the claim
   describes the site rather than the crawl budget.
3. **"P0: keep accessibility claims automated-only."** Already true; the copy
   explicitly disclaims automated conformance.
4. **"FAQ retirement shows why the registry cannot live in code comments."** The
   conclusion stands; the evidence does not. `ai.schema.faq` never promised a
   Google rich result.
5. **"Verify field vs lab separation."** Fully implemented, including the subtle
   suppression of lab TBT when field INP exists.
6. **"Coverage honesty FULL after v2 fixes."** Confirmed, and stronger than
   described: `_only_what_we_saw` also suppresses content claims on blind crawls.

---

## D. Real remaining gaps

### D-1. P0 — `seo.click_depth` asserts the opposite of what it measures

**Detected.** The check counts *outgoing* internal links
(`sum(1 for link in page.links if link.is_internal) < 3`, `seo.py:569–577`).
The customer-facing consequence reads *"Almost nothing links to this page:
search engines visit it rarely and treat it as secondary"* — a statement about
*incoming* links. The recommendation ("Add contextual links to related pages")
matches the measurement; the description and consequence do not.

**Customer impact.** A well-linked page with few outbound links is told nobody
links to it — a claim Crawldy's own `graph.incoming` can disprove.

**Current limitation.** The graph holds both facts; the check uses neither.

**Direction.** Per §0.5, decide the intended assertion first — isolation by
inbound links (use `graph.incoming`) or thin outbound linking (keep the
measurement, rewrite the copy) — then align code, copy and identifier together.
Treat as scoring-visible: run the snapshot A/B before and after.

**Priority: P0.** It is the only item that makes a shipped report untrue.

### D-2. ~~P1~~ RESOLVED in `11f865e` — AI crawler registry and RFC 9309

**Detected.** `AI_USER_AGENTS` is a flat tuple of 11 lowercase strings
(`site_context.py:15–27`) with no purpose classification, no source and no
verification date. Blocking is recognised **only** for a literal `Disallow: /`
(`:62–68`); `Allow` is never parsed; wildcards `*`/`$` are unsupported; path-
scoped disallows are invisible; 5xx robots is treated as "no rules" where
RFC 9309 requires assuming complete disallow **[ext]**.

**[ext]** Anthropic currently operates three distinct tokens — `ClaudeBot`
(training), `Claude-User` (user-directed retrieval) and `Claude-SearchBot`
(search indexing). Crawldy's list carries `claudebot`, `claude-web` and
`anthropic-ai`; the latter two are legacy, and **`Claude-SearchBot` is absent**.
`Perplexity-User` is likewise absent.

**Customer impact wording.** Anthropic's supportable claim is that disabling
`Claude-SearchBot` prevents indexing for search and so may reduce visibility
and accuracy in Claude's results. It does not license "decides whether Claude
may cite you", and the readiness ≠ presence boundary (§0.2) forbids it.

**Customer impact.** A site blocking `Claude-SearchBot` — precisely the control
over whether Claude may cite it — gets silence. This is a false negative on the
capability Crawldy sells.

**Current limitation.** One finding, "N AI crawlers are blocked", cannot
distinguish a deliberate training opt-out (legitimate, common, often
deliberate) from a search-crawler block (usually accidental, directly costly).

**Direction.** A versioned registry keyed by
`(vendor, token, purpose ∈ {search, user, training}, source_url, last_verified_at)`
populated from **primary vendor sources only** (§0.3), with robots evaluation
raised to RFC 9309 semantics (§0.4), and the finding split by purpose.

**Resolved 2026-08-25 in `11f865e`.** Registry holds 12 primary-source verified
entries across OpenAI, Anthropic, Perplexity, Google and Meta; four tokens were
retired with recorded reasons (`claude-web`, `anthropic-ai` — superseded by the
vendor; `ccbot` — Common Crawl documents itself as an open archive, so no
purpose in the taxonomy is primary-source supported; `bytespider` — ByteDance
publishes no reachable documentation at all). `app/audit/robots.py` implements
RFC 9309 group selection, merging, `*`/`$`, longest-match and allow-wins ties.
Findings are now purpose-specific and path-scoped. **Scoring unchanged** —
one finding per audit, identical severity and weight. Splitting into
`variants` by purpose would give each its own penalty ceiling, so it is
deferred to the calibration phase (§K.4).


### D-2a. Source-semantics correction (`8a86a44`)

Three claims in the first implementation went beyond what the vendors
document. Corrected on 2026-08-25, re-verified against primary sources:

**`Perplexity-User` is not evaluated through the robots path.** Perplexity
documents: *"Since a user requested the fetch, this fetcher generally ignores
robots.txt rules."* Treating a `Disallow` for it as a block would contradict
the vendor. `AiCrawler.obeys_robots` now carries this; the crawler is excluded
from blocking findings and from `RobotsInfo.blocked_ai_agents`. The directive
is still recorded under `evidence.directives_ignored_by_vendor` — factual, not
a finding — because an owner may believe they closed that door. Its sibling
`PerplexityBot` is expected to respect robots.txt and is unaffected.

**`Google-Extended` is not purely a training control.** Google documents it as
governing *both* training of future Gemini models *and* grounding — *"providing
content from the Google Search index to the model at prompt time to improve
factuality and relevancy"* — while stating it *"does not impact a site's
inclusion in Google Search nor is it used as a ranking signal."* Classifying it
as TRAINING alone discarded the half that actually costs visibility.
`CrawlerPurpose` gains `GROUNDING`, and `AiCrawler.purpose` becomes
`purposes: tuple[...]` so one token can carry both — the smallest structurally
correct change. A new `llm.crawler_blocked.grounding` message is scoped to what
Google establishes: the token controls whether **content Google crawls** may be
used for grounding **in Gemini Apps and Vertex AI**, it says nothing about other
assistants, and it **explicitly denies any Google Search effect**. An earlier
draft said "an assistant may not draw on your pages" — unbounded across
assistants and stated as fact; tightened in the follow-up wording commit. A guard test fails if a
non-Google grounding token is ever added, since the copy names Google surfaces.

**Priority order** is now SEARCH → GROUNDING → USER_INITIATED → TRAINING.
Scoring is unchanged: one finding per audit, same severity, weight, effort and
absent `variants`.

### D-3. ~~P1~~ RESOLVED in `3586e9c` — response-vs-render differential

**Detected.** Both a static `PageSignals` and a rendered re-parse
(`RenderResult.signals`) exist per rendered URL — the docstring at
`types.py:426` names the difference "the SSR delta". Only one differential is
consumed: `visible_without_js()`, a text-volume ratio feeding
`llm.client_rendered`.

**Customer impact.** The classic JavaScript-SEO failures are invisible: a
canonical or `meta robots` injected by script, structured data added after
hydration, links that exist only in the rendered DOM.

**Current limitation.** No field-by-field comparator exists.

**Direction.** A comparator over the two `PageSignals` covering title, meta
description, canonical, meta robots, `lang`, H1, internal links and JSON-LD
types. Detector layer only; testable offline against stored snapshots.

**Resolved 2026-08-25 in `3586e9c`.** `app/audit/render_diff.py` is a reusable
comparator returning a `RenderDiff` (`FieldDelta` with `added`/`removed`/
`changed` direction, plus a `LinkDelta` holding both link directions). It
compares semantically — robots directives as sets, URLs through
`logical_pages.normalize`, JSON-LD as a set of `@type`/`@id`, links as sets — so
reordering, whitespace and formatting produce no finding. Insufficient
comparison quality (`render.disabled`, `render.failed`, `render.no_signals`,
`render.not_attempted`, `response.not_ok`) yields `comparable=False` with a
named reason and no finding: a renderer failure is never reported as a fact
about the site. Snapshots already carried both signal sets, so replay
reproduces the differential with **no migration and no re-rendering**.

`lang` was left out: it is a one-field addition that belongs with the hreflang
item rather than duplicating language work across two tasks.

### D-4. P1 — JavaScript-only links are never discovered

**Detected.** The pipeline crawls (`orchestrator.py:183`) and *then* renders
(`:190`); the crawl frontier reads static `page.links` (`crawler.py:90,122`).

**Customer impact.** A client-rendered SPA yields a one-page crawl. Coverage is
reported honestly and `llm.client_rendered` fires CRITICAL, so the customer is
not told the site is fine — but the audit is thin precisely where it matters.

**Direction.** Feed links from rendered pages back into the frontier for the
rendered subset, budget-capped. Touches pipeline ordering; sequence after D-3.

### D-5. P1 — Actual AI Presence track does not exist

**Detected.** No subsystem: no presence, citation, mention or answer-engine
module anywhere in `app/` **[code]**. The enrichment layer runs
`site_understanding`, `root_cause_grouping` and `remediation_plan` — none makes
presence claims — and is disabled by default.

**Customer impact.** Crawldy can currently answer "is this site readable by AI
systems" but not "is this business actually showing up in AI answers", which is
the question owners ask first.

**Current limitation.** Nothing overstates it today, which is the right starting
position (§0.2) — but the gap is real and committed (§0.1).

**Direction.** A separate evidence tier with its own provenance, distinguishing
*presence*, *citation*, *mention* and *sentiment* as different observations,
retaining raw evidence per observation, and expressing sampling uncertainty.
Measurement provider and query methodology remain experimental (§H); the tier,
its contracts and its separation from readiness do not.

### D-6. ~~P1~~ RESOLVED — hreflang / international SEO

**Detected.** Zero occurrences in `app/audit` or `app/report`.

**Customer impact.** For a product shipping in six languages and selling into
multilingual markets, international customers received no signal at all.

**Delivered.**

*Standards registry* — `app/audit/standards/language_tags.py` carries ISO 639-1
(184), ISO 15924 (39) and ISO 3166-1 Alpha 2 (249) with `SOURCES`,
`LAST_VERIFIED_AT` and a `registry_problems()` self-check, matching the
`ai_crawlers.py` pattern. The grammar validated is **Google's**, not BCP 47 in
full: `language[-script][-region] | x-default`, in that order. Script subtags are
first-class — `zh-Hant`, `zh-Hans`, `zh-Hans-US` are valid, exactly as Google's
own examples state. A language-and-region-only validator would have rejected all
three. `TagProblem` names each failure separately (`separator`, `unknown_region`,
`region_as_language`, `order`, `unknown_script`, `not_a_language`, `malformed`,
`empty`) because each implies a different instruction to the customer.

*Three equivalent mechanisms.* Google calls HTML, the HTTP `Link` header and the
XML sitemap equivalent, so all three are collected and merged:

| Mechanism | Where captured |
|---|---|
| `<link rel="alternate" hreflang>` | `extractor._extract_head`, beside canonical, before the destructive `_extract_text` |
| `Link:` header (RFC 8288) | `extractor._hreflang_from_header`, read **before** the non-HTML early return so a PDF can declare its versions |
| `xhtml:link` in the sitemap | `site_context._parse_sitemap`, now structural per `<url>` rather than a flat `loc` sweep |

A site that declares correctly in the sitemap alone therefore produces **no
warning** — the specific false positive this item was raised to prevent, fixed
and pinned by `test_a_site_that_declares_only_in_the_sitemap_is_not_warned`.

*Script registry — corrected after review.* The first version carried 39 script
codes chosen by hand as the ones that "actually occur", with no source and no
rule. Audited against the ISO 15924 Registration Authority
(`unicode.org/iso15924/iso15924.txt`), **187 of 226 codes were missing** —
including `Aran` (Nastaliq), `Tfng` (Tifinagh), `Syrc`, `Bopo`, `Java`, `Sund`.
A customer writing the correct `ur-Aran` or `zh-Bopo` would have been told the
value was invalid: a false positive on correct markup, the most expensive
mistake this product makes. The list is now a vendored snapshot of all 226
registry codes with `ISO_15924_SOURCE`, `ISO_15924_AMENDED` (2025-04-24),
`ISO_15924_RETRIEVED` and `ISO_15924_COUNT`; `registry_problems()` fails on
silent truncation. Nothing is fetched at audit runtime.

Cross-checked independently against the IANA Language Subtag Registry
(File-Date 2026-08-08): 224 script subtags plus the `Qaaa..Qabx` private-use
range whose two endpoints the RA file lists individually — 224 + 2 = 226. Two
sources agree.

The same audit cleared the other two lists but was not silent about them.
**ISO 639-1**: our 184 matches IANA's 184 current codes exactly; the 6 codes
IANA marks deprecated (`in`, `iw`, `ji`, `jw`, `mo`, `sh`) are now accepted and
flagged `deprecated` in evidence, because telling a customer `iw` is invalid is
the same false positive as rejecting `ur-Aran`. No new message — evidence is
data, not copy. **ISO 3166-1**: 249 officially assigned alpha-2 codes, and
unlike the scripts this *was* a deterministic rule. IANA additionally carries 12
exceptionally-reserved codes (`EU`, `UN`, `AC`, `DG`…) and 11 withdrawn ones
(`AN`, `SU`, `YU`…). Whether Google accepts `en-EU` for targeting is a product
judgement, not a registry lookup, so it is recorded in §K.4 rather than decided
here.

*Normalised model* — `app/audit/hreflang.py`. `Annotation` carries the parsed
tag, the normalised target, the raw href and the **set of sources** that
declared it: the same pair declared in two places is one annotation with two
sources, not a duplicate. `Declaration` answers self-reference; `Map` answers
conflicts and reciprocity. No severity and no customer string live here.

*Detectors* — five codes, all `Module.SEO`, all silent on a site that declares
nothing:

| Code | Variants | Shipped | Provisional weight (§K.4) |
|---|---|---|---|
| `seo.hreflang_invalid` | — | INFO / 0 | MEDIUM / 2 |
| `seo.hreflang_reciprocity` | `self`, `return` | INFO / 0 | MEDIUM / 2 |
| `seo.hreflang_conflict` | `duplicate`, `x_default`, `canonical` | INFO / 0 | MEDIUM / 3 |
| `seo.hreflang_broken` | `unreachable`, `noindex` | INFO / 0 | MEDIUM / 2 |
| `seo.hreflang_missing` | — | INFO / 0, `Confidence.MEDIUM` | LOW / 2 |

**Coverage-aware by construction.** `Reciprocity` carries `targets_checked`,
`targets_declared` and `coverage_complete`; a target outside the crawl is never
called missing, and the customer-facing sentence states how much of the set was
opened. `seo.hreflang_broken` speaks only about addresses the crawler actually
requested — status codes and `noindex` we read ourselves.

**`x-default` is optional.** Its absence is never a finding; only two
*conflicting* x-defaults are. An `x-default` pointing at the page does not count
as that page's self-reference — it means "come here when nothing matched".

**Two defects found by verification, not by tests.**

1. *Stale snapshots claimed absence.* Replaying the 56 benchmark snapshots fired
   `seo.hreflang_missing` on MDN and FastAPI — not because those sites lack
   hreflang, but because the snapshots predate the field. That is our own gap
   reported as the site's. `SiteContext.hreflang_observed` now records whether we
   could have seen a declaration; `snapshot.load` sets it `False` when the stored
   pages lack the key, and the check stays silent. Snapshot schema → `"2"`.
2. *One template mistake cost three issue keys.* On `fastapi.tiangolo.com` all
   thirteen language variants are labelled `hreflang="en"` — a real mkdocs-material
   misconfiguration. It fired `conflict:duplicate`, `reciprocity:self` and
   `reciprocity:return` for a single edit. A set Google may discard wholesale
   cannot also be judged for completeness, so reciprocity now skips a page whose
   declarations contradict themselves.

   **Correction to the numbers first reported here.** The original entry read
   "SEO 62 → 53" as the result of the suppression. That put the *baseline* on the
   left of an arrow describing the *suppression*, and the direction it implied
   was wrong. Measured on one snapshot, all three states:

   | State | Findings | hreflang issue keys | SEO | Overall |
   |---|---|---|---|---|
   | A — detectors absent | 104 | — | 62 | 63 |
   | B — weighted, before suppression | 123 | 19 across 3 keys | 45 | 60 |
   | C — weighted, after suppression | 115 | 11 across 1 key | 53 | 62 |

   The suppression moved SEO **45 → 53**, upward, as removing duplicate penalties
   must. A → C was the −9 net cost of the capability. No scoring defect; a
   reporting error, and the reason the numbers are now given as a state table
   rather than a sentence.

**Unrelated regression surfaced and fixed.** `RobotsInfo.parsed` (added in D-2)
was never wired into the snapshot; `json.dumps(default=str)` silently stored the
string `"RobotsFile(groups=[...])"`, and replaying a *fresh* snapshot crashed in
`llm.ai_crawler_access` with `'str' object has no attribute 'evaluate'`. `parsed`
is now derived from `content` on load rather than stored, and
`test_a_snapshot_is_plain_json_without_a_stringifying_fallback` dumps without the
`default=str` crutch so the next such object fails at the test, not on live data.

**Scoring — corrected after review.** The first version of this work shipped the
family with real weights and argued the baseline was preserved because
`scoring.py` and `SCORING_RULES` were untouched. That argument was wrong: adding
weighted detectors changes scoring *behaviour* even when the scoring *engine* is
unchanged, and state C above proves it — the same site scored 62 before and 53
after, with nothing changed on the site. Two audits either side of the release
would have been incomparable, which is what the freeze exists to prevent.

The family is therefore **`Severity.INFO`, `weight = 0`** until the §K.4
calibration phase — the compromise already accepted for `seo.render_delta`
(§I-7), for the same reason. Verified across all 56 benchmark snapshots and the
FastAPI snapshot: **zero score movement**. `fastapi.tiangolo.com` now reports 11
hreflang findings at SEO 62 → 62, overall 63 → 63.

Nothing else was given up. Detection, evidence, recommendations, grouping,
prioritisation, all six locales and both report formats are unchanged; the
recommendation still appears in the full list with complete evidence, and is
excluded only from "What to do first", which is where INFO belongs. The
provisional weights are recorded in §K.4 as calibration input: what this should
cost is a decision to take on a distribution, not on one multilingual site.

**Verification.** 1482 tests green; `ruff` clean; `mypy --strict` clean across
all seven packages. `tests/test_hreflang.py` carries 39 cases (50 with
parametrisation) covering grammar, all three mechanisms, source merging, every
detector with its silent counterpart, coverage limits, snapshot round-trip and
both defects above. All nine catalogue keys exist in all six `COMPLETE_LOCALES`
and are exercised by synthetic contexts in `test_i18n.py`. Report output verified
end-to-end on a live snapshot in `en`, `uk` and `de`.

**Live validation, three multilingual sites.** The benchmark corpus predates the
field and contributes nothing here, so the detectors were run against fresh
crawls:

| Site | Pages | Declaring | Annotations | Sources | Findings |
|---|---|---|---|---|---|
| `mozilla.org` | 10 | 8 | 343 | HTML | none |
| `about.gitlab.com` | 10 | 10 | 134 | HTML + sitemap | none |
| `fastapi.tiangolo.com` | 11 | 11 | 143 | HTML | 11 × `conflict:duplicate` |

Silent on both correctly-configured sites and firing only on the genuine defect —
the shape a detector should have. GitLab exercises the HTML + sitemap merge on
production data. 93 distinct hreflang values across the three, all valid.

**Honest limit on the registry evidence.** None of those 93 values used a script
subtag, so the 39-code list would not have produced a false positive on this
sample. The defect was established by comparison against the registry
(187 of 226 missing) and by direct parse tests, not by an observed live failure.
It is latent, and it would surface on exactly the publishers most likely to use
hreflang carefully at scale — CJK, South Asian and Arabic-script sites writing
`zh-Bopo`, `ur-Aran`, `su-Sund`.

### D-4. ~~P1~~ RESOLVED — JavaScript-only internal link discovery

**Detected.** The pipeline ran `crawl()` to completion, closed the fetcher in a
`finally` block, and only then rendered. Three separate reasons made
rendered-only links unreachable, and any one of them was sufficient:

1. **Ordering** — render was a phase strictly after the crawl.
2. **Lifetime** — `fetcher.aclose()` ran *before* `_render_pages`, so at render
   time there was no HTTP client left to fetch anything with.
3. **Scope** — the frontier (`queue`, `seen`) were locals inside `crawl()`,
   discarded on return. Nothing survived to be added to.

**Customer impact.** A client-rendered site whose response HTML carries no
internal links was crawled as a one-page site, and every content check then
described that single page as if it were the whole site.

**Integration point chosen.** The smallest correct one: extract the queue and
its admission rules into `app/audit/frontier.py`, let `crawl()` accept a
frontier so it can be called again, and move the render phase inside the
fetcher's lifetime. No second crawler, no second comparator, no rendered-link
filtering stack — `Frontier.offer()` is the single door every URL passes,
whatever found it.

**Wave loop and termination.** `_render_and_discover` repeats: render what is
not yet rendered → take `RenderDiff.links.only_after_render` → offer to the
frontier → crawl what was admitted. It stops on the first of:

| Condition | Where |
|---|---|
| Nothing left to render within budget | `_render_targets` returns empty |
| Renderer unavailable or disabled | `_render_batch` returns `False` |
| No new eligible rendered-only URL | `_links_only_after_render` returns 0 |
| Page budget exhausted | `len(ctx.raw_pages) >= max_pages` |
| Crawl wave returned nothing | `if not pages` |
| Safety limit | `MAX_DISCOVERY_WAVES = 5` |

**Budget model — one page budget, unchanged.** Render-discovered pages spend the
same `max_pages`; there is no second budget. The render budget
(`render_max_pages`, default 3) keeps its original meaning — a small sample
answering "is the content visible without JS" — and doubles as the fuel that
bounds the waves. The two fit together without special-casing: a static site
spends all three renders in wave 0 and has nothing to discover, while a SPA has
one page in wave 0 and therefore still has fuel. The feared failure — SPAs
losing every page slot before discovery — does not occur, because a SPA's static
crawl ends far *under* budget, not over it.

**Provenance.** `PageSignals.discovered_via` carries `entry` / `response` /
`sitemap` / `render`, merged when several apply and merged again when logical
grouping folds two URLs into one page. `Source.RENDER` means exactly what
`only_after_render` means — absent from the response — so a URL present in both
stays `["response"]`: in the DOM it did not appear, it merely remained.

**Filtering.** One gate, `Frontier.eligible()`: scheme, same-origin,
non-page extensions, robots. `nofollow` stays on the link rather than the URL,
since the same page named elsewhere without it should still be crawled.

**Robots — a gap this work closed rather than inherited.** The crawler enforced
robots.txt nowhere: not for rendered links, and not for static ones either.
Adding it only for rendered URLs would have been precisely the duplicate rule
set the frontier exists to prevent, so it went into the shared door and applies
to everything. Cost measured before committing to it: **2 pages out of 950
across the 47 corpus sites with a non-empty robots.txt.**

**Link graph.** `build()` now unions each page's response links with its
rendered links where a render exists. Without this a render-discovered page
would carry zero incoming edges and read as an orphan — while we had seen the
link with our own eyes. Depth reflects the path actually taken.

**Scoring.** No constant, weight, severity or normalisation touched;
`scoring_version()` stays `3fdd28054fda` and no detector attribute changed.
Replaying all 56 benchmark snapshots produced **zero** changes to scores or
finding sets — the graph union uses information those snapshots already
contained. Scores will move on live audits, and only because Crawldy now reads
pages it previously never fetched: observational improvement, not a rule change.

**Snapshots.** `discovered_via` round-trips; old snapshots load and report `[]`,
which honestly means "unknown", never "static". `raw_pages` is crawl-time
bookkeeping and is deliberately excluded from the snapshot — the grouped pages
are already stored, and keeping the raw list too would store one truth twice.
Replay can re-run the comparator and every detector; it cannot retro-crawl a URL
that was never fetched during that audit, and does not pretend otherwise.

**`seo.render_delta` unchanged.** No second finding says what it already says.
Its evidence gained one field — `links.only_after_render_crawled` — answering
the question the finding raises: of the links that appear only after rendering,
how many did we then actually read. No new message, no locale change.

**Two defects found by the live run, not by the tests.**

1. *The entry page vanished from every real audit.* The condition deciding
   whether to absorb the prefetched home page was "was a frontier passed?" —
   and production passes one always. `excalidraw.com` returned **0 pages, 0
   failures**. Every fixture test passed, because fixtures passed
   `prefetched=None`. Now the condition is "have we already fetched the entry",
   and `test_a_prefetched_entry_survives_being_given_a_shared_queue` pins the
   production combination specifically.
2. *Recording provenance ordered a second fetch.* `offer()` records the source
   even for a known URL, but it also enqueued — so naming the already-downloaded
   home page queued it again. `offer()` now refuses to queue anything already
   fetched, not merely anything already seen.

**Live validation.** `auditlensapp.com`: **8 pages before, 12 after**, four
reached only through rendering — `/contact`, `/auth`, `/privacy`, `/terms`.
Three of those four are pages that trust and contact checks look for and
previously could not find. Across the corpus, 18 of 56 sites carry links that
exist only after rendering.

**Deliberately deferred.** Interactive discovery — clicking menus, infinite
scroll, form submission, tab switching, authenticated journeys — is out of
scope and remains so. Discovery here reads link signals the renderer already
captured; it does not drive the page.

### D-7a. ~~P2~~ RESOLVED — redirect chains, loops and destination quality

**What already existed.** `RedirectHop` and `PageSignals.redirect_chain` were
collected and stored, and no detector read them. Verified before writing
anything: the fetcher follows up to 5 redirects, records each hop's status and
`Location`, and `extract()` sets `redirected_from` plus the chain. Enough for
hop count, statuses, source and destination — no collection redesign needed.

**Two things the trace found that would have made the findings wrong.**

1. *`Location` is often relative.* `httpbin.org/redirect/3` returns
   `/relative-redirect/2`, and we stored the header value verbatim. The chain is
   therefore resolved step by step — first hop against the requested URL, each
   subsequent hop against the previous resolution — otherwise the evidence shows
   a path with no domain.
2. *Raw hops overstate complexity.* `/a` → `/a/` is **zero** meaningful
   transitions, not one: both normalise to the same page. Length is counted in
   normalised addresses, so a site is never sent to fix something that is not
   broken.

**Architecture.** `app/audit/redirects.py` turns the stored data into a `Chain`
(`source`, resolved `hops`, `final_url`, `final_status`, normalised `path`). It
knows nothing about severity or wording. Three detectors consume it:

| Code | Fires on | Variants |
|---|---|---|
| `seo.redirect_chain` | more than one meaningful transition | — |
| `seo.redirect_loop` | repeated address, or limit exceeded | `repeated`, `limit` |
| `seo.redirect_target` | chain ends on 4xx/5xx | — |

A single redirect never produces a finding: `http → https` and legacy → current
are legitimate, and warning about them would be noise.

**Chain versus loop — the boundary that mattered most.** A true infinite loop
cannot be proven from our data: httpx raises `TooManyRedirects` at the limit and
**returns no history at all**, so we know neither where it circled nor whether it
circled. Therefore:

- `repeated` states only what was seen — an address occurring twice in a chain
  that *finished*, both occurrences observed;
- `limit` states only that we followed 5 redirects and received no page, and its
  evidence carries `chain_available: false`. Its wording contains no word for
  "loop" in any of the six languages, pinned by a test.

Distinguishing them structurally required one small fetcher change:
`FetchResult.redirect_limit_exceeded`, set by catching `httpx.TooManyRedirects`
separately. The alternative was parsing a third-party library's English error
string to make a claim to a customer — the failure mode this codebase already
recorded once ("Розбирати рядок `error` не можна").

**Customer-facing interpretation.** Only defensible consequences: each extra hop
is another round trip before anything appears; a chain that never ends returns
nothing at all; a redirect landing on an error sends visitors to a failure while
the site appears to be handling the address correctly. **No claim of a ranking
penalty in any locale** — Google does not state one and we did not measure it.
`test_no_wording_promises_a_ranking_penalty` enforces this across all six
catalogues in six languages.

**Internal-link attribution (minimum reusable form).** Evidence carries
`linked_from`: pages whose already-collected `page.links` point at the
redirecting address. Reused from the same source the link graph builds on — no
second graph. This is deliberately the minimum: general broken-link attribution
remains the separate D-7 item, and single-hop internal-link inefficiency is
**deferred** (warning on every internal `http → https` link would be noise).

**Canonical.** No second canonical detector, and no finding overlapping the
existing `seo.canonical*` criteria. The chain's destination and its canonical
relationship remain visible through existing evidence.

**Scoring.** All three detectors are `Severity.INFO`, `weight = 0`.
`scoring_version()` stays `3fdd28054fda`; no constant, weight, severity or
normalisation changed. Replaying all 56 benchmark snapshots: **zero score
movement**, verified as a test rather than a one-off measurement.
`detector_version()` moves, as it must when checks are registered.

**Snapshots.** `redirect_chain` round-trips, and its declared type is now
restored on load — JSON has no tuples, so it had been coming back as lists of
lists under a `tuple[tuple[int, str], ...]` annotation. Old snapshots load and
report no redirects, which is true of the stored data; `redirect_limited` is
empty on them because the field did not exist, which is "not recorded", not "no
limit was hit".

**Live and corpus evidence.** Corpus replay: 20 of 56 snapshots carry recorded
redirect data, and `seo.redirect_chain` fires on 5 sites — all genuine two-hop
paths (`twohillsaccounting.com → twohillscpas.com` domain migration,
`web.dev → developer.chrome.com` content move, `semrush.com/enterprise →
enterprise.semrush.com`). The limit path was verified live end to end against
`httpbin.org/redirect/9`: flag set structurally, carried through the crawler into
the frontier.

**Verification.** 1543 tests green; `ruff` clean; `mypy --strict` clean across
all seven packages. 24 cases in `tests/test_redirects.py` built on real
`FetchResult`/`RedirectHop` objects through `extract()`, not on hand-made
findings.

### D-7b. ~~P2~~ RESOLVED — sitemap consistency cross-checks

**What already existed.** Discovery (robots + two conventional paths), index
handling, parsing, `url_count`, the `_spread` sample, `has_lastmod`, item #4's
hreflang annotations, and two detectors: `seo.sitemap` (missing / invalid /
empty / *pages absent from the sitemap*) and `seo.sitemap.lastmod`. Note the
direction: the existing `coverage` variant asks whether crawled pages are **in**
the sitemap. This item asks the opposite — whether what the sitemap declares
matches what we observed. No overlap, and `lastmod` was not touched.

**What did not exist.** Per-URL provenance. `collect_sitemap` recorded only the
top-level file, so "which sitemap is this URL in" had no answer at all.
`SitemapInfo` now carries `sources` (url → file), `is_index`, `children_read`
and `children_total`.

**Architecture.** `app/audit/sitemap_audit.py` builds an `Audit` of `Entry`
records — declared URL, normalised form, source files, whether we observed it,
status, reasons, detail. It performs no collection: status, redirects, `noindex`
and canonical all come from `PageSignals`, and the redirect chain from item #6's
`redirects.chain_of`. One detector consumes it.

**Inconsistency types**, one issue per reason with the URL list in evidence — a
5 000-URL sitemap with 200 redirects is one job, not 200 findings:

| Variant | Meaning |
|---|---|
| `error` | the address answered 4xx/5xx when we opened it |
| `redirects` | the address forwards elsewhere; the sitemap should carry the destination |
| `noindex` | listed as worth finding while asking not to be shown |
| `canonical` | the page names a different address as primary |
| `not_for_search` | sign-in, basket, archive — reuses the existing `NOT_FOR_SEARCH` set |

**Dedup / root cause.** Each URL gets exactly **one** primary reason, by the
priority above; the full reason list stays in its evidence. A page that is both
`noindex` and canonicalised elsewhere is one root cause and one action, so it
produces one finding, not two. This is also why the family does not restate
`seo.noindex`: that check asks whether the exclusion was intended, this one says
"you are asking search engines to find a page you closed" — a different claim
with a different fix.

**Coverage honesty.** Every finding carries `declared` / `checked` / `unchecked`
/ `inconsistent` alongside the count, so "your sitemap is clean" can never be
implied from 22 URLs out of 3 407. A sitemap URL the crawl never opened produces
no finding of any kind — *not crawled ≠ broken* — and the wording nowhere claims
that presence in a sitemap guarantees indexing.

**A category error the corpus caught — and its proper fix.** `crustula.com.ua`
reported five broken sitemap pages that were actually deleted **images**:
sitemaps mix `image:loc` into the URL list because `root.iter()` collected every
`loc` at any depth. The first fix filtered them by file extension after parsing.
That was the wrong discriminator and was replaced.

*Why extensions cannot decide this.* An image URL need not have an extension
(`/render/1024`), may carry query parameters (`/img?id=7&size=l`), and may live
on another host entirely (`cdn.example.net/a/b`). Meanwhile `/report.pdf` inside
`<url><loc>` is a legitimate document entry that an extension filter would throw
away. The schema answers the question exactly: `<url><loc>` is the entry,
`<image:image><image:loc>` and `<video:video><video:content_loc>` are resources
attached to it.

`_parse_sitemap` now returns a `ParsedSitemap` — `pages`, `children`, `images`,
`hreflang`, `is_index` — read structurally from direct children rather than by
flat traversal. Media is preserved in `SitemapInfo.images` for future vertical
sitemap work; **no image-sitemap detector was added.** The extension guard
survives only inside `sitemap_audit` as a compatibility shim for snapshots taken
before this parser existed, where images are already baked into `urls`; on fresh
audits that branch is dead.

**Sitemap index coverage.** The old code read exactly one child, chosen as
`urls[0]`, with no record of how many existed. It now reads up to
`MAX_SITEMAP_CHILDREN = 5`, selected with the same `_spread` sampling used for
URLs — the beginning of an index is whatever the generator emitted first, which
is the lesson already learned on `furniturerow.com`. The model distinguishes
`children_total`, `children_read`, the pages found in those children, and
`index_complete`; the detector's evidence carries all four, so a sampled view can
never read as a whole-index verdict. **The page budget is untouched**: more
sitemap files parsed changes the pool `_seed_from_sitemap` selects from, never
`max_pages`.

*Measured on the site that exposed the bug.* `crustula.com.ua`'s
`/sitemap.xml` is in fact an **index**, which the flat parser never recognised.
Before: 21 "URLs", 10 of them non-pages, one child read. After: recognised as an
index, all 5 children read (`index_complete: true`), **86 real page URLs**, and
275 media resources kept separately. Zero non-pages left to filter.

*Score consequences, stated plainly.* Replaying the frozen corpus shows **zero**
movement, because snapshots store the already-parsed URL list. Fresh audits are
a different matter: `url_count` was previously inflated by media and, on
indexes, by whichever single child was read. It feeds `_sample_covers_the_site`
(the `seo.orphan_pages` gate), the `seo.sitemap` coverage variant, the
`seo.sitemap.lastmod` gate and the report's `pages_known`. On `crustula.com.ua`
the crawl-coverage ratio moves from 18/21 to 25/86 — the second is the honest
number, the first was measured against a denominator that included images. This
is a corrected input, not a changed rule; `scoring_version()` stays
`3fdd28054fda` and no constant moved.

**Snapshots.** `sources`, `is_index`, `children_read` and `children_total` round
trip. Old snapshots load and report `provenance_known: false` — unknown
provenance, never "one source" and never "no source". No finding is manufactured
from data those snapshots do not contain.

**Scoring.** `INFO` / `weight = 0`. `scoring_version()` stays `3fdd28054fda`;
no constant touched. Replaying all 56 snapshots: **zero score movement**, written
as a test.

**Corpus evidence.** 46 of 56 snapshots carry a usable sitemap; all five reasons
fire on real sites — `not_for_search` on 7, `redirects` on 6, `error` on 5,
`noindex` on 4, `canonical` on 2. The sharpest true positive is
`auditlensapp.com`, where all eight sitemap URLs canonicalise to `/`.

**Verification.** 1572 tests green; `ruff` clean; `mypy --strict` clean across
all seven packages. 29 cases in `tests/test_sitemap_consistency.py` driving real
`_parse_sitemap` and real `extract()`.

**Deferred, deliberately.** Reading *every* child of a large sitemap index: the
cap of five bounds cost, and an index of a hundred files stays explicitly
sampled (`index_complete: false`) rather than silently partial. Raising the cap
is a calibration decision, recorded in §K.4. Also deferred: the `rstrip("/")`
comparison inside the older weighted `seo.sitemap` check, which is looser than
`normalize()` used everywhere else — a real inconsistency, but correcting it
would move frozen scores. And no vertical (image/video/news) sitemap detectors:
the metadata is now captured, the criteria are not written.

### D-7c. ~~P2~~ RESOLVED — broken internal-link attribution

**What already existed.** Everything needed, unjoined. `LinkRef` has carried
`url`, `anchor`, `rel`, `is_internal` and `in_chrome` since Phase 0; rendered
links live in `RenderResult.signals.links`; the graph counts incoming edges;
`ctx.failed_urls` and page status codes record failures.

**Where attribution was lost.** In the detector. `seo.broken_links` emitted
`{"urls": {url: "HTTP 404"}}` truncated to 15 — a list of broken addresses with
no mention of which page linked there, with what text, or whether the link even
existed in the server's response. The graph knew eight links pointed at a page
and could not name one of them. The customer action was therefore "fix the links
pointing to these pages" without saying which pages.

**Architecture.** `app/audit/link_evidence.py` — `Observation` (source, target,
anchor, `Seen`, `in_chrome`, `rel`) and `Destination` (target, `TargetState`,
status, observations, detail). It is deliberately about links in general rather
than broken ones, because **item #9 needs exactly these observations** for
anchor-text quality; an array bolted onto the broken-link detector would have
had to be rewritten.

**Confirmed versus unverified.** `TargetState` separates `client_error`,
`server_error`, `redirect_to_error`, `fetch_failed`, `not_checked` and
`blocked`. Only the first three are `CONFIRMED_BROKEN`. A destination the crawl
never reached is never called broken; neither is one robots.txt kept us away
from, nor a transport failure — that may be our side, not theirs.

**Response versus render.** `Seen.RESPONSE` / `RENDER` / `BOTH`, derived from the
two already-parsed link lists. No second DOM comparison: the rendered list was
produced by the same `extract` at render time.

**Redirect interaction.** Reuses item #6 evidence. `page → broken URL` and
`page → redirecting URL → broken destination` are distinct states, and the
second carries `final_url` and hop count so the owner can see whether to repoint
the link or fix the redirect.

**Dedup and grouping.** One finding per audit, never one per `<a>`. Destinations
are grouped by normalised URL, so `/gone`, `/gone/` and `/gone?utm_source=x` are
one target. A repeated identical link on one page is one observation of that
page — counting markup rather than the site would inflate every template.
Ordering is deterministic (`-links`, then key).

**Reporting size.** Bounded display with honest totals at every level:
`examples_shown` / `examples_truncated` per destination, `destinations_total` /
`destinations_truncated` per finding, and real `source_pages` / `links` counts
regardless of what is shown. A truncated list never implies completeness.

*A Word-rendering defect this surfaced.* `docx._format_evidence` rendered any
list value with `str(v)`, so nested attribution arrived in the client document as
a raw Python dict — `{'from': '…', 'in_chrome': False}`, quotes and all. It now
formats to a bounded depth with `(+N)` for the remainder. The fix is generic, not
special-cased: every check's nested evidence benefits.

**Scoring.** The detector's firing condition is unchanged **verbatim** — the same
`failed_urls` prefix scan and the same status-code sweep. Attribution enriches
evidence only. Corpus check: exactly one issue on each of 22 sites, penalty 9 on
every one, `scoring_version()` unchanged at `3fdd28054fda`, no check attribute
touched. A destination with no linking source (it came from the sitemap) stays in
the list precisely so the condition does not shift; it is labelled
`source_pages: 0`, and `seo.sitemap_consistency.error` covers it properly.

**Localization.** No new catalogue key — the existing criterion carries the
richer evidence, as required. Its `description` was **empty** and is now filled
in all six locales; the recommendation changed from "fix the links pointing to
these pages" to working from the named source pages. No locale claims ranking
loss.

**Corpus evidence.** Of 56 snapshots, 22 fire the finding and **14 now name
source pages and anchor text**. The remaining 8 are destinations that arrived
from a sitemap rather than a link — correctly shown with zero sources.

**Verification.** 1612 tests green; `ruff` clean; `mypy --strict` clean across
all seven packages. 32 cases in `tests/test_link_attribution.py` built on real
`extract()` output and the real link graph, including an invariant that
attribution and `graph.incoming` agree.

**Deferred to item #9, deliberately.** Anchor text is *stored* and never judged:
no finding about "click here", empty anchors, keyword stuffing, repetition or
descriptiveness. `test_an_empty_anchor_is_recorded_without_judgment` pins that
boundary. External-link checking remains out of scope — no new collection
behaviour was added for it.

### D-7d. ~~P2~~ RESOLVED — internal anchor-text quality

**What already existed.** `LinkRef.anchor` (visible text, whitespace-collapsed,
capped at 200), `in_chrome`, `rel`, and item #8's `link_evidence.Observation`
with source/target/anchor/`Seen`. Verified before judging anything — and two of
the four capabilities the task asked about were **absent**:

- an image link exposed **no** alt text (`node.text()` is empty for
  `<a><img alt="…"></a>`), so every logo and product-card link looked textless;
- an icon link with `aria-label` was indistinguishable from a genuinely
  unlabelled one.

Both are now captured as `LinkRef.image_alt` and `LinkRef.label`, deliberately as
**new fields rather than folding into `anchor`**: `anchor` feeds crawl priority
via `kind_of` and two weighted checks, so changing it would move frozen scores.

**Shipped: one class.** `seo.anchor_text` — the same uninformative phrase leading
to **two or more distinct destinations**. The threshold is not a tuned number: it
is the exact condition under which the claim becomes true. One "read more"
pointing at one page is a matter of style; the text stops distinguishing only
when different pages hide behind it. Google's guidance supplies the phrase
examples (`click here`, `read more`, `website`, `article`), and the finding never
claims those examples are a ranking rule.

**Rejected after measuring on real sites — empty anchor text.** It was
implemented, measured, and dropped. On the corpus it fired on 40 of 56 sites,
including **524 links on `aldg.org` (35% of all contextual links)** and **240 on
`crustula.com.ua` (67%)**. The cause is ours, not the sites':
`_extract_links` keeps the **first** `<a>` per URL and discards the rest, while
the standard card is

    <a href="/product"><img …></a>
    <h3><a href="/product">Moon cake</a></h3>

— the text lives in the second `<a>` and never reaches us. Shipping that would
have blamed customers for our blind spot. The count survives as
`links_without_any_text` in evidence for calibration; fixing it properly means
changing extractor deduplication, which moves crawl priority and two weighted
checks.

**Also deliberately not implemented.** *Excessive length* — no defensible
threshold was found, and inventing one to have a detector is what §12 forbids.
*Anchor/destination mismatch* — requires semantic judgment, explicitly out of
this deterministic track.

**Language.** Per-language phrase registries for the six report locales. A page
whose language cannot be established from `html lang` (parsed with item #4's
`language_tags`) is skipped entirely; so is a language with no registry. An
English list is never run against a Ukrainian page — `pages_without_language`
records how often we stayed silent.

**Chrome versus context.** Only `in_chrome=False` links are judged. A repeated
"Pricing" in the header is a landmark, not a defect; `navigation_links_skipped`
reports the volume set aside (639 on `web.dev` against 406 contextual links).

**Registry provenance.** The phrase lists live in `app/audit/anchor_text.py`, not
in `standards/`. That is on purpose: `standards/` holds vendored external
registries with a source URL and verification date, and dressing a hand-built
heuristic in that provenance would be a fabrication. The module says so in its
first paragraph.

**Grouping.** One finding per audit; inside it, one row per phrase with `links`,
`destinations`, `source_pages` and bounded examples marked
`examples_truncated`. The customer's unit of work is the phrase — usually one
template — not the individual link.

**Live corpus validation.** Fires on **16 of 56 sites**, 1–3 phrases each, never
dominating: SaaS (`jasper.ai` 57 links, `asana`, `stripe`, `cloudflare`,
`supabase`), publishers (`web.dev` 36, `searchengineland`, `moz`), documentation
(`mintlify`, `supabase-docs`), ecommerce (`shopify`), local business
(`twohillsaccounting`, `anchoredgetechno`), enterprise (`bosch`, `hubspot`). Only
four phrases fire across the whole corpus — `learn more`, `read more`, `here`,
`article` — all of them Google's own examples. Manual review of `web.dev`
(36 links labelled "article" to 33 different articles), `jasper.ai` and
`anthropic.com` found no false positives. No multilingual site fired, so the
non-English registries are covered by tests rather than corpus evidence.

**Scoring and graph.** `INFO` / `weight = 0`; `scoring_version()` unchanged at
`3fdd28054fda`; zero movement across all 56 snapshots, written as a test. Anchor
quality does **not** enter graph importance — a test pins that `incoming`,
`outgoing` and `depth` are byte-identical before and after analysis.

**Verification.** 1648 tests green; `ruff` clean; `mypy --strict` clean across all
seven packages. 36 cases in `tests/test_anchor_text.py`, built on real `extract()`
and real `link_evidence`.

### D-7e. ~~P2~~ RESOLVED — mixed content and browser-impact evidence

**What already existed — and the gap the trace found.** `ResourceLoad` carries
`url`, `resource_type`, `is_third_party` for rendered pages, and
`RenderResult.requests` records what the browser actually asked for. But the
response-HTML side kept **only hosts**: `_extract_third_party` walked
`script[src]`, `link[href]` and `iframe[src]` and threw the URLs away, scheme
included. Mixed content was therefore unrecoverable from markup — the question
had no answer at all before this item.

Measured on the frozen corpus: **one** site shows an insecure request in the
browser log and **zero** `ResourceLoad` entries do. That is not because sites are
clean — it is because Chrome upgrades eligible requests before the request event
fires, so runtime evidence alone systematically under-reports. The signal has to
come from markup.

**New extraction.** `PageSignals.insecure_refs` (`InsecureRef`: url, kind,
`in_srcset`), collected only when the document itself is HTTPS. `link` entries
carry their `rel` as the kind — a stylesheet and a favicon are different request
destinations. Ordinary `<a href="http://…">` navigation is **not** collected:
the browser navigates, it does not subload, and conflating the two would blame a
site for something that did not happen.

**Classification.** `app/audit/mixed_content.py` replaces any ACTIVE/PASSIVE
binary with five states — `BLOCKABLE`, `UPGRADEABLE`, `MIXED_DOWNLOAD`,
`NOT_MIXED`, `UNKNOWN`. An IP-literal host on an otherwise upgradeable resource
is `UNKNOWN`, not `UPGRADEABLE`: the upgrade algorithm does not apply to IP
hosts, and we did not measure what each browser then does.

**Declared versus observed — kept apart deliberately.** `handling` is the
standards-expected behaviour; `observed` is what the browser log shows —
`UPGRADED`, `REQUESTED_INSECURELY`, `NOT_OBSERVED`, or `NO_RENDER` for the pages
we never opened. Neither is allowed to stand in for the other: claiming a
resource was blocked without seeing it blocked is invention, and treating
"the browser will upgrade it" as "the setup is fine" is the opposite mistake —
the upgrade holds only while the HTTPS version of the file exists.

**Response versus render.** `seen_in` is `response` / `render` / `both`, read
from the two already-parsed signal sets; requests visible only in the network log
get `network` and their own variant. No second DOM comparison.

**CSP.** `upgrade-insecure-requests` is recorded as
`pages_with_upgrade_insecure_requests` beside the finding and never suppresses
it. The obsolete `block-all-mixed-content` is recommended nowhere — a test
enforces its absence in all six locales.

**Findings.** One code, four variants: `blockable`, `upgradeable`, `download`,
`runtime`. Grouped by class, never one finding per resource — twenty insecure
images are one finding with `resources_total: 20` and eight bounded examples
marked truncated. Ownership rides in evidence (`third_party`) rather than
creating a separate scored criterion.

**HTTP pages produce nothing.** Mixed content requires a secure context; the
insecure document itself is already `seo.https`, and duplicating that root cause
was explicitly avoided.

**Live validation.** Three legacy-leaning sites crawled fresh.
`anchoredgetechno.com` and `twelvestrike.com`: clean. **`microtechia.com`: 8
pages declare `<script src="http://stats.viennam.com/…">`** — third-party,
classified `BLOCKABLE`, and on the 3 pages we rendered the browser was *observed*
issuing the request over http, while the other 5 honestly report `no_render`.
That single site exercises both halves of the model at once. Frozen-corpus
replay finds only the network-observed case, because those snapshots predate
`insecure_refs` — correctly reported as `seen_in: network`, never invented.

**Scoring.** `INFO` / `weight = 0`; existing HTTPS/TLS scoring untouched;
`scoring_version()` unchanged at `3fdd28054fda`; zero movement across all 56
snapshots, written as a test.

**Scope held.** No CVE scanning, no exploit testing, no server probing, no
security score. Only insecure subresources embedded by HTTPS pages, their
expected browser handling, and where to fix them.

**Deferred.** CSS-discovered resources (`url()` inside stylesheets) — we do not
fetch or parse CSS, so those references are invisible; and per-request
destination typing for `runtime` findings, which the browser log does not record,
leaving them `UNKNOWN` by construction. Both are recorded in §K.4.

### D-7f. ~~P2~~ PARTIALLY RESOLVED — duplicate content clusters

**What existed.** `PageSignals.text` — `<main>` text, or the whole `<body>` when
there is no `<main>` — stored in snapshots, plus `word_count`, canonical,
`noindex`, redirects, page type and item #4's hreflang clusters. No hash, no
fingerprint, no similarity of any kind. Enough to compare pages offline; not
enough to isolate primary content.

**Normalisation.** Comparing `text` directly would call every page of a
navigation-heavy site a duplicate. Shingles (5-word) whose document frequency
crosses `BOILERPLATE_SHARE` are treated as chrome and dropped. Two corrections
came out of testing, both about the same trap — **shared content erasing
itself**:

1. On a three-page site the 0.6 share gives a cutoff of two, so two identical
   pages declared their own shared text to be boilerplate. Floor raised to three
   pages.
2. Frequency is now counted over **distinct contents**, not raw pages. Three
   identical pages out of four are 75% of pages; measured that way their shared
   text looked like a template and vanished exactly when it was the finding.

**Exact duplicates — shipped.** Identical normalised text under distinct logical
URLs. No threshold is involved, so none had to be invented. Guarded by
`MIN_OWN_SHINGLES`: a page whose text survives boilerplate removal with almost
nothing left cannot be compared — this is what keeps the SPA shell
(`auditlensapp.com`, four URLs serving one skeleton) out of the results.

**Near duplicates — measured, NOT shipped.** This is the substantive finding of
the item, and it is an architectural limit rather than a tuning problem.

Measured across 51 corpus sites, 9 869 pairs. Raw similarity would flag 353 pairs
at ≥ 0.7; after boilerplate removal, 24. Every one of those 24 was inspected by
hand. Twenty-three are genuine — `/` vs `/index.html`, WordPress archive triples,
`asana.com/campaign/team-calendar` vs `/uses/team-calendar` (0.989),
`stripe.com/contact/sales` vs `/contact/sales-ib` (0.967). One is not, and it
sits **high** in the band, not at the margin: `fastapi.tiangolo.com/about/` vs
`/newsletter/` at **0.944**. Those pages are near-empty; their `text` is the
documentation sidebar. Boilerplate filtering could not see it because the crawl
spans thirteen language variants, so the English sidebar appears on two pages out
of twenty-four — far below any sane cutoff.

The mechanism generalises to any multilingual site with heavy navigation, and
below 0.7 the errors are blatant: `hubspot.com/services/…/ongoing` against a
person's biography page scored 0.62. **Until primary content can be isolated,
a similarity threshold measures shared navigation, not shared pages.** Near
similarity is therefore computed, exposed as `near_duplicate_pairs_measured`, and
kept out of customer-facing findings — the outcome §7 and §22 of the task
explicitly permit.

| Similarity | Pairs (raw) | Pairs (boilerplate removed) |
|---|---|---|
| ≥ 0.3 | 954 | 121 |
| ≥ 0.5 | 578 | 58 |
| ≥ 0.7 | 353 | 24 |
| ≥ 0.85 | 156 | 21 |
| ≥ 0.95 | 69 | 18 |

**Candidate generation.** MinHash (64 permutations) with LSH banding (16×4);
only pairs sharing a band bucket are scored. Deterministic — fixed multipliers,
no seeds. Verified: **500 distinct pages produce 0 candidate pairs** against
124 750 for all-pairs, in 4.2 s; a 200-page guard test asserts candidates stay
under 5% of all pairs.

**Canonical, indexability, hreflang.** Clusters carry each member's canonical and
one of four consolidation states. `CONSISTENT` — every member names one member —
produces **no finding**: that is correct consolidation. `ALL_SELF` and `ABSENT`
become `unconsolidated`; contradictory or outward-pointing canonicals become
`conflicting`. Members are labelled `indexable` / `noindex` / `redirected` /
`not_for_search`, and a cluster needs at least two indexable members to be worth
raising. Pairs the site itself declares as hreflang alternates are excluded —
regional variants are configuration, not oversight.

**Representative** is chosen deterministically: the member others canonicalise
to, else the shortest normalised URL, else alphabetical. It is never called a
"Google canonical" — which one search picks is not something we know.

**Corpus results.** Fires on 3 of 56 sites: `clouddimension.in` and
`airtechsolutionsinc.com` (`/` vs `/index.html`) and `hvac-oc.com` (five
http/https twins). All true positives. Two further clusters —
`24hourplumberdfw.com` WordPress archives and `anchoredgetechno.com` blog tags —
are found but stay silent, having fewer than two indexable members.

**Scoring.** `INFO` / `weight = 0`; `scoring_version()` unchanged at
`3fdd28054fda`; zero movement across all 56 snapshots, written as a test.

**Deferred to the ~1 000-site calibration.** Whether primary-content extraction
is worth building (a `<main>`/readability subsystem), which would unlock near
duplicates; whether a threshold survives a real distribution once it can;
and whether exact duplicates deserve a scored severity distinct from near ones.

### D-7g. ~~P2~~ RESOLVED — compression and protocol diagnostics

**What existed.** `FetchResult.headers` already carried `content-encoding`,
`content-length` and `content-type` for every response, and `httpx` is configured
with `http2=True` with the `h2` package installed — so the client genuinely
negotiates HTTP/2. **The gap:** `response.http_version` was read nowhere, and
neither was the request's own `Accept-Encoding`. Without the second, "the server
did not compress" is not a statement at all.

**No overlap.** No compression check existed anywhere, and Lighthouse's
`uses-text-compression` is not surfaced by our PSI integration. This adds missing
deterministic evidence rather than restating another subsystem.

**Measurement limits established first, by probing the live client:**

- We advertise **`gzip, deflate` only** — `brotli` and `zstandard` are not
  installed, so we never ask for them. A server offering Brotli alone would
  answer us with identity. Every conclusion is therefore phrased about *this
  response*, never about server capability.
- `httpx` decompresses bodies, so the body length is the **decoded** size while
  `Content-Length` describes what actually travelled. Those are different
  quantities; dividing one by the other is only meaningful when both exist and
  there is no `Transfer-Encoding: chunked`. When in doubt the value stays `None`.
- Our stack does not negotiate **HTTP/3** at all, so its absence is unknown, not
  a fact about the site. Nothing is reported about it.

**Architecture.** `app/audit/transport.py` — `Coding` (gzip / br / zstd / deflate
/ identity / other, per RFC 9110, RFC 7932, RFC 8878 + RFC 9659),
`Compressibility` (textual / already-compressed / unknown, decided by
`Content-Type`, never by extension), and `Observation` carrying protocol,
coding, both sizes, and what we advertised. `PageSignals` gained `http_version`
and `accept_encoding`.

**Live distribution**, six sites across SaaS, publisher, local business and
e-commerce, 60 responses:

| | Result |
|---|---|
| Protocol | **50 HTTP/2**, 10 HTTP/1.1 |
| Text encodings | **49 gzip**, 11 identity |
| Unencoded text sizes | 39.7 KB – 109.7 KB |

Both findings shipped, because both preconditions held:

**Compression** — `aldg.org` returns 10 pages of 66–110 KB HTML with no encoding
while we advertised gzip; `python.org/about/apps/` returns 39.7 KB unencoded with
`Content-Length` equal to the decoded size, confirming it. Materiality floor is
**10 KB decoded** — a noise-control heuristic, not an SEO rule, set well below
the smallest observed case so it is not tuned to the sample.

**HTTP/1.1** — the precondition in the task ("client demonstrably capable")
holds: `h2` installed, `http2=True`, and 50 of 60 responses negotiated HTTP/2.
`aldg.org` returned HTTP/1.1 on three consecutive direct probes (Apache,
chunked). The firing rule checks **client capability**, not in-audit contrast:
requiring both protocols within one audit would have silenced the very site that
is entirely HTTP/1.1 — the actual case. Wording is "we negotiated HTTP/1.1 for
these responses"; a test forbids "does not support" in all six languages.

**Browser protocol** is not compared, because our renderer does not record it —
stated rather than fabricated.

**Scoring.** `INFO` / `weight = 0`; existing performance scoring untouched;
`scoring_version()` unchanged at `3fdd28054fda`; zero movement across all 56
snapshots, written as a test.

**Snapshots.** `http_version` and `accept_encoding` round-trip. Old snapshots
have neither, and that reads as **unknown** — the analysis counts them in
`responses_without_transport_data` and the check stays silent, never
reinterpreting an absent field as "HTTP/1.1" or "uncompressed".

**Deferred.** Installing `brotli`/`zstandard` so we can advertise and observe
those codings; capturing browser-side protocol for the crawler-vs-browser
comparison; and measuring actual compression savings, which needs compressing
the bodies ourselves. All recorded in §K.4.

### D-7. P2 — closed

All items of the Coverage reconciliation are now implemented or explicitly
deferred with recorded reasons.

### Deliberately not proposed

**Google rich-result eligibility.** It contradicts the current AI-citability
framing and would import exactly the feature churn the review warns about.
Revisit only on customer demand. See §I-1.

---

## E. False gaps / duplicates

Checked before declaring anything missing.

| Apparent gap | Already covered by |
|---|---|
| "No orphan detection without owner data" | `seo.orphan_pages` + sitemap + coverage gate |
| "No internal-link analysis" | `link_graph.py` + `importance()` in prioritization |
| "No page-importance weighting" | `_group_importance`, `_stamp_importance` |
| "FAQ recommendations now obsolete" | Framed as LLM citability, not a Google feature |
| "May claim WCAG conformance" | Explicitly disclaimed in `a11y.failures` |
| "Field and lab may be conflated" | `source` + `Confidence` per metric; lab TBT suppressed |
| "AI presence may be overstated" | No subsystem exists; enrichment makes no presence claim |
| A new "JS content invisible" detector | Would duplicate `llm.client_rendered` |
| A new "site blocks our crawler" detector | Would duplicate `tech.crawler_blocked` |
| A new "site blocks AI bots" detector | Would duplicate `llm.crawler_blocked` — extend it instead |

---

## F. Architecture implications

- **Shared standards registry** — new, e.g. `app/audit/standards/`. AI crawler
  tokens first (real payload, not an abstract refactor), then `SECURITY_HEADERS`,
  the a11y `BLOCKING` set, and schema expectations. Each entry carries source URL
  and `last_verified_at`; tests assert freshness. Primary vendor sources only
  (§0.3).
- **robots evaluation** — belongs beside the registry as a reusable RFC 9309
  evaluator (§0.4), not as string checks inside `_parse_robots`. It has two
  consumers: what Crawldy reports about a site, and how Crawldy's own crawler
  behaves.
- **Detector layer only** — response-vs-render diff, redirect chains, hreflang,
  sitemap cross-checks. No new collection; `snapshot.py` already round-trips the
  inputs, so all four are testable offline via `--from-snapshot`.
- **Crawler/renderer boundary** — JS-only link discovery is the single item that
  changes pipeline ordering. Isolate it.
- **Extractor** — hreflang is the only genuinely new signal to capture.
- **AI Presence subsystem** — its own module with its own evidence contracts,
  structurally unable to feed deterministic crawl facts, mirroring how
  `app/enrich/` has no path back into scoring. Provider behind an adapter, as
  with `PerformanceProvider` and `BillingProvider`.
- **External/owner evidence tier** — GSC, Bing, analytics enter as provenanced
  providers alongside deterministic facts, never mutating them.
- **Report layer** — anchor text and broken-link attribution are presentation
  gaps over data already collected, not detection gaps.

---

## G. Implementation order

1. ~~**Reconcile `seo.click_depth`** against graph semantics (§0.5, D-1)~~ —
   **done in `84dee3e`.** The check measured outgoing links while telling the
   customer almost nothing linked *to* the page; renamed to
   `ThinOutboundLinkingCheck`, code kept for score continuity.
2. ~~**AI crawler purpose registry + RFC 9309 robots evaluation** (D-2)~~ —
   **done in `11f865e`.** Registry with primary-source provenance, RFC 9309
   evaluator, purpose-aware findings. Two follow-ups recorded: severity by
   purpose (§I-3, calibration phase) and the remaining hardcoded lists
   (item 8 below), which the pattern is now proven enough to absorb.
3. ~~**Response-vs-render field differential** (D-3)~~ — **done in `3586e9c`.**
   Reusable comparator; findings are informational so the frozen baseline is
   untouched. One follow-up recorded: whether `index → noindex` after render
   deserves a scored severity (§I-7, calibration phase).
4. **Actual AI Presence tier — contracts and separation first** (D-5, §0.1) —
   define the evidence model, provenance and the readiness/presence boundary
   (§0.2) before any provider is chosen.
5. ~~**hreflang** (D-6)~~ — **done.** Closes the only wholly absent
   classical-SEO area. Standards registry on Google's actual grammar (ISO 639-1
   + ISO 15924 script + ISO 3166-1), all three declaration mechanisms, five
   detectors, six locales. Two follow-ups recorded: provisional weights and
   variant co-occurrence (§K.4, calibration phase).
6. ~~**Redirect chains and loops** (D-7a)~~ — **done.** Three informational
   detectors over data that was already collected; chain and loop kept
   structurally distinct because the loop case cannot be proven.
7. ~~**JS-only link discovery** (D-4)~~ — **done.** One shared frontier,
   wave-based discovery bounded by the existing page and render budgets,
   provenance on every URL. Robots enforcement arrived with it, uniformly.
8. **Migrate remaining hardcoded lists into the registry** — headers, a11y,
   schema expectations.
9. ~~**Sitemap cross-checks**~~ — **done** (D-7b). Broken-link attribution and
   anchor text remain in D-7.
10. **Google Search Console integration** — largest owner-data step; its own
    product track (auth, storage, evidence tier).

After items 1–9 (experimental §H items excluded): the **large-scale
validation and calibration phase** of §K.2–K.7 — benchmark, human validation,
calibration decision, corrections, regression benchmark, new scoring freeze.
The Coverage phase is not declared complete before it.

---

## H. Experimental backlog

Kept out of the committed roadmap and out of any score until standards or
customer value stabilise.

- **AI Presence measurement methodology** — which providers, query sets,
  sampling, refresh cadence, uncertainty expression. The *track* is committed
  (§0.1); only the method is experimental here.
- Agentic browsing readiness — accessibility tree, interaction stability.
- WebMCP registered tools and schema validity.
- UCP and commerce-agent protocols (vertical-specific).
- IndexNow.
- Server-log analysis (enterprise tier).
- ACT rule-ID provenance — cheap once the registry exists, commercially weak;
  do it opportunistically, not as its own task.

---

## I. Conflicts with previous decisions

1. **Google rich-result eligibility (review P0)** conflicts with the accepted
   AI-citability framing and with the frozen scoring baseline. Recommend
   declining; revisit only on customer demand.
2. **ACT/WCAG provenance (review P0)** conflicts with the standing rule that a
   check must change what the customer does. Downgraded to opportunistic (§H).
3. **AI bot purpose matrix implies weighting changes.** Scoring is frozen since
   `7586487`. Adding tokens raises the *detector* and is allowed; weighting
   blocked search bots differently from blocked training bots is a scoring change
   requiring the documented snapshot A/B and an explicit unfreeze.
4. **`seo.click_depth` resolution is scoring-visible** — changing measurement or
   identifier moves findings and `issue_key`. Same A/B requirement (§0.5).
5. **Agent readiness section (review P1)** conflicts with the standing rule
   against promising what was never measured, while Chrome's category remains
   informational and unbenchmarked. Experimental, no score.
6. **The review's own §2 states it is not a code audit.** Where this document
   contradicts it, the difference is repository access, not disagreement.
7. **`seo.render_delta` is informational (INFO, weight 0) by necessity.**
   An `index → noindex` divergence after rendering is arguably serious, but any
   scored severity would move every SPA's score and break comparability across
   the freeze. Detection and evidence ship now; what it should cost is a
   calibration decision (§K.4), taken on real distribution data rather than
   intuition.

---

## J. Recommended next implementation task

After D-1 is reconciled as a correctness patch:

> **Replace the flat `AI_USER_AGENTS` tuple with a versioned, purpose-classified
> AI crawler registry sourced from primary vendor documentation, raise robots
> evaluation to RFC 9309 semantics, and split `llm.crawler_blocked` by purpose.**

**In scope:** a registry module carrying
`(vendor, token, purpose, source_url, last_verified_at)`; entries verified
against vendor documentation only (§0.3), including the currently missing
`Claude-SearchBot`, `Claude-User` and `Perplexity-User`; an RFC 9309 evaluator
handling `Allow`, longest-match precedence, `*` and `$`, group merging and the
5xx complete-disallow rule (§0.4); the finding split so blocking a *search*
crawler and blocking a *training* crawler no longer read as the same problem;
catalogue strings for the new variants in both languages; tests including a
freshness assertion on `last_verified_at` and RFC 9309 precedence cases.

**Out of scope:** severity or weight changes (scoring frozen — see §I-3), WAF
probing, and migrating any other hardcoded list; those follow once the pattern
is proven on a real payload.

**Invariant to preserve throughout:** nothing in this work may present crawler
accessibility as evidence of actual AI citation or presence (§0.2).

---

## K. Calibration & cross-cutting completion rules (accepted 2026-08-25)

Added after the reconciliation was accepted; governs all Coverage
implementation work from here on. Nothing above is rewritten by this section;
where it adds gates, the gates win.

### K.1 Cross-cutting Definition of Done for every audit criterion

**A criterion is not complete because its detection logic exists.** Any new or
modified audit criterion is complete only when it is consistently wired through
every relevant Crawldy surface — where applicable:

detector logic; factual evidence; interpretation and recommendation;
catalogue/registry; API serialization; scoring/severity/version metadata;
free/short report; full/paid report; every supported report output format;
**every supported report locale**; grouping and category placement; tests;
fixtures/snapshots where used; documentation/versioning where applicable.

No customer-facing criterion may exist only in English, silently fall back,
disappear from a localized report, or render incomplete in another supported
locale. Automated completeness tests are added where practical so a missing
translation, missing catalogue entry or disconnected report surface fails
before merge rather than in a customer's report.

**Report locales have a single source of truth.** `i18n.COMPLETE_LOCALES` —
derived from the explicit `complete=True` flag in the `LOCALES` registry — is
the authoritative set of supported report/catalogue languages (currently the
six launch languages: EN, DE, ES, FR, RU, UK). The wider `LOCALES` registry
(12 entries) describes website/UI locales and must not be used as the
completeness target: demanding catalogues for all twelve would either make the
test red by design or force translations for languages the report does not
ship in. A report requested in an unsupported locale falls back to English
**explicitly, by design** — verified in code (`i18n.render` with `Locale.PT`
returns the English string, not a raw key and not a crash).

First application: the `seo.click_depth` correction (commit `84dee3e`) ships
with tests that walk the criterion through findings, recommendations, JSON,
API serialization and DOCX in all six report locales, and fail on silent
English fallback. These tests are the template for subsequent criteria.

### K.2 Large-scale post-implementation validation

After the accepted P0 + P1 + principal P2 backlog is implemented, Crawldy
undergoes a new large-scale validation phase before the resulting
audit/scoring version is considered calibrated.

**Target: ~1,000+ real websites**, diverse enough to expose detector bias and
edge cases. The corpus deliberately includes, where available: SaaS;
ecommerce; local businesses; publishers/content sites;
multilingual/international sites; JavaScript-heavy/SPA sites; mostly
static/server-rendered sites; small sites; larger multi-page sites; different
CMS/platform families.

The objective is not score collection. For every new or materially changed
detector, evaluate: activation frequency; severity distribution; confidence
distribution; page/site coverage; suspiciously high or low firing rates;
false positives; false negatives; interaction with other findings; unexpected
category or site-type bias.

Particular attention goes to the new high-risk/high-value areas: AI crawler
accessibility and purpose classification; response HTML vs rendered DOM;
hreflang; JavaScript-only discovery; near-duplicate analysis; any detector
whose semantics or thresholds changed materially.

Method constraint carried over from `VALIDATION.md` experience: two crawl
runs are never compared to each other — rule changes are evaluated by
re-scoring the **same snapshots** (`calibrate.py --snapshots`, then
`rescore_dir.py` before/after), and the calibration crawl uses the product's
own budget, not a reduced one.

### K.3 Human validation layer

The benchmark includes manual review of a representative sample; calibration
is never driven by detector frequency alone. For selected positive and
negative cases, verify by hand: whether the factual detection is correct;
whether the interpretation is justified; whether the stated customer impact is
defensible; whether the recommendation is actionable; whether Crawldy is
creating false certainty; whether severity matches real business impact. The
sample deliberately includes both obvious and borderline cases.

### K.4 Score and threshold calibration

During implementation the **currently frozen scoring baseline is preserved**
unless a correctness defect makes that impossible (per §I-3/§I-4). After the
benchmark: inspect total and module score distributions; severity
distribution; saturation, clustering and outliers; whether new detectors
disproportionately move scores; whether existing thresholds remain sensible.

Only then decide whether detector thresholds, severity, confidence, weights,
normalization or scoring rules need adjustment. **Scoring is never changed to
produce a visually pleasing distribution** — changes must be justified by
observed detector behaviour and customer impact.

**Open calibration inputs recorded during Coverage implementation.** These are
observations, not decisions; each names the single site it rests on, which is
why none of them is being acted on yet.

| Input | Observation | Question for calibration |
|---|---|---|
| `seo.render_delta` cost (§I-7) | Fires on every SPA; currently INFO / weight 0 | What should an `index → noindex` render divergence cost? |
| hreflang weights (D-6) | Shipped INFO / 0. Provisional weights would have cost `fastapi.tiangolo.com` 9 SEO points (62 → 53) | What should each of the five codes cost? Decide on the corpus, not on one site. |
| hreflang co-occurrence (D-6) | Before suppression, three issue keys fired for one edit: SEO 45 vs 53 | Are the variant splits still too generous when several co-occur legitimately? |
| `seo.hreflang_missing` confidence | Language inferred from `html lang` across ≥ 4 pages | How often is "looks multilingual" wrong on the benchmark corpus? |
| ISO 3166-1 breadth (D-6) | 249 officially assigned; IANA also lists 12 exceptionally-reserved (`EU`, `UN`) and 11 withdrawn | Does Google accept `en-EU`? A product judgement, deliberately not taken during implementation. |
| Sitemap index depth (D-7b) | Up to 5 children read, spread across the index; `index_complete` marks a sampled view | Should the cap rise for large indexes? It changes the seed pool, so it moves live scores. |
| Compression coding breadth (D-7g) | We advertise `gzip, deflate` only; `brotli`/`zstandard` absent from the environment | Install them so Brotli/Zstd servers are observed as compressing, not as identity? |
| Transport severity (D-7g) | Ships INFO / 0. `aldg.org`: 10 responses of 66–110 KB unencoded, all HTTP/1.1 | Should uncompressed substantial text cost anything once the corpus is large? |
| Near-duplicate threshold (D-7f) | Not shipped. 24 pairs ≥ 0.7 after filtering, of which `fastapi.tiangolo.com/about/` vs `/newsletter/` at 0.944 is pure sidebar | Build primary-content extraction first; a threshold on `<body>` text measures navigation. |
| Duplicate severity split (D-7f) | Exact duplicates ship at INFO / 0; 3 of 56 sites fire | Should exact duplicates cost, and should near ones differ once they exist? |
| Mixed-content severity (D-7e) | Ships INFO / 0; `microtechia.com` shows 8 blockable third-party scripts | Should `blockable` outrank `upgradeable` once the corpus is large enough to see the split? |
| CSS-referenced resources (D-7e) | Not collected: we neither fetch nor parse stylesheets | Worth fetching CSS to find `url(http://…)`, or out of proportion? |
| Empty anchor text (D-7d) | Not shipped: extractor keeps only the first `<a>` per URL, so card patterns look textless — 524 links on `aldg.org`, 240 on `crustula.com.ua` | Change extractor dedup to prefer the link with text? It moves crawl priority and two weighted checks. |
| Anchor length (D-7d) | No defensible threshold found; nothing shipped | Does a length signal exist that survives a 1 000-site distribution? |
| Anchor ambiguity threshold (D-7d) | Ships at ≥ 2 distinct destinations; fires on 16 of 56 sites | Is two the right point, or does the corpus suggest higher? |
| Sitemap `url_count` correction (D-7b) | Structural parsing removes media from the count; `crustula.com.ua` coverage moves 18/21 → 25/86 | The orphan gate and report coverage now use a real denominator — confirm the 0.5 threshold still suits it. |
| `seo.sitemap` URL matching (D-7b) | The existing weighted check compares with `rstrip("/")`, not `normalize()` | Looser than everything else in the codebase; correcting it moves frozen scores. |

### K.5 Regression benchmark and new scoring freeze

If calibration changes are made: (1) apply the accepted corrections;
(2) rerun the benchmark/regression corpus on the same snapshots; (3) verify
false positives/negatives and score behaviour improved; (4) rerun automated
tests; (5) confirm report/localization completeness (K.1); (6) version the
resulting rules (`SCORING_RULES` bump where applicable); (7) freeze the new
scoring baseline.

The completed sequence is therefore:

> Coverage implementation → large-scale benchmark → human validation →
> calibration decision → corrections if needed → regression benchmark →
> scoring/version freeze.

This validation phase is **part of completing the Coverage roadmap**, not an
optional future idea.

### K.6 Product boundaries during calibration

Calibration continues to respect the accepted model: traditional Search
Visibility; AI readiness/accessibility; Actual AI Presence. AI readiness ≠
Actual AI Presence (§0.2). Large-scale crawling results are never used to
infer actual AI citations, mentions or presence; that remains the separate
core track with its own evidence methodology (§0.1, D-5).

### K.7 Roadmap placement

The validation/calibration phase sits **after** the P0/P1/principal-P2
implementation items of §G and **before** the Coverage phase is declared
complete. Experimental and out-of-scope items (§H) do not gate the benchmark.
The benchmark is not started now — it is a later, explicitly gated phase that
begins once the agreed implementation backlog is substantially complete.

---

## Appendix — how this reconciliation was produced

Method, so it can be repeated or challenged:

- Detector inventory enumerated from the live registry
  (`app.audit.checks.REGISTRY`), not from file listings — 68 checks with module,
  severity, weight, `variants` and `reads_content`.
- Every IMPLEMENTED claim traced to a module, function or line, and where
  relevant to the customer-facing catalogue string, since wording is where
  several defects turned out to live.
- Every MISSING claim preceded by a search for equivalent functionality under a
  different name (§E), because the repository deliberately names things by
  domain meaning rather than by industry jargon.
- Fast-changing external claims verified against primary sources on 2026-08-25:
  Anthropic crawler tokens; RFC 9309 robots semantics. Aggregators were not used
  as sources of truth (§0.3).
- Where behaviour could not be confirmed by reading alone, the status is PARTIAL
  rather than a guess.

Re-verification entry points: `app/audit/checks/` for detectors,
`app/audit/link_graph.py` for architecture signals, `app/audit/render/` and
`orchestrator.py:183–190` for the crawl/render boundary,
`app/audit/site_context.py:15–75` for robots and AI-bot handling,
`app/report/builder.py:55–110` for what reaches the customer.
