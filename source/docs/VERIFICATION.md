# Crawldy Completion, Remediation and Verification Report

What is known about the current product, what was corrected to get here, how each correction
was verified, and what was deliberately left alone. This is the consolidated record: the raw
audit and evidence directories it was built from have been removed, so every decisive figure,
count and identifier is reproduced here rather than cited by a path that no longer exists.

This describes a **local** verification stage. The application is not deployed.

---

## 1. Current product scope and final local status

Crawldy audits a website and returns a score from 0 to 100 with findings, evidence and
recommendations, and separately measures whether AI assistants actually mention a brand. The
three questions it answers are kept apart deliberately — see [the README](../README.md).

`IMPLEMENTED` and exercised locally: the audit engine (6 modules, 80 registered checks),
report generation (JSON and Word), a six-locale public website, a customer cabinet, an admin
area, authentication, commercial offers and credits, Paddle-backed payment plumbing, and the
AI Presence subsystem.

`OUT OF CURRENT SCOPE`: hosting, deployment, a public domain, HTTPS, HSTS, a production
Content-Security-Policy and analytics. Nothing in this repository is served publicly.

**Status: the local website and engine correction stage is closed.** The final six-locale
closure run found no new defect on the exercised surface, and the two website defects it was
run to confirm are gone. Every locally executable check then passed with zero failures,
including the PostgreSQL-dependent integration suite (§8.6) — 3298 backend tests, 731 frontend
tests, 612 integration tests, a clean type-check, a clean `mypy --strict`, and a production
build. That is completion for the agreed and exercised local scope, not a claim about defects
nobody has found.

## 2. Final verified baseline

| Property | Value |
|---|---|
| Commit | `e016ea75` on `main` |
| Engine modules | `performance`, `seo`, `ai_ready`, `llm_visibility`, `tech`, `accessibility` |
| Registered checks | 80 (`seo` 32, `tech` 14, `ai_ready` 12, `performance` 11, `llm_visibility` 9, `accessibility` 2) |
| `CRAWLER_VERSION` | `4` |
| `DETECTOR_RULES` | `14` |
| `SCORING_RULES` | `5` |
| Public website locales | `en`, `de`, `es`, `fr`, `ru`, `uk` |
| Cabinet locales | the same six (`COMPLETE_LOCALES`) |
| Public routes | 80 |
| Registered pages | 14 |
| Database migrations | 53 |

Module weights live only in `backend/app/audit/scoring.py`; the public methodology page uses a
snapshot of them that `backend/tests/test_methodology_page_facts.py` compares against the
implementation. They are deliberately not restated here — a number stored twice drifts.

## 3. Consolidated remediation registry

Every material completed correction. Intermediate attempts and failed experiments are not
listed; the final problem, cause, correction and verification are.

Status values: `FIXED`, `CALIBRATED`, `REMOVED`, `ACCEPTED DECISION`, `ENVIRONMENT-DEFERRED`.

### 3.1 Engine — coverage and honesty

**ENG-001 · Engine · `FIXED` · `8a01595`**
*Problem:* on the Lighthouse provider the accessibility module did not exist at all — it was
excluded from the score even when the provider's answer carried fully usable data.
*Root cause:* the sidecar returns the `accessibility` category in the same request as speed,
but `LighthouseProvider.measure()` only ever called `_parse_lab`. PSI had read the same
category from the start.
*Correction:* `measure()` calls the same `_parse_accessibility` PSI uses — identical reading of
identical data, not a new detector.
*Verification:* 38 stored reports from the accepted self-audit all produce a score, matching
PSI's normalization field for field. A/B on six Crawldy snapshots (64/71/64/64/64/71) and a
100-snapshot sample: no change to any issue key, module score or overall score.
*Regression protection:* `backend/tests/test_psi_accessibility.py`,
`backend/tests/test_report_accessibility.py`, `backend/tests/test_checks_performance.py`.

**ENG-002 · Engine · `FIXED` · `6e535ab`**
*Problem:* the shared parser published an accessibility score it could not verify — an empty or
garbage `auditRefs` yielded 50 from a zero denominator, and raw scores of `-0.1` and `1.1`
became `-10` and `110`.
*Root cause:* the parser trusted whatever sat in the score field.
*Correction:* a category is usable only in full — score within 0..1, at least one real
reference, every reference resolving to an audit object, every automatic audit scored 0..1, and
a denominator that exists. Otherwise the direction is **unmeasured**: no score, no counter, no
failure. The refusal logs one reason code with a credential-free URL.
*Verification:* on 38 stored Lighthouse reports the parser output is identical to `8a01595`;
PSI/Lighthouse parity exact. Full suite with PostgreSQL: 2739 passed, 3 skipped.
*Regression protection:* `backend/tests/test_psi_accessibility.py` (two tests that had demanded
the old permissive behaviour were corrected, not deleted).

**ENG-003 · Engine/Reports · `FIXED` · `0072a53`**
*Problem:* a module filter ended coverage analysis before the accessibility evidence was
checked, so accessibility requested without data kept a phantom score of 100 **and its full
weight**. Separately, `llm_visibility` was reported as complete when its semantic check had not
run.
*Root cause:* the filter was deciding what was *measured* instead of only what was *requested*.
*Correction:* the filter decides only what was requested; the data decides what was measured.
Accessibility without data is withheld with a non-failure `PARTIAL_DATA`
`notice.accessibility.not_measured` (owner decision, Option B). `llm_visibility` is partial
whenever `llm.unstated_facts` did not run. Reports and the web contract gained an additive
`withheld_reason` (`excluded_by_request` | `withheld_not_measured`). Nothing was migrated; no
score changed. `DETECTOR_RULES` 3 → 4.
*Regression protection:* `backend/tests/test_degradation.py`, `backend/tests/test_report_web.py`.

**ENG-004 · Engine · `FIXED` · `10d9922`**
*Problem:* the same defect on the performance axis — an explicit module filter ended coverage
before the provider rule ran, so requested performance with no provider result kept a score
with no degradation.
*Correction:* the unfiltered provider rule now lives in one function, `_performance_coverage`,
called once whenever performance is requested, filtered or not. With the crawler's own response
times the score is kept and marked `PARTIAL_DATA no_vitals`; with nothing, the module is
withheld as `PROVIDER_UNAVAILABLE no_metrics`. `DETECTOR_RULES` 4 → 5.
*Verification:* an explicit selection × evidence matrix, plus filtered/unfiltered equivalence on
a real snapshot.
*Regression protection:* `backend/tests/test_coverage.py`, `backend/tests/test_degradation.py`.

**RPT-001 · API · `FIXED` · `afd44e7`**
*Problem:* the additive `withheld_reason` field was unpinned, so a later change could have
altered a published contract silently.
*Correction:* the field is frozen — present in both published schemas, nullable, not required,
accepting exactly `excluded_by_request` and `withheld_not_measured`, serializing as `null` for
measured modules, with `RESULT_CONTRACT_VERSION` staying 2. No production logic changed.
*Regression protection:* `backend/tests/test_api_contracts.py`.

### 3.2 Engine — evidence and determinism

**ENG-005 · Engine · `FIXED` · `36121b5`**
*Problem:* `seo.links_to_noindex` showed the first five entries of `ctx.links.to_noindex`, and
which five — and in what order — depended on `PYTHONHASHSEED`.
*Root cause:* the link graph fills that list while iterating a **set** of normalised URLs.
*Correction:* the check sorts its copy of the complete `(source, target)` pair list before
taking five. Counts, targets, severity, weight and every score are unchanged; only the choice
and order of examples became stable.
*Verification:* identical evidence from interpreters started with `PYTHONHASHSEED` 0, 1, 7, 123.
*Regression protection:* `backend/tests/test_link_graph.py`.

**ENG-006 · Engine · `FIXED` · `bd43cf7`**
*Problem:* substring rules with no host binding counted Crawldy's own `/v1/plans` as Segment,
a third party's `sandbox-checkout-analytics.paddle.com` as a first-party counter, and the
`/admin/analytics` route as installed measurement.
*Root cause:* a curated list of vendor **names** cannot tell a proven observation from a guess.
*Correction:* every observation now carries a kind, a rule and a channel. The
`backend/app/audit/standards/analytics_vendors` registry matches hosts by name labels, so look-alikes fail; a
documented proxy on an own domain counts as a vendor only beside a co-signal from the same
vendor; an own address with a measurement marker but no vendor yields
`tech.analytics.unconfirmed` and an incomplete module rather than a passed check.
`DETECTOR_RULES` 5 → 6.
*Regression protection:* `backend/tests/test_checks_tech.py`,
`backend/app/audit/standards/analytics_vendors`.

### 3.3 Engine — route applicability and URL handling

**ENG-007 · Engine · `FIXED` · `03c2db1`**
*Problem:* every check judged every page read. A login page lost points for a missing title, a
cart for underscores in its URL, an error page for an empty description, and a social preview
card was demanded of an admin screen nobody shares. A search complaint about a route that is
outside search is not strictness — it is untrue.
*Correction:* applicability is **declared, not guessed**: eight canonical route classes × thirteen
claim classes, 104 policy cells, each declaring eight fields (A-01…A-13). The table lives in one
place rather than scattered across the checks. Intent must be *observed*: a route counts as
known-non-search only when its class is funnel, cabinet, admin or error **and** we saw `noindex`
or a robots.txt disallow. A funnel page the site itself indexes stays public content and is
judged in full.
*Regression protection:* `backend/tests/test_check_registry.py`,
`backend/tests/test_passed_checks.py`, `backend/tests/test_coverage.py`.

