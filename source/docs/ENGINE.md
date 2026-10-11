# Engine

`backend/app/audit/` is the audit core. It takes a URL and returns an `AuditOutcome`. It
imports neither FastAPI nor SQLAlchemy, which is why every check is testable without a
database and without the network.

## Pipeline

```
resolve → site_context → crawl → extract → checks → score → persist
```

| Stage | Module | Responsibility |
|---|---|---|
| resolve | `fetcher.py` | HTTP with SSRF protection and limits |
| site context | `site_context.py` | `robots.txt`, `sitemap.xml`, `llms.txt` |
| crawl | `crawler.py`, `frontier.py` | breadth-first within the origin, in waves — rendering can reveal new URLs |
| extract | `extractor.py` | HTML to `PageSignals` |
| render | `render/` | optional JavaScript rendering, SSR delta, third-party impact |
| checks | `checks/` | the rule registry |
| score | `scoring.py` | findings to 0–100, bands, unclamped score for prioritisation |
| report | `../report/` | `ReportSource` → `ReportDocument` → JSON or `.docx` |

`snapshot.py` stores everything needed to re-score an audit later without crawling again.
`to_json()` is a compact report projection and cannot be loaded back — the two are different.

## Modules

Six, declared in `backend/app/audit/enums.py`:

| Module | Checks | Question it answers |
|---|---|---|
| `seo` | 32 | Can search engines reach, index and understand the pages? |
| `tech` | 14 | Security headers, analytics, form protection, 404s, redirects. |
| `ai_ready` | 12 | Is the page structured so AI systems can use it? |
| `performance` | 11 | Core Web Vitals and loading behaviour. |
| `llm_visibility` | 9 | Is the site suitable to be cited by an assistant? |
| `accessibility` | 2 | What blocks use, separated from what merely hinders it. |
| **Total** | **80** | |

Counts are the registered `@register` classes in `backend/app/audit/checks/`.

**Suitability is not presence.** `llm_visibility` measures whether a site is fit to be cited.
Whether assistants actually cite it is measured separately by `backend/app/presence/`, by
asking them. The engine never infers one from the other.

## Rule registry

A check declares itself and is picked up automatically:

```python
@register
class MyCheck(Check):
    code = "seo.my_check"      # unique, dotted; the registry rejects duplicates
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.LOW
    reads_content = True       # does the conclusion require having read the page?
    variants = ("a", "b")      # semantically different problems this check distinguishes
```

- **A check writes no prose.** Strings live in `backend/app/audit/i18n/`; the check yields a key and
  parameters.
- **Three identifiers, not two.** `code` is the detector category, `issue_key` is the specific
  problem (`perf.core_web_vitals:lcp`) and carries the penalty ceiling and recommendation
  grouping, and `msg` is a catalogue string — presentation, never an identifier.
- **An empty result means the check passed.**
- **`reads_content`** decides whether a finding survives when the crawl returned no pages. A
  check that judges what it read must stay silent when it read nothing; a check whose evidence
  is the server response itself stays valid.

## Scoring

```
penalty      = Σ(weight × severity_multiplier)      , two ceilings per issue_key
module_score = 100 × half_scale / (half_scale + penalty)
overall      = Σ(module_score × MODULE_WEIGHT[module])
```

The scale is hyperbolic, not linear, and never reaches zero — so a repeat audit can always
show progress. Module weights live only in `backend/app/audit/scoring.py`; the public
methodology page uses a snapshot of them that a test compares against the implementation.
Do not copy the numbers into prose: a number stored twice drifts.

Two ceilings apply per `issue_key`: one relative to the finding itself, one as a share of the
module half-scale. The ceiling is taken from the **worst** finding in the group, so a milder
finding can never reduce a penalty.

### Exclusions and coverage

A module has three states, not two:

| State | When | In the score | In the report |
|---|---|---|---|
| full | all signals collected | yes | normal |
| `partial` | some signals missing, but something was measured | yes | a caveat in `missing_data` |
| `skipped` | disabled, or no data at all | **no** | `null` |

A missing module is excluded from `overall`, never counted as zero. Content modules are
excluded when the crawl was blind, and that exclusion is applied **before** any user module
filter, so blindness does not depend on which modules were requested.

## Route applicability

- `kind_of` decides what to fetch first; `type_of` decides what a page **is**. Rules depend on
  the second: `noindex` on a login page is appropriate, on a commercial page it is serious.
- Path words are split on `/` and on hyphens, then matched — substring matching on a URL lies
  the same way it lies in HTML.
- A sitemap is sampled evenly across its whole length, never from the start, and service pages
  get reserved slots.

## Localization

Message catalogues live in `backend/app/audit/i18n/`. Vocabulary that rules match against lives in
`backend/app/audit/vocab/`, keyed by concept and language, so a rule's verdict does not depend on which
language a page happens to be written in. That separation is the fix recorded as engine
correction 2 — see [VERIFICATION.md](VERIFICATION.md).

## Paths that depend on something external

| Path | Depends on | Behaviour when unavailable |
|---|---|---|
| `performance` | PSI or Lighthouse | module excluded; with `--no-perf` it is not requested at all |
| `accessibility` | the **same** Lighthouse call as performance | does not execute when that call is not made |
| rendering | Playwright | the null renderer is used; SSR delta is not computed |
| `backend/app/audit/llm/` | an AI provider, **before** scoring — it can create a finding | `LEGACY`, disabled |
| `backend/app/enrich/` | an AI provider, **after** deterministic truth | disabled by default; has no path back into findings or scores |

`backend/app/audit/llm/` and `backend/app/enrich/` are deliberately separate code with nothing shared, so a new
gateway cannot accidentally reactivate the older path.

## Inputs, outputs, configuration

**Input** — a URL, plus options: page and depth budget, module filter, language, renderer,
performance provider, model.

**Output** — `AuditOutcome`; then a report as JSON or Word. Four documents exist, not two:
audit and presence are separate products, each in a general view (no jargon) and a technical
view (with evidence). Both views of one subject are assembled by one code path so two
documents about the same run cannot disagree.

**Engine identity** — three fingerprints travel with every result:

| Constant | Current | Meaning |
|---|---|---|
| `CRAWLER_VERSION` | `4` | how pages were gathered |
| `DETECTOR_RULES` | `14` | what the rules decide |
| `SCORING_RULES` | `5` | how findings become a number |

`detector_version()` hashes check **declarations**, not rule bodies, so a changed condition
does not move it — that is exactly why the manual `DETECTOR_RULES` counter exists beside it.
Scores either side of a change in these values are not comparable, and `history.compare` says
so rather than presenting a difference as progress.

## Tests and verification

- `backend/tests/` — unit tests per check plus integration tests. Integration tests require
  PostgreSQL and are **skipped** without it; a run reporting hundreds of skips is not a
  complete run.
- Every new check needs a test that fires, a test that stays silent on a clean page, and an
  i18n test that touches every new catalogue key.
- Calibration compares **the same snapshots** before and after a rule change
  (`rescore_dir.py`). Two live runs are not comparable: the spread between them is larger than
  most changes being evaluated.

## Standards that change

`backend/app/audit/standards/` holds vendored reference data — AI crawler lists, language and script
codes — each with its source and the date it was checked. A hand-picked subset is a bug
waiting to happen: a valid value the list omits becomes a false finding against correct markup.
`registry_problems()` fails loudly on silent truncation.