**ENG-008 · Engine/Localization · `FIXED` · `c6a4bf9`**
*Problem:* route classification knew two of the six launch languages. German `/preise`, Spanish
`/precios`, French `/tarifs` and Russian `/tseny` meant nothing, so a pricing page on such a site
stayed unrecognised — type-dependent rules did not apply to it and the crawl spent its budget on
product cards instead. Bare `/de` was not the home page either.
*Correction:* the language prefix is stripped from the path — but **only** when the site itself
declared that language through `<html lang>`, hreflang or its sitemap (OD-05). Two letters in a
URL are not proof: `/de/folder` on a monolingual site stays a folder and the conclusion about it
is honestly marked incomplete. Declared locales are derived once into
`SiteContext.locales_declared`, with a default so pre-existing snapshots load without migration.
The route vocabulary covers all six launch languages. `DETECTOR_RULES` 6 → 7;
`CRAWLER_VERSION` 3 → 4, because crawl order changed once translated high-value routes became
recognisable.
*Regression protection:* `backend/tests/test_localization.py`,
`backend/tests/test_logical_pages.py`.

**ENG-009 · Engine · `FIXED` · `c6a4bf9` (package v1.1)**
*Problem:* URL paths reach the route vocabulary **percent-encoded**, so a localized segment such
as a Cyrillic slug never matched its vocabulary entry.
*Root cause:* decoding was attempted on the whole path rather than per segment.
*Correction:* each segment is percent-decoded **after** splitting on `/`, never before — decoding
first would let an encoded `%2F` invent a segment boundary that the site never had.
*Regression protection:* `backend/tests/test_localization.py`.

### 3.4 Engine — structured data and content boundaries

**ENG-010 · Engine · `FIXED` · `da1de65`**
*Problem:* the "about" page was decided by substring, and each of three consumers searched
differently. `/about-cookies` became a company page, an article about someone else's team did
too, `/de/ueber-uns` never did, and a menu link whose target was never opened counted as a page
that had been read. Of nineteen canonical cases the engine reproduced nine.
*Correction:* one decision (`backend/app/audit/about_page.py`) driven by **primary intent**: an exact route
segment in the six launch languages (with the same prefix stripping as ENG-008), a title or H1
that *begins* with an intent phrase, a menu item with that phrase, or `AboutPage` markup.
`Organization` markup, a company name, "we"/"our", mission words and any substring match only
*confirm* and never create a candidate — which is why a home page carrying `Organization` and
"we" stays a home page. Content length appears nowhere in the rule: readability is the presence
of text, not its volume. The state is two-axis — read page → `PASS`+`COMPLETE`; unopened menu
candidate → `NO_VERDICT`+`PARTIAL`; substituted document → `NO_VERDICT`+`NOT_MEASURED`; no
candidate at full coverage → `FAIL`.
*Regression protection:* `backend/tests/test_site_identity.py`,
`backend/tests/test_checks_llm.py`.

**ENG-011 · Engine · `FIXED` · `a92c6b6`**
*Problem:* the breadcrumb check treated any page deeper than the entry point as a hierarchy and
counted any `BreadcrumbList` as valid. Crawl depth is our own queue, not the site's structure.
*Measured before the fix:* on 24 canonical cases, nine of fifteen states were wrong, seven
findings were false, and five of nine validity cases were wrong. On a 107-snapshot sample a flat
site got a finding in 10 cases and a half-read site in 38.
*Correction:* two centralized decisions. `hierarchy.py` establishes a hierarchy from **one**
verified parent→child link between different eligible pages; there is no number in the rule at
all — the previous "three or more" was replaced by the absence of a threshold, not a smaller
one. `breadcrumbs.py` judges validity against Google's documented contract: at least two
`ListItem`s, whole positions increasing in trail order, a name on each, a URL on each except the
last, and every URL inside the site by shared `site_scope` rather than string match.
*Regression protection:* `backend/tests/test_structured_data.py`.

**ENG-012 · Engine · `FIXED` · `ca6f487`**
*Problem:* the extractor collected headings level by level, so `h1, h3, h3, h2` was stored as
`1, 2, 3, 3`. A level skipped in reading order was not merely missed — it was
**unrepresentable**, and `seo.heading_hierarchy` could never report one.
*Correction:* one pass over the document tree replaces the per-level loop (not
`css("h1,…,h6")`, which returns matches by selector — the same grouped order in shorter form; a
test now fails if anyone simplifies it back). `PageSignals.headings_in_document_order` carries
the provenance and is set only by the extractor, only after walking a document. The rule
separates two claims: a level absent from the page *entirely* is a fact about a set and still
fires as before; a level skipped in *reading order* is a fact about order and is asserted only
where order is vouched for.
*Verification:* on the 106-snapshot corpus under two hash seeds, no rescore change at all. On 24
captured routes, detection went from 0 to 24 with no false positive on 56 controls.
`DETECTOR_RULES` 10 → 11 — the firing condition changed without any check declaration moving, so
the detector fingerprint alone would not have shown it.
*Regression protection:* `backend/tests/test_extractor.py`, `backend/tests/test_h1_family.py`.

**ENG-013 · Engine · `REMOVED` · `0f01c80` · owner decision OD-01**
*Problem:* fitness for a FAQ snippet is not a general requirement of a website, so "you have no
FAQ markup" was not a defect to charge for. The check fired on ordinary marketing headings —
Crawldy's own home page triggered it in all six languages — and Google documents no FAQ
requirement for its AI surfaces.
*Correction:* only `@register` was removed. `FaqSchemaCheck` keeps its code, module, severity,
weight, effort, variants and message keys, because the canonical rollback is putting the
decorator back rather than restoring deleted code. The applicability declaration went with it.
Six locales still carry `ai.schema.faq` and `RETIRED_MESSAGE_KEYS` marks them retained, so a
report stored earlier still renders in the language it was ordered in.
*Verification:* on the 106-snapshot corpus under two hash seeds and two pristine trees:
**13,803 − 21 + 0 = 13,782**. The 21 removals are exactly 21 `ai.schema.faq` rows on 21 sites,
one row each. Nothing was added; every other finding, applicability row, route class and module
score is identical.
*Regression protection:* `backend/tests/test_checks_ai.py`, `backend/tests/test_i18n.py`.

**ENG-014 · Engine · `FIXED` · `b442a80`**
*Problem:* the site-content sufficiency floor counted words per **URL read**, not per distinct
text. The same content under several addresses was added once per address: a 25-word placeholder
catalogue served under eight query URLs counted as 200 words, passed the 100-word floor and
scored 61 on an empty site — exactly the case the floor was written for.
*Root cause:* `group()` attaches a variant to a representative only when the page itself declares
a canonical, and a placeholder never does.
*Correction:* each group of identical content counts once, keyed by the same `canonical_text`
hash `duplicates` already uses for exact matches — there must not be a second definition of
"the same content" in the project. `DETECTOR_RULES` 12 → 13.
*Regression protection:* `backend/tests/test_content_floor.py`,
`backend/tests/test_duplicates.py`.

**ENG-015 · Engine/Localization · `FIXED` · `20599e2`**
*Problem:* `cro.no_action` asked whether a link label matched a list that lived as a tuple inside
the check. The list knew English and Ukrainian/Russian roots and nothing else, so the verdict
about an **identical** page depended on the language of its labels.
*Measured on frozen E2 evidence:* six locale copies of Crawldy's own pricing page — same page
type, same links (`/login`, `/result`), same forms, contacts and buttons — split as
`Buy the pack` (en) action found, `Купить пакет` (ru) found, `Придбати пакет` (uk) **not found**,
`Paket kaufen` (de) not found, `Comprar el paquete` (es) not found.
*Correction:* the anchors moved into the shared vocabulary, covering all six launch languages.
`DETECTOR_RULES` 13 → 14. A CTA token that is a common noun in another language must never be
added — that is how a language-independent rule becomes language-dependent again.
*Regression protection:* `backend/tests/test_checks_conversion.py`,
`backend/tests/test_conversion_locale.py`.

### 3.5 Reports — wording and severity calibration

**RPT-002 · Reports · `FIXED` · `e3eb9a7` · owner decision OD-07**
*Problem:* a guest whose audit ended badly saw a status and nothing else. The only thing
available was the raw `error` column, which is not showable — it carries exception names,
internal paths, hosts and provider names.
*Correction:* the response carries a normalized `failure_class` and a localized
`failure_reason`, written by us, in all six locales, for five classes, and never quotes the
database. `provider_failed` stays provider-neutral on purpose. Class and sentence are decided
together by one function, so they cannot disagree; an unknown class reads as `internal_error` in
both. Queued and running audits carry neither field **by absence** — the two fields are excluded
explicitly rather than by `exclude_none`, so the shape of the response does not depend on the
data in it.
*Verification:* rescoring the 106-snapshot corpus on the accepted baseline and on this tree gives
identical findings, field for field. No version axis moved.
*Regression protection:* `backend/tests/test_report_web.py`,
`frontend/app/(product)/result` tests (`result-screen.test.ts`).

**RPT-003 · Reports · `CALIBRATED` · `8d4c9ba`**
*Problem:* the consequence for `seo.sitemap.missing` said search engines find pages only through
links, "so new and deep pages reach the index with a delay". The check does not see that:
`collect_sitemap` probes the standard addresses and the one the site names, and all it observes
is the file's absence. Search-engine behaviour and indexing latency are not our measurement.
*Correction:* six owner-approved strings describing exactly what was observed. Detection,
sitemap collection, weights, severity, `issue_key`, order, evidence, recommendation and both
fingerprints are unchanged — only report text.
*Regression protection:* `backend/tests/test_precalibration_statements.py`,
`backend/tests/test_sitemap_consistency.py`.

**RPT-004 · Reports · `CALIBRATED` · pre-baseline, owner-approved**
*Problem:* the product promised what it never measured. "LLM visibility = 93" reads as "ChatGPT
mentions you in 93% of answers", and consequence strings asserted third-party behaviour
("Google and ChatGPT do not count…", "you are not named"), visitor behaviour, and categorical
absence from a partial sample.
*Correction:* the direction is named **suitability for citation** in reports (not renamed in the
database), and consequence strings were rewritten to probability. What stays categorical is only
what we read with our own eyes — a `robots.txt` disallow the site itself published. A hedge must
now sit **adjacent** to the claim it softens: the previous guard accepted a hedge anywhere in the
text, which is how "ChatGPT and similar services **can**not read your site and **do not mention
you**" passed for a long time.
*Regression protection:* `backend/tests/test_precalibration_statements.py` —
`test_consequence_does_not_promise_what_we_never_measured`,
`test_consequence_avoids_the_jargon_of_the_technical_wording`.

**RPT-005 · Reports/AI-readiness · `CALIBRATED` · pre-baseline**
*Problem/correction:* `llms.txt` is reported as a retrievability signal that the site publishes,
not as a ranking or citation guarantee; AI-readiness wording describes machine-readability of
the markup we read, and never claims an assistant's behaviour. Suitability (`llm_visibility`) and
actual presence (`backend/app/presence/`) are separate products and the engine never infers one
from the other.
*Regression protection:* `backend/tests/test_llms_txt.py`,
`backend/tests/test_precalibration_statements.py`.

### 3.6 Website, cabinet and localization

**SITE-001 · Website/Accessibility · `FIXED` · `55e197a`**
*Problem:* the language switcher showed a language code ("EN") but was named "Language" for a
screen reader, so voice control could not find it by what a person reads (WCAG 2.5.3, Label in
Name). Lighthouse `label-content-name-mismatch` fired on 35 of 38 captured runs.
*Correction:* one attribute. In compact mode the code is not visible, so the name stays the label
itself.
*Verification:* zero changed pixels; DOM difference limited to `aria-label`.
*Regression protection:* `frontend/app/components/language-switcher-name.test.ts`.

**SITE-002 · Website/Accessibility · `FIXED` · `f094cab`**
*Problem:* `CardGrid` sits directly under the page `h1` and card titles were `h3`, so the
structure skipped a level — `h1,3,3,3,2,…` on 24 of 80 routes; Lighthouse `heading-order` fired
on 9 of 38 runs.
*Correction:* the tag name only; the class string is unchanged character for character.
*Verification:* zero changed pixels, DOM difference limited to the tag.
*Regression protection:* `frontend/app/components/card-heading-level.test.ts`.

**SITE-003 · Website/Accessibility · `FIXED` · `302d20a`**
*Problem:* `Heading` derived both the tag and the type size from one `level`, so a section that
structurally had to be `h2` was written `level={3}` purely to get a smaller size. Pages emitted
`h1 → h3` with no `h2` between them.
*Measured* by capturing the production build's DOM in document order, not by reading the source:
24 affected routes (of 76 at the commit, 80 in the owner working copy), always `[1,3,3,3,…]`.
*Correction:* what was coupled was separated. `level` remains the real tag level and no value of
it draws a different tag; a new `size` controls type size alone. 96 call sites became real `h2`.
*Verification:* zero changed pixels across the affected routes.
*Regression protection:* `frontend/app/components/heading-hierarchy.test.ts` — pins the four
repaired families exactly plus a structural rule elsewhere, deliberately **not** the page
inventory, because the owner is removing pages and pinning which pages exist would break their
suite.

**SITE-004 · Website/Accessibility · `FIXED` · `3b653db`**
*Problem:* the methodology table's first row is a `<th colSpan={2}>` styled as a group heading —
to the eye a subheading, to a screen reader just a cell, leaving the table unnamed
(`table-fake-caption`, 3 runs of 3).
*Correction:* a real `<caption>` as the table's first element, hidden with `sr-only`. `caption`
is a required field of `ScoringRulesStrings`, so a locale that supplies no string fails the
build; there is no English fallback.
*Verification:* zero changed pixels in six locales; markup byte-identical after removing the
caption itself.
*Regression protection:* `frontend/app/components/scoring-rules.test.ts`.

**SITE-005 · Website/Accessibility · `FIXED` · `7289ac9`**
*Problem:* the pricing-card note was `text-accent` — `#00b2ba` on white, contrast 2.60:1, below
4.5:1 for normal text.
*Correction:* `text-accent-text` — `#007c82`, 4.99:1. Both utilities set only `color`, so
geometry, copy and behaviour are unchanged.
*Root cause of the miss:* the test asserted the class with `toContain("text-accent")`, which
accepts `text-accent-text` too — it could not see this change. It now tokenizes `className` and
requires the whole token, proven with three negative controls.
*Regression protection:* `frontend/app/content/pricing-account-note.test.ts`.

**SITE-006 · Website · `FIXED` · `48b86a5`**
*Problem:* price and button were on the card but the access condition was not, so a buyer
clicked "Buy the pack" and learned at the checkout that an account was required.
*Correction:* each card states it — one-off "No registration", pack and monthly "A Crawldy
account is required", placed under the feature list and deliberately without a tick, because it
is a condition of access rather than part of the offer.
*Regression protection:* `frontend/app/content/pricing-account-note.test.ts` reads the sources of
all six locales; a missing locale here is not cosmetic but a buyer led to a checkout unwarned.

**SITE-007 · Website · `FIXED` · `19bf361`** — short technical screens (start, waiting,
checkout) were pinned to the top leaving an empty screen below; one shell centres them.
*Regression protection:* `frontend/app/lib/result-screen.test.ts`.

**SITE-008 · Frontend build · `FIXED` · `472c86c`**
*Problem:* `next build` failed — an App Router page module may export only what Next allows, and
`page.tsx` also exported `Running`.
*Correction:* the component moved to an ordinary module beside the page together with its
dependency closure; markup, text, classes and logic transferred unchanged. The export was not
simply deleted: the guard test **renders** the component to prove the backend's raw `error` has
nowhere to reach the screen, so removing the export would have removed the only evidence.
*Regression protection:* `next build` is a required gate for every frontend change, alongside
`npx tsc --noEmit`.

**SITE-009 · Styles · `FIXED` · `404c67c`**
*Problem:* `tokens.css` carried contrast ratios in comments and its header promised they were
real. Nine had drifted from the values they described, all low by exactly 0.968 — measured once
against a different background.
*Correction:* the numbers were **removed, not updated**. A ratio is derived from the token and
its background; rewritten by hand it goes stale at the next palette change and no test checks
it. Generated CSS is byte-identical.

**SEC-001 · Security · `FIXED` · `e016ea7`**
*Problem:* the application sent no security header at all and added `X-Powered-By: Next.js` to
every response. Measured on a production build — on all 76 public routes of the clean tree and
all 80 in the owner working copy, `X-Powered-By` was present and all four headers absent.
*Correction:* exactly what depends on the application itself:
`X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
`X-Frame-Options: DENY`, `Permissions-Policy: camera=(), geolocation=(), microphone=()`, plus
`poweredByHeader: false`. Array order is response order and is deliberately fixed.
*Regression protection:* `frontend/app/lib/security-headers.test.ts` — pins the four headers and
the invariant that **every redirect keeps its exact status and Location**. It deliberately does
**not** assert that redirects lack headers: future middleware, edge hosting, CSP or HSTS must
stay free to add them.

**SEC-002 · Security/Crawlers · `FIXED` · `e6823ea`**
*Problem:* the training-crawler policy was on paper only. The group was closed with
`anthropic-ai`, a token no longer in Anthropic's documentation, while the current training
crawler `ClaudeBot` passed under the wildcard.
*Correction:* one token added. `Claude-SearchBot` and `Claude-User` stay open deliberately —
they are search and human-initiated retrieval, which is the visibility the policy exists to
protect.
*Regression protection:* `frontend/app/robots-policy.test.ts`.

**LOC-001 · Localization · `FIXED` · owner layer, bound by test**
*Problem:* the cabinet was written in two locales while the public site had six, so a German
visitor entering the cabinet dropped to English.
*Correction:* `COMPLETE_LOCALES` now lists the same six launch locales as
`PUBLIC_SITE_LOCALES`, and the cabinet catalogue was completed to match.
*Regression protection:* `frontend/app/lib/cabinet-locales.test.ts` binds the two constants
together so they cannot drift apart silently; `frontend/app/lib/i18n-inventory.test.ts` guards
catalogue completeness.

**LOC-002 · Localization · `FIXED` · owner layer**
*Problem:* the cabinet has no locale prefix in its URL, so the public site's language was lost on
the way in and out; a German visitor returned to the English home page.
*Correction:* the last public locale is remembered in the browser under `crawldy_site_locale`,
and every route back to the site is built from it. The **profile wins** over that memory when it
has a language — a deliberate choice outranks the trace of a visit; the memory covers the
locales the profile cannot express.
*Regression protection:* `frontend/app/lib/locale-links.test.ts`,
`frontend/app/lib/landing.test.ts`.

**LOC-003 · Localization · `FIXED` · owner layer**
*Problem:* the guest result link carried the language only for Ukrainian — `ctaOf` returned
`/result?lang=uk` and a bare `/result` for every other locale, so a German visitor from the
German page got an English result although the screen had existed in six languages all along.
*Correction:* the rule is "English without a parameter, every other locale with `?lang=`",
applied everywhere rather than as a special case.
*Regression protection:* `frontend/app/content/copy-corrections.test.ts` requires it for all five
non-English locales.

**LOC-004 · Reports/Localization · `FIXED` · pre-baseline**
*Problem:* locale-parity tests compared locales against each other, so a key missing from **all
six** frames passed every check while the client saw a raw key in the Word document.
*Correction:* parity is no longer only comparative — the check looks for raw keys in
`document.xml` of both fixtures, because some keys live only in the document without a score.
*Regression protection:* `backend/tests/test_report_locale_parity.py`, `backend/tests/test_i18n.py`.

### 3.7 Documentation and inventory consistency

**DOC-001 · Documentation · `FIXED` · `8324cd7`**
*Problem:* `CLAUDE.md` named 79 checks in one line and listed 82 across modules in another; the
registry had 80. Three hand-written numbers, none of which checked anything.
*Correction:* numbers corrected from the measured registry (`ai_ready` 13→12,
`llm_visibility` 10→9, total 79→80) and a test now **parses** `CLAUDE.md` and compares it with
`REGISTRY`. A second hand-written list inside the test would have been the same disease under
another name. Claims are split deliberately so a total shift, a module shift, a vanished module,
a duplicate code and an internal contradiction fail on different lines; proven with five negative
controls.
*Regression protection:* `backend/tests/test_check_registry.py`.

**DOC-002 · Documentation · `FIXED` · `cf777b1`**
*Problem:* `CLAUDE.md` claimed "1648 tests" where the suite had 3192 clean and 3268 with the
owner layer — wrong by more than double, and volatile by construction.
*Correction:* the number was **removed, not refreshed**. Substituting 3192 would reintroduce the
same defect with a newer date. A guard rejects a test count reattached to that paragraph, while
historical statements elsewhere in the file legitimately name past run counts — and the guard
proves that boundary rather than passing vacuously.
*Regression protection:* `backend/tests/test_check_registry.py` guard.

**DOC-003 · Documentation · `FIXED` · this series**
Five canonical documents replaced a stale entry point and scattered decisions:
[README.md](../README.md), [docs/APPLICATION.md](APPLICATION.md), [docs/ENGINE.md](ENGINE.md),
[docs/DEVELOPMENT.md](DEVELOPMENT.md) and this report. Deeper references
(`ARCHITECTURE.md`, `ROADMAP.md`, `VALIDATION.md`, `PHASE4_ARCHITECTURE.md`) were not
superseded. Every path, link, command, script, environment-variable name, count, locale, module,
version constant, security header, mirror host and closure figure in them is checked
mechanically against the code — 160 checks, 0 problems at the time of writing.

### 3.8 Commerce and entitlement safeguards

These were implemented in the owner layer and are confirmed by tests present in the repository.

**COM-001 · Backend/Commerce · `FIXED`** — entitlement comes only from a **verified provider
event**, never from the browser returning to a success URL. Returning from checkout is not proof
of payment.
*Regression protection:* `backend/tests/test_entitlement_invariants.py`,
`backend/tests/test_payment_security.py`,
`backend/tests/integration/test_billing_events.py`.

**COM-002 · Backend/Commerce · `FIXED`** — the fake billing provider is not registered at all
when the environment is production; the gate lives in the registry rather than in a route, so
checkout, webhook and anything added later all pass through it.
*Regression protection:* `backend/tests/test_payment_security.py`,
`backend/tests/integration/test_commercial_config.py`.

**COM-003 · Backend/Commerce · `FIXED`** — audit credits and AI Presence credits are separate
quantities spent separately (`credit_type`), so a package cannot promise units it does not
contain; a failed payment is not a terminal purchase state; a second transaction against the
same intent becomes its own purchase rather than being silently absorbed; reconciliation credits
only what the provider itself calls paid and holds no authority of its own.
*Regression protection:* `backend/tests/test_entitlements.py`,
`backend/tests/test_billing_state_machine.py`,
`backend/tests/integration/test_payment_reconciliation.py`,
`backend/tests/integration/test_payment_state.py`,
`backend/tests/integration/test_billing_concurrency.py`,
`backend/tests/integration/test_refund_access.py`.

### 3.9 Test contract

**QA-001 · QA/test contract · `FIXED` · `CRAWLDY-FINAL-GREEN-CLOSURE-01`**

*Problem:* `test_api_contracts.py::test_the_engine_surface_is_untouched_by_this_phase` asserted
`DETECTOR_RULES == "12"` and `detector_version() == "2aee7ec30532"`. The engine has fourteen
detector rules and fingerprint `3b9a556ab798`, so the test failed on every run.

*Root cause:* an **uncommitted owner-layer edit** to that test file reverted two assertions to
the values from before ENG-014 and ENG-015 while the implementation moved on. The test and the
code had otherwise tracked each other exactly through every accepted commit — `e3eb9a7` 12/12,
`b442a80` 13/13, `20599e2` 14/14, HEAD 14/14 — and the owner's working copy is the only place
they diverge.

*Proof that production code was already correct, established before the edit:*

- `backend/app/audit/versions.py` is **clean** — not owner-modified — and reads
  `DETECTOR_RULES = "14"`, `SCORING_RULES = "5"`, `CRAWLER_VERSION = "4"`, with
  `detector_version()` returning `3b9a556ab798`, a registry of 80 checks and 80 declarations,
  executed from a disposable copy in which `app` was proven to resolve to that copy.
- The **HEAD version of the same test passes** against that engine, while the owner's version
  fails, in the same copy.
- **Four other test modules already assert the same values** — `test_checks_ai`,
  `test_content_floor`, `test_conversion_locale`, `test_free_paid_boundary` — and all passed.
  The project's own corpus contradicted the single stale assertion.
- No accepted decision anywhere asks for a twelve-rule engine; §2 and ENG-014/ENG-015 record
  12 → 13 → 14 as accepted.

*Correction:* exactly two byte-level substitutions in that one file — `"12"` → `"14"` and
`"2aee7ec30532"` → `"3b9a556ab798"`. The file was **not** replaced with its HEAD version: the
same uncommitted edit also adds eight legitimate route rows (presence export and admin payment
endpoints), and replacing the file would have deleted them. Byte count, line-ending counts and
encoding are unchanged; the diff against HEAD went from +10/−2 to **+8/−0**. No production code
was touched.

*Verification:* the test alone, its module (34), ten related engine and API-contract modules
(345) and Ruff on the modified file — all clean. Then the complete suite with a database
available: **3298 passed, 3 skipped, 0 failed**, and the PostgreSQL integration suite
**612 passed, 0 failed, 0 skipped** (§8.6).

*Regression protection:* the assertion is again identical to HEAD's, and five test modules now
pin the same engine identity, so a future drift fails in five places rather than passing
silently in one.

## 4. Accepted product decisions

Not defects, and deliberately not treated as findings against the product.

| ID | Decision |
|---|---|
| AD-001 | Approved page **title lengths**. The non-Ukrainian titles measure 61–66 characters against the engine's 60-character threshold; the wording is approved and is not shortened to satisfy our own check. |
| AD-002 | Approved **meta-description lengths**, on the same basis. |
| AD-003 | **No analytics.** An owner product and privacy decision, not an omission. The engine's `tech.analytics` finding against Crawldy's own site is therefore expected. |
| AD-004 | A deliberate **AI-training-crawler policy** (training disallowed, search and human-initiated retrieval open) and an **empty `sameAs`**. |
| AD-005 | **Accessibility withheld, Option B** — when performance is excluded, accessibility is withheld with a non-failure notice rather than scored or silently dropped. |
| AD-006 | **FAQ markup is not required** (OD-01) — see ENG-013. |

## 5. Removed or retired behaviour

| What | How | Why |
|---|---|---|
| `ai.schema.faq` scored check | `@register` removed; class, code, severity, weight, variants and message keys retained (ENG-013) | Not a general requirement of a website. Canonical rollback is restoring the decorator, not deleted code. |
| Its applicability declaration | Row removed from `CHECK_DECLARATIONS` | `build_evidence()` iterates declarations independently of the registry, so a leftover row would have granted applicability to a check that no longer exists. |
| Volatile test total in `CLAUDE.md` | Removed, never replaced (DOC-002) | Wrong by construction — the next commit makes any fixed number false. |
| Contrast ratios in `tokens.css` comments | Removed, not updated (SITE-009) | Derived values restated by hand drift from what they describe. |
| Legacy pre-score LLM layer | Present but disabled (`LLM_ENABLED=false`) | It sits **before** scoring and can create a finding; `backend/app/enrich/` sits after deterministic truth and has no path back. They deliberately share no code. |

## 6. Environment-dependent items outside the completed local stage

None of these is an open defect in the finished local stage; each needs an environment that does
not exist yet.

**ENV-001 · Content-Security-Policy · `ENVIRONMENT-DEFERRED`.** Measured rather than guessed, and
**both verdicts are negative: not ready for enforcement and not ready for Report-Only.** The
measured candidate is a measurement artifact and must not be shipped. Decisive findings:

- 177 of 744 unique inline script hashes (clean tree) and 193 of 882 (owner overlay) **change
  between two builds of identical source**, so a hash-based `script-src` is not viable.
- Nonces cannot exist in the 92 of 98 prerendered documents without moving them to per-request
  dynamic rendering.
- Both `script-src` and `style-src` would require `'unsafe-inline'`; no wildcard, `unsafe-eval`,
  `data:` or `blob:` is present or needed.
- The candidate still contains the local placeholder `http://127.0.0.1:8099` in `connect-src`,
  and uses `frame-src 'none'`, which is incompatible with the production shape of the Paddle
  overlay and Turnstile frames.
- Zero residual violations were achieved **only on the exercised, incomplete surface** and only
  with `'unsafe-inline'`.
- There is no `report-uri`/`report-to` collection path, so a deployed Report-Only policy would
  produce no centralized telemetry.
- Paddle and Turnstile never initialized, because both read configuration from the backend and
  every `/v1/*` request answered `ERR_CONNECTION_REFUSED`; the authenticated cabinet is likewise
  unexercised, as `/app` redirects to `/login` without a session.

**ENV-002 · HSTS · `ENVIRONMENT-DEFERRED`.** It depends on the HTTPS hosting environment, which
does not exist. Set blind it either does nothing or locks a browser onto a scheme the site does
not serve.

**ENV-003 · Paddle in production · `ENVIRONMENT-DEFERRED`.** The adapter, webhook verification,
reconciliation and entitlement rules are implemented and unit-tested (COM-001…COM-003), but live
payment completion was never exercised. Closing this needs a disposable backend and a Paddle
sandbox.

**ENV-004 · Turnstile in production · `ENVIRONMENT-DEFERRED`.** Same shape: the widget's site key
is fetched from the backend before the script loads, so with no backend reachable it never
initializes.

**ENV-005 · Hosting, deployment, public domain, HTTPS, production API origin ·
`ENVIRONMENT-DEFERRED`.** The production value and origin contract for `NEXT_PUBLIC_API_URL` is
unresolved.

## 7. Final verification results

### 7.1 The final six-locale closure run

Task `CRAWLDY-FINAL-LOCAL-CLOSURE-RUN-01`, run against HEAD `e016ea75` plus the complete
verified owner layer. Clean HEAD alone was not audited.

Engine configuration, identical to the previous comparable audit:

```
--max-pages 25 --max-depth 2 --no-llm --no-perf
```

Engine identity of that run: crawler `4`, detector `3b9a556ab798`, scoring `aa4ecc62a5a3`,
config `0cff99ff0f90`.

**Coverage.** Six locale entry points, all six succeeded. The engine read **16 pages per
locale** out of 80 known routes. That is a sample governed by the crawl budget — **it is not a
claim that every engine rule ran against every one of the 80 public routes.** To keep the two
corrected website defects off a sample, all **80 public routes were additionally checked at HTTP
level** for exactly those two defects.

| Measure | Result |
|---|---|
| Engine score, each of `uk` `en` `de` `es` `fr` `ru` | **68** (prior comparable run: also 68 in all six) |
| `seo.heading_hierarchy` | disappeared in all six locale results |
| `cro.no_action` | not emitted in any locale |
| Heading-level jumps, 80 HTTP-checked routes | **0** |
| The four accepted security headers | matched on all applicable routes |
| `X-Powered-By` | absent |
| New confirmed defects on the exercised surface | **none** |
| Findings | 8 `CONFIRMED CLOSED`, 1 `ACCEPTED PRODUCT DECISION`, 2 `UNEXERCISED / ENVIRONMENT-LIMITED` |

The unchanged score is the expected outcome, not a failure to improve: the heading rule carries
no weight in the score, and `tech.security_headers` still fires for the headers that remain
deliberately absent. The rule-level change is visible where it should be — a finding disappeared
and none appeared.

**Correction order, established from commit ancestry rather than from clocks:** `b442a80`
(ENG-014) → `20599e2` (ENG-015) → the previous website audit, built from HEAD `20599e22` with
detector `3b9a556ab798` → `302d20a` (SITE-003) → `e016ea75` (SEC-001). That earlier audit
therefore **contained both engine corrections** and neither website correction; the closure run
closed exactly that gap.

### 7.2 An accepted, content-driven locale difference

`seo.title:too_long` fired in `en`, `de`, `es`, `fr` and `ru` and not in `uk`. The cause is the
content, not the engine: the non-Ukrainian titles measured 61–66 characters against the existing
60-character threshold, and the Ukrainian crawl contained no title over it. This is the opposite
of the former locale-dependent engine defect (ENG-015), which produced different verdicts from
byte-identical markup. See AD-001.

### 7.3 Not exercised in that run

The comparable final run used `--no-perf`. Performance was therefore excluded, and accessibility
did not execute because it shares that engine path. External PSI cannot audit a private loopback
target. This result does not imply that locally executed Lighthouse is universally unable to
inspect localhost. Neither performance nor accessibility was counted as passed.

In the run's own output, `performance` produced a score entry the engine marked excluded in every
locale, and `accessibility` produced no score entry at all.

### 7.4 Historical coverage reconciliation

Every accepted historical task family maps to a registry entry, to evidence that produced no
product change, or to a result that superseded it. This is what makes removing the old task
directories safe: nothing unresolved is discarded with them.

| Historical family | Disposition |
|---|---|
| G1 — accessibility ingestion | ENG-001, ENG-002 |
| G2 — coverage honesty under filters | ENG-003, RPT-001 |
| G2.1 / G2.2 — performance coverage | ENG-004 |
| G3 — evidence determinism, analytics classification | ENG-005, ENG-006 |
| G4a / E-12 — localized routes, URL encoding | ENG-008, ENG-009 |
| G4b | `SUPERSEDED BY FINAL RESULT` — never started; no accepted decision is open |
| G5a — About page detection | ENG-010 |
| G5b — breadcrumbs / hierarchy | ENG-011 |
| G5c — heading document order | ENG-012 |
| G6 — FAQ retirement | ENG-013 |
| G7 | `SUPERSEDED BY FINAL RESULT` — never started |
| G5/G6 mutation runs (`g5*mut`, `g4*mut`, `g6v*`) | `EVIDENCE ONLY — NO PRODUCT CHANGE` — mutation testing of the above |
| E-01 / E-09 | ENG-003 |
| E-04 | DOC-001 |
| E-05 | DOC-002 |
| E-10 | ENG-010 |
| E-11a/b/c | ENG-006 |
| E-13 / E-14 (LATER v1…v7) | RPT-002 — only the final package was accepted; v1–v6 are superseded iterations |
| E1 — website copy inventory | RPT-003 (E1-01); E1-02/E1-03 verified already correct; E1-04/E1-05 untouched by decision |
| E2 — local accepted vs owner overlay | `EVIDENCE ONLY — NO PRODUCT CHANGE` — its frozen evidence is the measurement quoted in ENG-015 |
| Route applicability (A-01…A-13) | ENG-007 |
| Finding 01 | ENG-014 |
| Finding 02 | ENG-015 |
| S-10 | SITE-005 |
| S-11 | SITE-004 |
| `SITE-A11Y-HEADING-01` | SITE-003 |
| `SITE-SECURITY-HEADERS-01` | SEC-001 |
| `SITE-CSP-MEASUREMENT-01` | ENV-001 — `EVIDENCE ONLY — NO PRODUCT CHANGE`; read-only by design, no commit |
| `CRAWLDY-FINAL-LOCAL-CLOSURE-RUN-01` | §7.1 |
| `CRAWLDY-CANONICAL-DOCS-AND-INVENTORY-01` | DOC-003 |
| Calibration / benchmark corpus runs | `EVIDENCE ONLY — NO PRODUCT CHANGE` — the reusable part is `backend/benchmark/`, which is retained (§7.5) |
| Frontend build-failure investigation | SITE-008 |
| Repository reconnaissance, site audit batches, note audits | `EVIDENCE ONLY — NO PRODUCT CHANGE` |

### 7.5 Calibration data retained in the repository

`backend/benchmark/` (125 files, ~121 MB) is retained in full. 23 files are tracked; 102 are
gitignored, which makes them invisible to git but **not** disposable — a rebuild reproduces none
of them. **123 non-cache files are allowlisted**; the two excluded entries are `__pycache__`
and are regenerable.

**Classification: a required test and benchmark-tooling dependency.** Not a runtime application
dependency, and it should not be described as one — no module under `backend/app/` references
these paths, and `backend/app/report/benchmark.py` is an unrelated concept (comparing a client
with competitors). The consumers, established by searching the current code rather than assumed:

- **Eight backend test modules** read the snapshots directly — `test_anchor_text`,
  `test_duplicates`, `test_js_discovery`, `test_link_attribution`, `test_mixed_content`,
  `test_redirects`, `test_sitemap_consistency`, `test_transport`. They glob
  `benchmark/snapshots/*.json` and iterate it, and `test_js_discovery` takes `next(...)` of that
  glob, so an empty directory raises rather than skipping.
- **Benchmark tooling** uses the retained paths: `backend/scripts/benchmark/cli.py`
  (`DEFAULT_ROOT = benchmark/runs`) and `backend/scripts/backfill_bench_costs.py`
  (`backend/benchmark/v2-model-comparison/results-live.json`).

The data holds the corpus snapshots, sweep packets, pilot runs and human review verdicts that
every rule change is A/B-tested against, and it cannot be regenerated: re-crawling produces a
different run, and two live runs of this engine are not comparable — the spread between them is
larger than most changes being evaluated. That is why a rule change is measured by rescoring
**the same snapshots** before and after (`scripts/rescore_dir.py`), never by running the crawler
twice.

### 7.6 Scope of this statement

The verdict applies to the agreed and exercised scope. It is not, and was never framed as, a
claim that no unknown defect exists.

## 8. Cleanup record and final product integrity

Recorded by `CRAWLDY-REMEDIATION-REPORT-AND-MAXIMUM-SAFE-CLEANUP-01`.

**Historical raw evidence was intentionally removed after the consolidation above was written
and verified.** Sections 3 to 7 exist so that it did not need to be kept: every decisive figure,
count, identifier and fingerprint from those audits is reproduced here, and §7.4 maps each
historical task family to a registry entry, to evidence that produced no product change, or to a
result that superseded it. No historical archive was created.

### 8.1 What was removed

| Category | Targets | Size |
|---|---:|---:|
| Historical audits and evidence packages (G4/G5/G6, E-series, LATER, calibration, recon, site batches) | 177 | 99.58 GB |
| Duplicate or reproducible areas — every file verified present in a retained area | 62 | 11.56 GB |
| Scratch material of unresolved purpose, named in the cleanup authorization | 6 | 3.42 GB |
| Consolidated closure, CSP and owner-freeze evidence | 3 | 186.2 MB |
| The temporary inventory and review directory | 1 | 37.4 MB |
| Brand-asset originals in `Downloads`, after verified transfer | 7 | 3.18 MB |
| A duplicate copy of one review document | 1 | 61.8 KB |
| Desktop shortcuts to the old workspace | 2 | 4.2 KB |
| **Total authorized targets** | **259** | **114,789,938,486 bytes (114.79 GB)** |

Plus the disposable execution copy used for §8.4 (22,651 files, 1.39 GB) and the quarantine
marker. Permanently removed in total: **628,957 files, 116,175,673,538 bytes**. Free space on
the work volume went from 270 GiB to 379 GiB — 109 GiB recovered, which is the same quantity in
binary units.

Dependency trees (`node_modules`, `.venv`, `.next`) inside those historical worktrees went with
them. The **active** development environment was deliberately left in place: `frontend/node_modules`
and `backend/.venv` are present and were used for the verification run.

### 8.2 How it was made safe

- A **933-file product allowlist** was frozen first, built twice by two independent
  enumerations — one asking git, one walking the filesystem — which agreed exactly; their only
  divergence was the nine intentional owner deletions, which are recorded separately.
- Every target was an **exact canonical absolute path**, never a pattern. Each was checked to
  exist, to not be a product/workspace/drive root or a broad parent, to not contain or overlap
  any allowlisted path, and to not be a reparse point.
- Everything was **moved to one quarantine directory first** and permanently deleted only after
  the integrity gate and the verification run had both passed. Exactly one directory was removed
  recursively.

Three defects were found by running this process rather than by reading it, and each is worth
keeping because each looked like success:

1. **A rollback hole.** A target was recorded as moved only *after* its verification passed, so
   the one target that failed verification had already moved and was invisible to the restore —
   which then reported a complete rollback. Corrected to record the move first; a later
   36-target rollback then restored cleanly with zero failures.
2. **MAX_PATH hid 14 files.** The quarantine name must carry a 52-character task ID, which
   lengthens every path inside a moved tree by about 60 characters. Windows does not raise past
   260 characters — `os.walk` simply cannot enumerate, so verification counted fewer files than
   were moved and read as data loss. No quarantine name short enough to avoid this can also
   contain the task ID, so the limit was removed with extended-length paths instead.
3. **A junction inflated the total by 23 GB.** `os.path.islink` is `False` for a Windows
   junction and `os.walk` descends into one regardless, so a single `node_modules` tree was
   counted through 28 junctions. The true size is 114.79 GB, not 137.71 GB. All 32 reparse
   points were then resolved: every destination lay inside the target set, and **none reached
   the product**.

### 8.3 What was preserved

- The complete current product: 933 allowlisted files, 135 MB. The allowlist frozen **before**
  the cleanup has digest
  `5c9168eaa6277699a5fc1e72c3fc6a326804693506712db7fa22cc81b0581461`; that is the value the
  integrity gate compared against, and after the deletion 0 files were missing and 0 had changed
  content. The **final** digest additionally covers this report and the README rows this task
  added, so it is not repeated here — a document cannot quote a hash that covers itself without
  going stale the moment it is written. It lives in
  [PRODUCT-BASELINE.json](PRODUCT-BASELINE.json), which states that it excludes its own hash.
  The two differ by exactly the authorized documentation changes and by nothing else.
- The **full owner layer** — 222 files, including 152 modified and the nine pending deletions,
  all unchanged.
- **`backend/benchmark/` in full**, 123 allowlisted files (plus two regenerable `__pycache__`
  entries), for the reason in §7.5.
- **Seven brand assets**, transferred into `brand-assets/` and verified byte-for-byte by SHA-256
  before their originals were removed. They were deliberately not placed in
  `frontend/public/brand/`: that directory is served by Next at `/brand/…` and its own README
  defines it as the web versions the components render. A vector source and four social banners
  are neither, and publishing them was not part of preserving them.
- The owner's OneDrive project folder, untouched (21 files). Only a duplicate copy of one
  document, held in a second folder, was removed.

### 8.4 Verification after the cleanup

Run in a disposable copy of the preserved product, not in the repository. The copy carried all
933 allowlisted files byte-identically, including all 222 owner-layer files, the brand assets
and the benchmark data. The editable install in `backend/.venv` maps the package `app` to the
live worktree, so it was stripped and `app` was proven to resolve to the copy
(`<WORK_DIR>\backend\app\__init__.py`) and to be absent from an unrelated directory —
otherwise the suite would have tested the owner's tree while appearing to test the copy.

| Command | Result |
|---|---|
| `npx tsc --noEmit` | clean |
| `npm run test` | 38 files, **708 passed**, 23 skipped, 0 failed |
| `npm run build` | production build succeeded |
| `ruff check app tests scripts` | all checks passed |
| `mypy --strict …` | no issues in 135 source files |
| `pytest -q` | **2693 passed**, 607 skipped, 1 failed |

The 607 backend skips are the integration suite, which collects 612 tests and requires
PostgreSQL — a documented prerequisite in [DEVELOPMENT.md](DEVELOPMENT.md). No database was
started for this run, and none of those tests reads removed material.

**The one failure is not attributable to the cleanup, and was not repaired.**
`test_api_contracts.py::test_the_engine_surface_is_untouched_by_this_phase` asserts
`DETECTOR_RULES == "12"`; the value is `"14"`. The committed file at HEAD asserts `"14"` and
detector `3b9a556ab798`, matching the code — the `"12"` exists only in an **uncommitted
owner-layer edit** that pins the engine identity from before ENG-014 (`b442a80`, 12 → 13) and
ENG-015 (`20599e2`, 13 → 14). Running that exact test from HEAD's version of the file, in the
same copy, passes. It is an owner file, and this task does not change product code to make a
test pass.

**On how that run was summarised.** Its closing summary presented the removal as following quarantine, integrity verification and
core test suites that had all succeeded. That was too broad: the ordinary backend suite produced
**one failure**, and a summary implying otherwise is wrong even when every individual claim
beneath it was accurate. The non-regression conclusion did not
rest on a clean suite — it rested on the 933-file product allowlist being byte-identical before
and after, on the frontend type-check and production build succeeding, and on the failure being
traced to an uncommitted assertion that reads only in-repository constants. That reasoning
stands; the summary sentence does not, and is not repeated. `CRAWLDY-FINAL-GREEN-CLOSURE-01`
(§8.6) corrected the assertion and re-ran everything.

### 8.5 Final product integrity

| Check | Result |
|---|---|
| Allowlisted files present and byte-identical | 933 / 933 |
| Product paths that vanished | 0 |
| Owner-layer files modified or lost | 0 of 222 |
| Intentional deletions preserved | 9 / 9 |
| Brand assets at their destinations | 7 / 7 |
| `backend/benchmark/` files intact | 123 / 123 |
| Lockfiles changed | none |
| `HEAD` / branch | `e016ea75` on `main`, unchanged |
| Staged paths | 0 |
| Commit created | no |
| Pushed | no — the repository has no remote |
| Quarantine or disposable tree remaining | none |

The machine-readable form of this state, including every file hash, is
[PRODUCT-BASELINE.json](PRODUCT-BASELINE.json).

### 8.6 Final green closure

`CRAWLDY-FINAL-GREEN-CLOSURE-01` corrected the one stale assertion (QA-001) and re-ran every
locally executable check, this time including the PostgreSQL-dependent suite that the previous
run had skipped. All of it ran in a disposable copy of the product with the editable install
stripped, so `app` resolved to the copy rather than to the owner's worktree.

| Check | Command | Result |
|---|---|---|
| Frontend tests | `npm run test` | 38 files, **731 passed**, 0 skipped, 0 failed |
| Frontend type-check | `npx tsc --noEmit` | clean |
| Frontend build | `npm run build` | compiled; 100 static pages |
| Ruff | `ruff check app tests scripts` | all checks passed |
| mypy | `mypy --strict …` | no issues in 135 source files |
| Backend suite (with database) | `pytest -q` | 3301 collected, **3298 passed**, 3 skipped, 0 failed, 524.35 s |
| Engine and API contracts | `pytest` over 10 related modules | **345 passed** |
| PostgreSQL integration | `pytest -q tests/integration` | 612 collected, **612 passed**, 0 skipped, 0 failed, 272.66 s |
| Product baseline integrity | recomputed twice, independently | 933 files, digests agree |

**The PostgreSQL suite was genuinely exercised, not assumed.** Its skip gate is
`TEST_DATABASE_URL` in `backend/tests/integration/conftest.py`, which skips the whole session when the
server is unreachable. A disposable `postgres:16-alpine` container (the image `docker-compose.yml`
documents) ran on port 55432 with task-specific credentials generated in memory, `--rm` and a
`tmpfs` data directory, so nothing persisted and nothing was written to `.env` or to the
repository. The suite's own fixture then created `crawldy_test_<uuid>`, applied
`alembic upgrade head`, and dropped it. The container was stopped and removed afterwards; the
owner's own `seoagent-*` containers were never started, stopped or modified.

**The three remaining skips are named, not waved through.** All three are parametrized cases in
`tests/test_site_scope.py:111` whose URL is not `http`/`https`; the extractor filters those
schemes earlier, so the assertion does not apply. They are an in-test guard, unrelated to
PostgreSQL and requiring no external credentials.

Collection reconciles exactly across both runs: 2693 + 607 + 1 = 3301 before, 3298 + 3 + 0 =
3301 now. The 607 database skips became passes and the single failure became a pass.

This states completion for the agreed and exercised local scope. It is not a claim of universal
correctness, and nothing here implies the software is free of unknown defects.

## 9. Password recovery and password policy

`CRAWLDY-AUTH-PASSWORD-RECOVERY-01` added password recovery and authenticated password change,
and raised the password minimum to twelve characters — declared once, rather than in the five
places that previously held it.

### 9.1 What was delivered

A person who has forgotten their password opens **Forgot your password?**, placed directly
below the sign-in button on the login form and in no navigation. The request screen answers
the same way for every address, the letter carries a one-time link, and the reset screen
checks that link before asking for anything. A signed-in person changes their password from
**Change password** in the account menu; the cabinet's five-item navigation grid is unchanged.

All three screens exist in the six launch locales (en, uk, de, es, fr, ru), and so does the
letter itself — subject, plain-text part and HTML part. The locale survives the whole journey:
the reset link carries it, and the language of the letter comes from the recipient's profile,
falling back to the language of the page the request came from.

Migration `0054` adds `password_resets`. The table stores a SHA-256 of the token and never the
token; a partial unique index (`used_at IS NULL AND superseded_at IS NULL`) lets one live link
exist per person, so asking again retires the previous one in the database rather than in code.

### 9.2 Delivery runs in the worker, not in the request

Delivery was moved into the existing ARQ queue. The HTTP route performs no account lookup at
all: it normalizes the address, enqueues `send_password_reset_task` for **every** address, and
returns. The worker does the lookup and stops silently when there is no account.

Identical response bodies were never sufficient on their own. While the route looked the
account up itself, a known address answered after a database query and an SMTP connection and
an unknown one answered immediately; the difference was in the timing, not the body. Both
cases are now one enqueue, so there is nothing left to measure. If the queue itself is
unavailable, both cases receive the same `503` and the log records only the exception type.

A temporary SMTP failure is retried twice with a growing pause, and the token is minted once,
before that loop — a retry sends the same letter rather than a second link. The task never
raises, because ARQ would otherwise run it again from a fresh session and issue a second
token. A delivery that fails for good does not cancel the token either: an SMTP timeout is not
proof that nothing was sent, and cancelling would kill a link the person may already hold.

### 9.3 Registry

**AUTH-001 · Backend/Auth · `FIXED`** — the recovery request cannot be used to discover whether
an address is registered. Known and unknown addresses receive the same status, the same body,
the same headers and the same queue path, and the route opens no database session.
*Regression protection:* `backend/tests/test_password_recovery.py`,
`backend/tests/integration/test_password_recovery.py`.

**AUTH-002 · Backend/Auth · `FIXED`** — the reset token exists in clear text only in memory and
in the letter. The database holds its SHA-256; a copy of the database is therefore not a set of
account keys. Single use is enforced by a conditional `UPDATE` and its row count, not by a
read-then-write, so two simultaneous requests cannot both succeed.
*Regression protection:* `backend/tests/integration/test_password_recovery.py`.

**AUTH-003 · Backend/Auth · `FIXED`** — a password that fails the policy does not spend the
link. The policy is checked before the token is claimed, so a mistyped new password leaves the
person able to try again instead of locked out with a dead link.
*Regression protection:* `backend/tests/integration/test_password_recovery.py`.

**AUTH-004 · Backend/Auth · `FIXED`** — both setting a password by link and changing it while
signed in revoke every session, including the one making the request, and clear any lockout.
Changing a known password still requires the current one: otherwise a stolen session becomes a
stolen account.
*Regression protection:* `backend/tests/integration/test_password_recovery.py`,
`backend/tests/integration/test_identity.py`.

**AUTH-005 · Backend/Auth · `FIXED`** — recovery has its own rate limit with two buckets, one
per address and one per client, so neither a single client probing many addresses nor many
clients flooding one mailbox is free. The address bucket keys on a hash, so the counter never
becomes a list of who tried to recover.
*Regression protection:* `backend/tests/integration/test_password_recovery.py`.

**AUTH-006 · Backend/Auth · `FIXED`** — no log line carries an address, a token, a reset link or
the text of a mail-library exception. Only the recipient's domain, the subject and the
exception type are recorded.
*Regression protection:* `backend/tests/test_password_recovery.py`.

**AUTH-007 · Backend/Config · `FIXED`** — production refuses to start without `MAIL_SMTP_HOST`,
`MAIL_SENDER` and an `https` `PUBLIC_APP_URL`, and `/health/ready` reports unhealthy outside
local when no mail transport is configured. The `no-reply@crawldy.ai` fallback was removed: an
address that fails SPF from a third-party relay looks like a successful send and behaves like a
lost letter. Captured `.eml` output is available only when `APP_ENV` is `local`.
*Regression protection:* `backend/tests/test_password_recovery.py`.

**AUTH-008 · Backend/Auth · `FIXED`** — the minimum length of a new password is twelve
characters, declared once in `backend/app/identity/passwords.py` and once in
`frontend/app/lib/password-policy.ts`, with a test binding the two. Before this task the number
lived in five places and said three different things: the server accepted ten, the interface
asked for twelve, and the guest-claim schema admitted eight.
*Regression protection:* `backend/tests/test_password_policy.py`,
`frontend/app/lib/password-recovery.test.ts`.

**AUTH-009 · Backend/Auth · `FIXED`** — raising the minimum locks nobody out. The policy applies
to creating a password, never to verifying one. Sign-in re-hashes a password when the argon2
parameters have been raised, and that path previously ran the policy check as well — so on the
day those parameters changed, a person whose password predated the new minimum would have
entered it correctly and received a server error from inside login. Re-hashing now uses a
separate entry point that performs no policy check.
*Regression protection:* `backend/tests/test_password_policy.py`,
`backend/tests/integration/test_identity.py`.

**AUTH-010 · Backend/Commerce · `FIXED`** — a weak password on guest claim is refused with `422`
and the machine-readable reason `password.weak`, as on registration, reset and change. It
previously produced `500`: the route's own schema admitted shorter passwords than the policy,
the domain rejected them, and nothing caught the resulting error.
*Regression protection:* `backend/tests/integration/test_guest_funnel.py`.

**AUTH-011 · Backend/Logging · `FIXED`** — a reset token no longer reaches the HTTP access log.
Checking a link is a `GET` whose query carries the token, and the access log records the full
request line, so the token was written in clear text — an account key, live until first use, in
a file that routinely outlives it and is routinely shipped elsewhere. The redaction filter for
exactly this existed and its pattern already covered `token=`, but it was attached only to the
handlers of the **root** logger, while `uvicorn.access` has its own handler and
`propagate = False`; its records never reached the filter. The filter is now installed on every
logger and every handler. Found while trying to prove the claim that no raw token exists in any
log, rather than by a test — no test described this configuration.
*Regression protection:* `backend/tests/test_logging_redaction.py`.

### 9.4 Verification

| Check | Command | Result |
|---|---|---|
| Frontend type-check | `npx tsc --noEmit` | clean |
| Frontend build | `npm run build` | compiled; `/forgot` and `/reset` static |
| Frontend tests | `npx vitest run` | 39 files, **756 passed**, **0 skipped**, 0 failed |
| Ruff | `ruff check app tests scripts` | all checks passed |
| mypy | `mypy --strict …` | no issues in 136 source files |
| Backend suite (with database) | `pytest -q` | 3415 collected, **3412 passed**, 3 skipped, 0 failed, 962.57 s |
| Six-locale check | `/forgot`, `/reset`, `/login` in en, uk, de, es, fr, ru | every string native |
| End-to-end recovery | live stack: queue → worker → captured letter → link | full flow |
| Product baseline integrity | recomputed twice, independently | 947 files, digest verified twice |

**The frontend run has no skips left.** The 23 tests that earlier runs reported as skipped are
gated by `describe.skipIf(!BUILT)`, where `BUILT` is the presence of `.next/BUILD_ID`, and the
gate is evaluated when the file is collected. Running the type check, then the production
build, then the suite lets them execute: they start a real `next start` on `127.0.0.1:3477` and
assert the four security headers, each exactly once, plus the absence of `X-Powered-By`, across
nine routes. The gate itself was not touched and no assertion was weakened. One change was
needed inside the gated block: waiting for the server to answer had been written inside the
first test, where vitest's five-second default applied, although the helper itself budgets
sixty seconds for that wait. The wait now happens in `beforeAll` with its own timeout, so the
cost of starting another process is no longer charged to the first assertion.

### 9.5 Not exercised

**Real SMTP delivery was not exercised, and production configuration is still required.** Every
run in this task used the local capture transport. No real credentials were used, no real
message was sent, and nothing here says anything about deliverability: SPF, DKIM and DMARC
alignment, and whether a provider files the letter as spam, can only be measured against a real
relay. The owner must supply `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT`, `MAIL_SMTP_USERNAME`,
`MAIL_SMTP_PASSWORD` and a `MAIL_SENDER` on an aligned domain, and set `PUBLIC_APP_URL` to the
real `https` origin. `MAIL_REPLY_TO` is optional.

Two further limits are worth stating plainly. The bounded retry is verified by the recorded
pause between attempts rather than by a real slow server, and the classification of temporary
against permanent failures is verified against synthesized `smtplib` exceptions rather than a
real relay refusing mail. No email-settings page was added to the admin panel.

**One exposure is inherent and remains.** AUTH-011 removed the token from the server's own
logs, but a link in an email has to carry the token in its address, so `/reset?token=…` still
enters the recipient's browser history and is still the page's own URL. That is a property of
emailing a link rather than a defect in this implementation; the token is single-use and
short-lived, which is what bounds it. Removing the address exposure as well would mean the
reset page exchanging the token for a short-lived cookie on load and rewriting its own URL, and
that was not done here.


## 10. First administrator of a new installation

`CRAWLDY-COMPLETE-PRODUCT-HANDOFF-01` found, while proving that a clean database could be
created from source alone, that a correctly deployed installation could not be administered at
all.

### 10.1 What was missing

`users.platform_role` was read in three places and written in none. No endpoint, no script, no
migration and no documented procedure set it; migration `0026` leaves it `NULL` for everyone,
which is the right default. The two staff rows in the owner's own database were created by hand
in SQL, and that fact was recorded nowhere.

For a single machine this was invisible. For a handoff it is a blocker: every admin route
requires a platform role, and the admin cabinet is the only supported place to create plans,
offers and prices. A recipient could migrate, start every service, register — and still have no
way to open `/admin`.

### 10.2 What was added

`backend/scripts/grant_platform_role.py` raises the platform role of a person **who has already
registered through the product**.

```
python scripts/grant_platform_role.py --email you@example.com --role admin
python scripts/grant_platform_role.py --email you@example.com --show
python scripts/grant_platform_role.py --email you@example.com --revoke
```

Three things it deliberately does not do, and the reason for each.

**It does not create a user or set a password.** The person registers with the ordinary form and
chooses their own password; the script only raises the role. A script that creates a default
administrator with a known password is not a convenience — it is a back door that survives
deployment and lands in every backup.

**It has no HTTP route.** Promotion to staff over HTTP would be an attack surface needed exactly
once in the life of an installation. Whoever can run the script already has the database, so it
opens nothing that was closed.

**It does not invent an address.** An unknown address is refused with an explanation, not
silently created — otherwise the installation would carry an account whose password nobody
knows.

Running it twice changes nothing and says so. `admin` covers `staff`; an empty role is an
ordinary customer and remains the default for everyone.

### 10.3 Verification

Proven end to end against a disposable, empty PostgreSQL created for the purpose — `--rm`, a
`tmpfs` data directory, no named volume, its own port and a password generated in memory. The
owner's `seoagent_pgdata` volume was never named or mounted.

| Step | Result |
|---|---|
| `alembic upgrade head` from an empty database | reaches `0054`, creates 42 tables |
| Rows created by the migrations themselves | 4 plans with entitlements, 1 system organization |
| Rows containing personal or commercial data | none: users, audits, pages, issues, purchases, sessions, resets, billing customers and offers are all empty |
| API and worker start against it | both start; 6 worker functions registered |
| `/health` and `/health/ready` | `200` and `200` |
| `/v1/plans`, `/v1/offers` | `200` with empty lists — no error on a fresh database |
| Unknown address passed to the script | refused, exit `1`, no user created |
| Register → `GET /v1/admin/commerce/offers` | `403` |
| Grant `admin` → same session, same request | `200` |

**AUTH-012 · Backend/Identity · `FIXED`** — a new installation can be administered. The platform
role of an already-registered person can be raised from the command line; nothing creates a
credential, and no route assigns a platform role.
*Regression protection:* `backend/tests/integration/test_platform_bootstrap.py`.

### 10.4 What is deliberately not seeded

The commercial rows in the owner's database — the `single` and `pack` offers, the `monthly`
plan, its price, and the AI Presence policy — are **not** part of the product and were not
exported. Every one of them carries identifiers from the owner's own payment-provider account
and amounts that are the owner's commercial decision. A new installation creates its own in the
admin cabinet, and publishes its own provider prices through the path the cabinet already uses.

The plan *definitions* — the four entitlement sets — are product configuration and are created
by the migrations, so they need no seed and no export.



## 11. Privacy cleanup of the calibration corpus

`CRAWLDY-COMPLETE-PRODUCT-HANDOFF-02` made the repository itself privacy-clean. The previous
package had achieved the same result by transforming files while packaging, which meant the
archive and the product no longer described the same thing. Everything below is now true of the
canonical source, and packaging copies it byte for byte.

### 11.1 The dataset that had to go

`backend/benchmark/snapshots/https-myfriendlythai-ca.json` held **54,488 unique real consumer
email addresses** across 5,654 domains, in 346,754 occurrences — crawled from the spam comments
of a compromised restaurant site, the same site §3 records for `perf.page_weight`. Heavy
European representation made it a data-protection liability rather than a curiosity.

It is deleted, and the archive that carried a **byte-identical** second copy,
`snapshots-auditlens-set.tar.gz`, was repacked without it. Excluding only the loose file would
have left the data in the package — that is exactly the mistake the first attempt made.

The site was also removed from `scripts/samples/calibration.txt` and `benchmark/corpus.py`. That
matters more than the deletion: without it the next ordinary `calibrate.py` run would crawl the
site again and import every address a second time. Prose that describes the site as a documented
case is left alone; a sentence about a broken site is not personal data.

**The A/B corpus now contains one site fewer: 56 snapshots became 55, and 55 scored rows became
54.**

### 11.2 What replaced the remaining addresses

About 125 further addresses remained across the corpus — contact details published on the public
pages the engine audited. They are replaced by deterministic synthetics under the reserved
`.invalid` domain:

```
info@company.example      →  info@d3f2a1c4.invalid
someone@company.example   →  user9b71e5d0@d3f2a1c4.invalid
```

Three properties, each load-bearing. **Deterministic**, so one address that appeared on four
pages still appears on those same four pages as the same synthetic — evidence about repetition
survives. **Structure-preserving**, so a role mailbox stays a role mailbox and the
contact-discovery checks still read what they read before. **One-way**, because the mapping is a
hash and nothing writes it down: there is no reverse table to leak, since none is built.

Captured third-party **cookie values** were replaced while their names and attributes were kept
(`SESSID=REDACTED; Path=/; HttpOnly`), and captured **browser API keys** were replaced with
markers that keep the recognisable prefix. Neither belonged to Crawldy; both were recorded by the
crawler from other companies' responses.

In total: **1,401 address occurrences (112 unique), 283 cookie values and 193 keys**, across 71
files, with every modified JSON re-parsed.

### 11.3 Paths and the crawler's contact

Machine-specific paths were replaced in nine files — three benchmark logs, a sweep packet, a
script default, a build-config comment and two documents — with `<PROJECT_ROOT>`, `<HOME>` and
`<WORK_DIR>`. Historical statements keep their meaning; the owner's username and drive layout do
not ship.

The first version of that rule matched `E:` case-insensitively and unanchored, so it found
`language:\n`, `site:\n` and `huggingface:/root` and reported seventeen English sentences as
paths. Replacing there would have corrupted third-party page text while claiming to protect
privacy. The rule now requires an uppercase drive letter not preceded by a word character.

The owner's personal address is gone from the two corpus-harvesting scripts. Wikidata and Tranco
both ask whoever pulls from them in bulk to identify themselves, so the contact is now a setting:

```
CRAWLER_CONTACT=          # backend/.env.example
```

Empty by default, and no address anywhere in the code. A script that needs it and does not have
it **refuses to run** rather than substituting a plausible-looking address — a fake contact is
worse than none, because the free service being asked for help writes to nobody. This is separate
from the engine's own `USER_AGENT`, which deliberately carries no contact at all (§3) and is
unchanged.

### 11.4 The gate

`backend/tests/test_benchmark_privacy.py` scans the corpus, nested archives included, and fails
on any of six classes: the removed snapshot, a real third-party address, an unredacted cookie
value, an unredacted third-party key, the owner's address, or a machine-specific path. It is
scoped to the corpus, so the company's own legal and contact pages — which carry addresses
legitimately — are untouched.

Cleaning once was never enough: the next `calibrate.py` run writes fresh third-party evidence
into the corpus, and whatever those pages contain comes with it.

**Every class was mutation-tested.** Each was reintroduced into a real corpus file, the matching
test was required to fail, and the file was restored and verified by hash:

| Reintroduced | Result |
|---|---|
| the removed snapshot | caught |
| a real third-party address | caught |
| an unredacted cookie value | caught |
| an unredacted third-party key | caught |
| the owner's address | caught |
| a machine-specific path | caught |

The guard assembles the owner's address from fragments rather than writing it out, so the
repository-wide check has no file that is exempt from itself.

### 11.5 Effect on the engine, measured

`rescore_dir.py` over the same corpus, before and after:

| | Before | After |
|---|---|---|
| Snapshots | 56 | 55 |
| Scored rows | 55 | 54 |
| Top tier | n=17, median 70 | n=17, median 70 |
| Middle tier | n=8, median 72.5 | n=8, median 72.5 |
| Bottom tier | n=18, median 61.5 | n=17, median 62 |
| Top–bottom gap | −7 | −7 |
| Inversions | 18 | 18 |

**Exactly one score moved: `smartkp.com.ua`, 57 → 58.** Fifty-three sites were unchanged.

The cause is precise and follows directly from the approved sanitization. `tech.demo_content`
counts independent signals, and one of them was an address whose *content* carried two of them at
once — a theme-vendor name in the local part and a placeholder domain. Replacing the address
removes that signal, the finding drops one severity band, and the site gains a point. The
detector was not touched: **`detector_version` remains `3b9a556ab798`, with 14 accepted detector
rules, 5 scoring rules, crawler version 4 and 80 registered checks.**

No stored expectation needed changing. No test asserts a count over the snapshots, and no
assertion anywhere reads the content of an address, a cookie or a key.

### 11.6 Verification

| Check | Result |
|---|---|
| Benchmark-consuming modules (13) | **370 passed** |
| Privacy gate | 10 passed; six mutations all caught |
| Backend suite | 3436 collected, **3433 passed**, 3 skipped, 0 failed, 568.77 s |
| Ruff | all checks passed |
| mypy `--strict` | no issues in 136 source files |
| Frontend type-check | clean |
| Frontend build | compiled |
| Frontend suite (post-build) | 39 files, **756 passed**, 0 skipped |

