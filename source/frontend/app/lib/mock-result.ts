/**
 * Еталонні результати аудиту — справжні, а не вигадані.
 *
 * Зібрані зі збережених знімків двох реальних сайтів
 * (`tests/fixtures/snapshots/`) тим самим шляхом, яким їх збирає продукт:
 * знімок → перерахунок → `build_report` → `to_web`. Тобто це буквально
 * те, що віддасть `GET /v1/audits/{id}/result`, включно з довжиною
 * речень, формою доказів і порядком пріоритетів.
 *
 * Це не педантизм. Екран, намальований під вигадані знахідки, вперше
 * зустрічається зі справжнім текстом уже в клієнта: заголовок на два
 * рядки, доказ із вісьмома полями, пріоритет із нульовою кількістю
 * сторінок, бо проблема стосується сайту цілком. Вигаданий макет усього
 * цього не має — і саме тому виглядає бездоганно.
 *
 * Два набори навмисно: сайт, який ми прочитали, і сайт, який віддав нам
 * 403. У другого немає загального бала, три напрями виключені зі скора,
 * приріст у балах не рахується ні для чого, і головне на екрані —
 * пояснення, чого ми не бачили.
 *
 * Файл згенерований: `scratchpad/gen_mock_result.py`. Правити руками не
 * треба — правити треба джерело.
 *
 * Блок `accessibility` доданий окремим механічним проходом: це живий
 * вимір PSI для тих самих адрес. Єдина вада pillowpa.org —
 * `heading-order`, тобто рівно те, що фільтр дублів раніше ховав: до
 * цієї зміни екран не показував про доступність нічого взагалі.
 */

import type { AuditResult, Locale } from "./contracts";

const SCORED_EN: AuditResult = {
    "contract_version": 2,
    "audit_id": "9c2e1b40-0000-4000-8000-00000000a001",
    "site_id": "5b1f0a3e-0000-4000-8000-000000000001",
    "url": "https://pillowpa.org/",
    "origin": "https://pillowpa.org",
    "status": "completed",
    "generated_at": "2026-08-23T16:20:38.973825Z",
    "finished_at": "2026-08-21T09:14:00Z",
    "overall_score": 75,
    "overall_band": "medium",
    "potential_score": 93,
    "modules": [
      {
        "module": "performance",
        "score": 56,
        "band": "poor",
        "weight": 0.22,
        "issues_count": 2,
        "excluded": false,
        "partial": false
      },
      {
        "module": "seo",
        "score": 62,
        "band": "medium",
        "weight": 0.22,
        "issues_count": 12,
        "excluded": false,
        "partial": false
      },
      {
        "module": "ai_ready",
        "score": 81,
        "band": "good",
        "weight": 0.18,
        "issues_count": 5,
        "excluded": false,
        "partial": false
      },
      {
        "module": "llm_visibility",
        "score": 100,
        "band": "good",
        "weight": 0.18,
        "issues_count": 0,
        "excluded": false,
        "partial": false
      },
      {
        "module": "tech",
        "score": 62,
        "band": "medium",
        "weight": 0.1,
        "issues_count": 2,
        "excluded": false,
        "partial": false
      }
    ],
    "summary": {
      "issues_total": 21,
      "by_severity": {
        "critical": 1,
        "high": 1,
        "medium": 5,
        "low": 14,
        "info": 0
      },
      "by_module": {
        "performance": 2,
        "seo": 12,
        "ai_ready": 5,
        "llm_visibility": 0,
        "tech": 2,
        "accessibility": 0
      },
      "coverage": {
        "state": "scored",
        "state_reasons": [],
        "pages_read": 4,
        "pages_fetched": 4,
        "pages_failed": 0,
        "urls_known": 4
      },
      "impact_is_independent": true
    },
    "priorities": [
      {
        "rank": 1,
        "issue_key": "tech.analytics:missing",
        "module": "tech",
        "severity": "high",
        "title": "The site has no analytics",
        "problem": "We opened the page in a real browser and ran all of its JavaScript. No counter appeared — no Google Analytics or GTM, no Plausible, Matomo, Segment or PostHog, and no first-party measurement script either.",
        "action": "Install Google Analytics 4 and verify the site in Search Console. Both are free and take about an hour to set up.",
        "consequence": "You do not know how many people arrive, where from, or where they drop off. Every change to the site is a guess, with no way to tell whether it helped.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "found": [],
          "checked_after_render": true
        },
        "impact_points": 2,
        "impact_by_module": {
          "tech": 25
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 2,
        "issue_key": "perf.core_web_vitals:lcp",
        "module": "performance",
        "severity": "critical",
        "title": "LCP = 4.1 s (mobile)",
        "problem": "Largest Contentful Paint — time to render the main element. The «good» threshold is 2500 s.",
        "action": "Optimise the hero image (preload, modern format) and remove render-blocking CSS/JS.",
        "consequence": "The main image or headline appears too late, and some visitors leave before it does.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "metric": "LCP",
          "value": 4126.042,
          "threshold_good": 2500,
          "rating": "poor",
          "strategy": "mobile",
          "source": "lab",
          "provider": "psi",
          "page_importance": 1.0
        },
        "impact_points": 7,
        "impact_by_module": {
          "performance": 32
        },
        "effort": "high",
        "confidence": "medium"
      },
      {
        "rank": 3,
        "issue_key": "ai.entity.sameas",
        "module": "ai_ready",
        "severity": "medium",
        "title": "No sameAs (entity signals)",
        "problem": "sameAs links your brand to external knowledge bases (Wikidata, LinkedIn, GitHub, Crunchbase) — the primary identity signal.",
        "action": "Add sameAs with links to the brand's official profiles.",
        "consequence": "There is no confirmation that this is the same brand as on Wikipedia or LinkedIn, so models are less confident about your data.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "found": null,
          "types": [
            "BreadcrumbList",
            "WebPage",
            "WebSite"
          ],
          "expected_property": "sameAs",
          "page_importance": 1.0
        },
        "impact_points": 2,
        "impact_by_module": {
          "ai_ready": 10
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 4,
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Missing meta description",
        "problem": "Without one, search assembles a snippet from a random chunk of text.",
        "action": "Add a description that fits the visible ~160 characters.",
        "consequence": "The snippet under your search result gets assembled from a random chunk of text — a wasted chance to explain what you offer.",
        "scope": "page",
        "affected_pages": 3,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/",
          "https://pillowpa.org/boro/"
        ],
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "Home - Pillow, PA",
          "og_description": "Welcome to Our Website!!! Thank you for visiting our website. Pillow is a small historic town of about 300 residents and 30 acres of land surrounded by the Mahantango Creek and the Mahantango Mountains. The town was founded in 1818 by John Snyder, and named Scheidershtettle. It was later incorporated as Uniontown and locally know […]",
          "page_importance": 1.0,
          "occurrences": 3
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 8
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 5,
        "issue_key": "perf.third_party",
        "module": "performance",
        "severity": "medium",
        "title": "Third-party code is 72% of the page (327 KB)",
        "problem": "We opened the page in a real browser and weighed everything it loaded. 72% of the total comes from other people's domains — widgets, chats, trackers, ads. Every one of them has to arrive before the page is fully usable.",
        "action": "Work through the heaviest domains listed in the evidence. Load anything not needed above the fold afterwards, and drop what nobody uses.",
        "consequence": "Your site's speed depends on other companies' servers. If they are having a slow day, so are your visitors — and there is nothing you can do about it.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "third_party_kb": 327,
          "total_kb": 455,
          "share": 0.72,
          "heaviest": [
            {
              "host": "i0.wp.com",
              "kb": 326
            },
            {
              "host": "stats.wp.com",
              "kb": 1
            },
            {
              "host": "pixel.wp.com",
              "kb": 0
            }
          ],
          "measured": true,
          "page_importance": 1.0
        },
        "impact_points": 1,
        "impact_by_module": {
          "performance": 4
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 6,
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Multiple H1 headings (2)",
        "problem": "",
        "action": "Keep one H1 and demote the rest to H2.",
        "consequence": "Several equally weighted headings blur the topic: it is unclear what the page is actually about.",
        "scope": "page",
        "affected_pages": 3,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/",
          "https://pillowpa.org/boro/"
        ],
        "evidence": {
          "h1": [
            "Pillow, PA",
            "Home"
          ],
          "page_importance": 1.0,
          "occurrences": 3
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 6
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 7,
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "No og:image",
        "problem": "",
        "action": "Add a 1200×630 image in the og:image meta tag.",
        "consequence": "Links to your site in messengers and social networks show as an empty rectangle, so fewer people click them.",
        "scope": "page",
        "affected_pages": 3,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/contact-us/",
          "https://pillowpa.org/boro/"
        ],
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 1.0,
          "occurrences": 3
        },
        "impact_points": 1,
        "impact_by_module": {
          "ai_ready": 5
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 8,
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "low",
        "title": "4 security headers are missing",
        "problem": "Not configured: content-security-policy, x-frame-options, x-content-type-options, referrer-policy.",
        "action": "Add the missing headers in your server or CDN configuration.",
        "consequence": "Some of the standard browser-side protections are not switched on. This does not mean the site is compromised or about to be: these headers remove a few specific classes of risk and cost nothing to configure.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy"
          ],
          "present": [
            "permissions-policy"
          ],
          "page_importance": 1.0
        },
        "impact_points": 0,
        "impact_by_module": {
          "tech": 7
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 9,
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "No HSTS header",
        "problem": "",
        "action": "Add `Strict-Transport-Security: max-age=31536000`.",
        "consequence": "The first visit may travel over an unprotected connection — a small but real security gap.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://pillowpa.org"
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 5
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 10,
        "issue_key": "ai.llms_txt:missing",
        "module": "ai_ready",
        "severity": "low",
        "title": "No llms.txt",
        "problem": "llms.txt is a markdown file at the site root that describes the site for language models: what it is, key sections, links to the main pages.",
        "action": "Create /llms.txt: an H1 with the product name, a short description, and `##` sections listing links to key pages.",
        "consequence": "ChatGPT, Perplexity and similar services have no short description of your site and assemble one themselves from whatever they find.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "status_code": 404
        },
        "impact_points": 0,
        "impact_by_module": {
          "ai_ready": 2
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 11,
        "issue_key": "seo.heading_hierarchy",
        "module": "seo",
        "severity": "low",
        "title": "Heading jump H1 → H3",
        "problem": "Skipping a level makes the structure harder to parse machine-side.",
        "action": "Do not skip heading levels.",
        "consequence": "The page structure looks illogical to the software reading it, making the text harder to split into meaningful blocks.",
        "scope": "page",
        "affected_pages": 2,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/"
        ],
        "evidence": {
          "heading": "Search",
          "level": 3,
          "previous": 1,
          "page_importance": 1.0,
          "occurrences": 2
        },
        "impact_points": 0,
        "impact_by_module": {
          "seo": 2
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 12,
        "issue_key": "seo.sitemap:coverage",
        "module": "seo",
        "severity": "low",
        "title": "4 crawled pages are absent from the sitemap",
        "problem": "",
        "action": "Keep sitemap generation in sync with the real site structure.",
        "consequence": "Some pages are missing from the sitemap, so search learns about them later or not at all.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "examples": [
            "https://pillowpa.org/",
            "https://pillowpa.org/about/",
            "https://pillowpa.org/contact-us/",
            "https://pillowpa.org/boro/"
          ],
          "sitemap_urls": 1
        },
        "impact_points": 0,
        "impact_by_module": {
          "seo": 2
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 13,
        "issue_key": "seo.thin_content",
        "module": "seo",
        "severity": "low",
        "title": "Only 129 words on the page",
        "problem": "Little text is a weak signal for both search and LLM citation. It may also mean the content is rendered client-side.",
        "action": "Grow the main copy to 250+ words, or verify SSR.",
        "consequence": "There is too little text for the page to be considered useful: it ranks weakly and there is almost nothing to quote.",
        "scope": "page",
        "affected_pages": 2,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/"
        ],
        "evidence": {
          "word_count": 129,
          "page_importance": 1.0,
          "occurrences": 2
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 4
        },
        "effort": "high",
        "confidence": "high"
      }
    ],
    "next_actions": [
      {
        "rank": 1,
        "issue_key": "tech.analytics:missing",
        "module": "tech",
        "action": "Install Google Analytics 4 and verify the site in Search Console. Both are free and take about an hour to set up.",
        "why": "You do not know how many people arrive, where from, or where they drop off. Every change to the site is a guess, with no way to tell whether it helped.",
        "expected_gain_points": 2,
        "expected_gain": "+2",
        "effort": "low",
        "affected_pages": 0
      },
      {
        "rank": 2,
        "issue_key": "perf.core_web_vitals:lcp",
        "module": "performance",
        "action": "Optimise the hero image (preload, modern format) and remove render-blocking CSS/JS.",
        "why": "The main image or headline appears too late, and some visitors leave before it does.",
        "expected_gain_points": 7,
        "expected_gain": "+7",
        "effort": "high",
        "affected_pages": 1
      },
      {
        "rank": 3,
        "issue_key": "ai.entity.sameas",
        "module": "ai_ready",
        "action": "Add sameAs with links to the brand's official profiles.",
        "why": "There is no confirmation that this is the same brand as on Wikipedia or LinkedIn, so models are less confident about your data.",
        "expected_gain_points": 2,
        "expected_gain": "+2",
        "effort": "low",
        "affected_pages": 1
      },
      {
        "rank": 4,
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "action": "Add a description that fits the visible ~160 characters.",
        "why": "The snippet under your search result gets assembled from a random chunk of text — a wasted chance to explain what you offer.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "medium",
        "affected_pages": 3
      },
      {
        "rank": 5,
        "issue_key": "perf.third_party",
        "module": "performance",
        "action": "Work through the heaviest domains listed in the evidence. Load anything not needed above the fold afterwards, and drop what nobody uses.",
        "why": "Your site's speed depends on other companies' servers. If they are having a slow day, so are your visitors — and there is nothing you can do about it.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "medium",
        "affected_pages": 1
      },
      {
        "rank": 6,
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "action": "Keep one H1 and demote the rest to H2.",
        "why": "Several equally weighted headings blur the topic: it is unclear what the page is actually about.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "low",
        "affected_pages": 3
      },
      {
        "rank": 7,
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "action": "Add a 1200×630 image in the og:image meta tag.",
        "why": "Links to your site in messengers and social networks show as an empty rectangle, so fewer people click them.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "low",
        "affected_pages": 3
      }
    ],
    "findings": [
      {
        "id": null,
        "code": "perf.core_web_vitals",
        "issue_key": "perf.core_web_vitals:lcp",
        "module": "performance",
        "severity": "critical",
        "title": "LCP = 4.1 s (mobile)",
        "description": "Largest Contentful Paint — time to render the main element. The «good» threshold is 2500 s.",
        "recommendation": "Optimise the hero image (preload, modern format) and remove render-blocking CSS/JS.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "metric": "LCP",
          "value": 4126.042,
          "threshold_good": 2500,
          "rating": "poor",
          "strategy": "mobile",
          "source": "lab",
          "provider": "psi",
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "tech.analytics",
        "issue_key": "tech.analytics:missing",
        "module": "tech",
        "severity": "high",
        "title": "The site has no analytics",
        "description": "We opened the page in a real browser and ran all of its JavaScript. No counter appeared — no Google Analytics or GTM, no Plausible, Matomo, Segment or PostHog, and no first-party measurement script either.",
        "recommendation": "Install Google Analytics 4 and verify the site in Search Console. Both are free and take about an hour to set up.",
        "page_url": null,
        "evidence": {
          "found": [],
          "checked_after_render": true
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.entity.sameas",
        "issue_key": "ai.entity.sameas",
        "module": "ai_ready",
        "severity": "medium",
        "title": "No sameAs (entity signals)",
        "description": "sameAs links your brand to external knowledge bases (Wikidata, LinkedIn, GitHub, Crunchbase) — the primary identity signal.",
        "recommendation": "Add sameAs with links to the brand's official profiles.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "found": null,
          "types": [
            "BreadcrumbList",
            "WebPage",
            "WebSite"
          ],
          "expected_property": "sameAs",
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.third_party",
        "issue_key": "perf.third_party",
        "module": "performance",
        "severity": "medium",
        "title": "Third-party code is 72% of the page (327 KB)",
        "description": "We opened the page in a real browser and weighed everything it loaded. 72% of the total comes from other people's domains — widgets, chats, trackers, ads. Every one of them has to arrive before the page is fully usable.",
        "recommendation": "Work through the heaviest domains listed in the evidence. Load anything not needed above the fold afterwards, and drop what nobody uses.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "third_party_kb": 327,
          "total_kb": 455,
          "share": 0.72,
          "heaviest": [
            {
              "host": "i0.wp.com",
              "kb": 326
            },
            {
              "host": "stats.wp.com",
              "kb": 1
            },
            {
              "host": "pixel.wp.com",
              "kb": 0
            }
          ],
          "measured": true,
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.meta_description",
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Missing meta description",
        "description": "Without one, search assembles a snippet from a random chunk of text.",
        "recommendation": "Add a description that fits the visible ~160 characters.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "Home - Pillow, PA",
          "og_description": "Welcome to Our Website!!! Thank you for visiting our website. Pillow is a small historic town of about 300 residents and 30 acres of land surrounded by the Mahantango Creek and the Mahantango Mountains. The town was founded in 1818 by John Snyder, and named Scheidershtettle. It was later incorporated as Uniontown and locally know […]",
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.meta_description",
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Missing meta description",
        "description": "Without one, search assembles a snippet from a random chunk of text.",
        "recommendation": "Add a description that fits the visible ~160 characters.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "About - Pillow, PA",
          "og_description": "About PILLOW. Pillow was incorporated as a borough on April 20, 1864, as Uniontown. It is the northernmost town in Dauphin County, Pennsylvania. Prior to the incorporation the original town was called Snydertown (Schneidershtettle) after John Snyder the founder. He was a land developer, and died in Mercer County in 1855. No elections were held […]",
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.meta_description",
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Missing meta description",
        "description": "Without one, search assembles a snippet from a random chunk of text.",
        "recommendation": "Add a description that fits the visible ~160 characters.",
        "page_url": "https://pillowpa.org/boro/",
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "Boro Council - Pillow, PA",
          "og_description": "Borough Council The Pillow Borough Council is the governing body of the town. It is comprised of one mayor and six council members. With the exception of the secretary/treasurer, they are elected positions with four year terms. There are also three auditors who are elected to six year terms. The council holds public meetings […]",
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.llms_txt",
        "issue_key": "ai.llms_txt:missing",
        "module": "ai_ready",
        "severity": "low",
        "title": "No llms.txt",
        "description": "llms.txt is a markdown file at the site root that describes the site for language models: what it is, key sections, links to the main pages.",
        "recommendation": "Create /llms.txt: an H1 with the product name, a short description, and `##` sections listing links to key pages.",
        "page_url": null,
        "evidence": {
          "status_code": 404
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.opengraph",
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "No og:image",
        "description": "",
        "recommendation": "Add a 1200×630 image in the og:image meta tag.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.opengraph",
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "No og:image",
        "description": "",
        "recommendation": "Add a 1200×630 image in the og:image meta tag.",
        "page_url": "https://pillowpa.org/boro/",
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.opengraph",
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "No og:image",
        "description": "",
        "recommendation": "Add a 1200×630 image in the og:image meta tag.",
        "page_url": "https://pillowpa.org/contact-us/",
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.h1",
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Multiple H1 headings (2)",
        "description": "",
        "recommendation": "Keep one H1 and demote the rest to H2.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "h1": [
            "Pillow, PA",
            "Home"
          ],
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.h1",
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Multiple H1 headings (3)",
        "description": "",
        "recommendation": "Keep one H1 and demote the rest to H2.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "h1": [
            "Pillow, PA",
            "About",
            "About PILLOW."
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.h1",
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Multiple H1 headings (2)",
        "description": "",
        "recommendation": "Keep one H1 and demote the rest to H2.",
        "page_url": "https://pillowpa.org/boro/",
        "evidence": {
          "h1": [
            "Pillow, PA",
            "Boro Council"
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.heading_hierarchy",
        "issue_key": "seo.heading_hierarchy",
        "module": "seo",
        "severity": "low",
        "title": "Heading jump H1 → H3",
        "description": "Skipping a level makes the structure harder to parse machine-side.",
        "recommendation": "Do not skip heading levels.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "heading": "Search",
          "level": 3,
          "previous": 1,
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.heading_hierarchy",
        "issue_key": "seo.heading_hierarchy",
        "module": "seo",
        "severity": "low",
        "title": "Heading jump H1 → H3",
        "description": "Skipping a level makes the structure harder to parse machine-side.",
        "recommendation": "Do not skip heading levels.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "heading": "Search",
          "level": 3,
          "previous": 1,
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.https",
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "No HSTS header",
        "description": "",
        "recommendation": "Add `Strict-Transport-Security: max-age=31536000`.",
        "page_url": null,
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://pillowpa.org"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.sitemap",
        "issue_key": "seo.sitemap:coverage",
        "module": "seo",
        "severity": "low",
        "title": "4 crawled pages are absent from the sitemap",
        "description": "",
        "recommendation": "Keep sitemap generation in sync with the real site structure.",
        "page_url": null,
        "evidence": {
          "examples": [
            "https://pillowpa.org/",
            "https://pillowpa.org/about/",
            "https://pillowpa.org/contact-us/",
            "https://pillowpa.org/boro/"
          ],
          "sitemap_urls": 1
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.thin_content",
        "issue_key": "seo.thin_content",
        "module": "seo",
        "severity": "low",
        "title": "Only 129 words on the page",
        "description": "Little text is a weak signal for both search and LLM citation. It may also mean the content is rendered client-side.",
        "recommendation": "Grow the main copy to 250+ words, or verify SSR.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "word_count": 129,
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.thin_content",
        "issue_key": "seo.thin_content",
        "module": "seo",
        "severity": "low",
        "title": "Only 176 words on the page",
        "description": "Little text is a weak signal for both search and LLM citation. It may also mean the content is rendered client-side.",
        "recommendation": "Grow the main copy to 250+ words, or verify SSR.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "word_count": 176,
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "tech.security_headers",
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "low",
        "title": "4 security headers are missing",
        "description": "Not configured: content-security-policy, x-frame-options, x-content-type-options, referrer-policy.",
        "recommendation": "Add the missing headers in your server or CDN configuration.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy"
          ],
          "present": [
            "permissions-policy"
          ],
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      }
    ],
    "missing_data": [],
    "engine_versions": {
      "schema": "1",
      "crawler": "3",
      "detector": "9bed4b4719a4",
      "scoring": "3fdd28054fda",
      "config": "ff5dfefdd052",
      "model": null
    },
    "localization": {
      "locale": "en",
      "fallback_locale": "en",
      "fell_back_strings": 0
    },
    "accessibility": {
      "available": true,
      "measured_url": "https://pillowpa.org/",
      "strategy": "mobile",
      "applicable": 27,
      "passed": 26,
      "failed": 1,
      "findings": [
        {
          "audit_id": "heading-order",
          "title": "Heading elements are not in a sequentially-descending order",
          "impact": "",
          "also_reported_as": "seo.heading_hierarchy",
          "also_reported_module": "seo"
        }
      ],
      "lighthouse_score": 98.0,
      "counts_toward_overall": true,
      "overall_weight": 0.1
    }
  };

const SCORED_UK: AuditResult = {
    "contract_version": 2,
    "audit_id": "9c2e1b40-0000-4000-8000-00000000a001",
    "site_id": "5b1f0a3e-0000-4000-8000-000000000001",
    "url": "https://pillowpa.org/",
    "origin": "https://pillowpa.org",
    "status": "completed",
    "generated_at": "2026-08-23T16:20:38.977521Z",
    "finished_at": "2026-08-21T09:14:00Z",
    "overall_score": 75,
    "overall_band": "medium",
    "potential_score": 93,
    "modules": [
      {
        "module": "performance",
        "score": 56,
        "band": "poor",
        "weight": 0.22,
        "issues_count": 2,
        "excluded": false,
        "partial": false
      },
      {
        "module": "seo",
        "score": 62,
        "band": "medium",
        "weight": 0.22,
        "issues_count": 12,
        "excluded": false,
        "partial": false
      },
      {
        "module": "ai_ready",
        "score": 81,
        "band": "good",
        "weight": 0.18,
        "issues_count": 5,
        "excluded": false,
        "partial": false
      },
      {
        "module": "llm_visibility",
        "score": 100,
        "band": "good",
        "weight": 0.18,
        "issues_count": 0,
        "excluded": false,
        "partial": false
      },
      {
        "module": "tech",
        "score": 62,
        "band": "medium",
        "weight": 0.1,
        "issues_count": 2,
        "excluded": false,
        "partial": false
      }
    ],
    "summary": {
      "issues_total": 21,
      "by_severity": {
        "critical": 1,
        "high": 1,
        "medium": 5,
        "low": 14,
        "info": 0
      },
      "by_module": {
        "performance": 2,
        "seo": 12,
        "ai_ready": 5,
        "llm_visibility": 0,
        "tech": 2,
        "accessibility": 0
      },
      "coverage": {
        "state": "scored",
        "state_reasons": [],
        "pages_read": 4,
        "pages_fetched": 4,
        "pages_failed": 0,
        "urls_known": 4
      },
      "impact_is_independent": true
    },
    "priorities": [
      {
        "rank": 1,
        "issue_key": "tech.analytics:missing",
        "module": "tech",
        "severity": "high",
        "title": "На сайті немає системи аналітики",
        "problem": "Ми відкрили сторінку у справжньому браузері й виконали весь її JavaScript. Жодного лічильника — ні Google Analytics чи GTM, ні Plausible, Matomo, Segment, PostHog, ні власного скрипта вимірювання — не зʼявилося.",
        "action": "Підключіть Google Analytics 4 і підтвердьте сайт у Search Console. Обидва безкоштовні, налаштування — приблизно година.",
        "consequence": "Ви не знаєте, скільки людей приходить на сайт, звідки вони й на чому йдуть. Будь-яка зміна на сайті робиться навмання: перевірити, стало краще чи гірше, нема чим.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "found": [],
          "checked_after_render": true
        },
        "impact_points": 2,
        "impact_by_module": {
          "tech": 25
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 2,
        "issue_key": "perf.core_web_vitals:lcp",
        "module": "performance",
        "severity": "critical",
        "title": "LCP = 4.1 s (mobile)",
        "problem": "Largest Contentful Paint — час до промальовування головного елемента. Поріг «добре» — 2500 s.",
        "action": "Оптимізуйте hero-зображення (preload, сучасний формат), приберіть render-blocking CSS/JS.",
        "consequence": "Головне зображення чи заголовок зʼявляються надто пізно, і частина відвідувачів іде, не дочекавшись.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "metric": "LCP",
          "value": 4126.042,
          "threshold_good": 2500,
          "rating": "poor",
          "strategy": "mobile",
          "source": "lab",
          "provider": "psi",
          "page_importance": 1.0
        },
        "impact_points": 7,
        "impact_by_module": {
          "performance": 32
        },
        "effort": "high",
        "confidence": "medium"
      },
      {
        "rank": 3,
        "issue_key": "ai.entity.sameas",
        "module": "ai_ready",
        "severity": "medium",
        "title": "Немає sameAs (entity signals)",
        "problem": "sameAs зв'язує ваш бренд із зовнішніми базами знань (Wikidata, LinkedIn, GitHub, Crunchbase) — головний сигнал ідентичності.",
        "action": "Додайте sameAs із посиланнями на офіційні профілі бренду.",
        "consequence": "Немає підтвердження, що це той самий бренд, що у Wikipedia чи LinkedIn, — моделі менш упевнені у ваших даних.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "found": null,
          "types": [
            "BreadcrumbList",
            "WebPage",
            "WebSite"
          ],
          "expected_property": "sameAs",
          "page_importance": 1.0
        },
        "impact_points": 2,
        "impact_by_module": {
          "ai_ready": 10
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 4,
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Відсутній meta description",
        "problem": "Без опису пошук складе його сам із випадкового шматка тексту.",
        "action": "Додайте опис, який вміщується у видимі ~160 символів.",
        "consequence": "Опис під посиланням у пошуку складеться автоматично з випадкового шматка тексту — це втрачена нагода пояснити, чим ви корисні.",
        "scope": "page",
        "affected_pages": 3,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/",
          "https://pillowpa.org/boro/"
        ],
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "Home - Pillow, PA",
          "og_description": "Welcome to Our Website!!! Thank you for visiting our website. Pillow is a small historic town of about 300 residents and 30 acres of land surrounded by the Mahantango Creek and the Mahantango Mountains. The town was founded in 1818 by John Snyder, and named Scheidershtettle. It was later incorporated as Uniontown and locally know […]",
          "page_importance": 1.0,
          "occurrences": 3
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 8
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 5,
        "issue_key": "perf.third_party",
        "module": "performance",
        "severity": "medium",
        "title": "Чужий код важить 72% сторінки (327 КБ)",
        "problem": "Ми відкрили сторінку у справжньому браузері й зважили все, що вона завантажила. 72% усієї ваги припадає на файли з чужих доменів — віджети, чати, лічильники, реклама. Кожен із них має завантажитись, перш ніж сторінка стане повністю робочою.",
        "action": "Пройдіться списком найважчих доменів у доказах. Те, що не потрібне на першому екрані, вантажте після нього; від того, чим ніхто не користується, відмовтесь.",
        "consequence": "Швидкість вашого сайту залежить від чужих серверів. Якщо в них сьогодні повільний день — повільний день і у ваших відвідувачів, а вплинути на це ви не можете.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "third_party_kb": 327,
          "total_kb": 455,
          "share": 0.72,
          "heaviest": [
            {
              "host": "i0.wp.com",
              "kb": 326
            },
            {
              "host": "stats.wp.com",
              "kb": 1
            },
            {
              "host": "pixel.wp.com",
              "kb": 0
            }
          ],
          "measured": true,
          "page_importance": 1.0
        },
        "impact_points": 1,
        "impact_by_module": {
          "performance": 4
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 6,
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Кілька H1 (2)",
        "problem": "",
        "action": "Залиште один H1, решту переведіть у H2.",
        "consequence": "Кілька рівнозначних заголовків розмивають тему: незрозуміло, про що сторінка насправді.",
        "scope": "page",
        "affected_pages": 3,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/",
          "https://pillowpa.org/boro/"
        ],
        "evidence": {
          "h1": [
            "Pillow, PA",
            "Home"
          ],
          "page_importance": 1.0,
          "occurrences": 3
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 6
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 7,
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "Немає og:image",
        "problem": "",
        "action": "Додайте зображення 1200×630 у мета-тег og:image.",
        "consequence": "Посилання на сайт у месенджерах і соцмережах виглядатиме порожнім прямокутником, і на нього рідше клікають.",
        "scope": "page",
        "affected_pages": 3,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/contact-us/",
          "https://pillowpa.org/boro/"
        ],
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 1.0,
          "occurrences": 3
        },
        "impact_points": 1,
        "impact_by_module": {
          "ai_ready": 5
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 8,
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "low",
        "title": "Бракує 4 заголовків безпеки",
        "problem": "Не налаштовані: content-security-policy, x-frame-options, x-content-type-options, referrer-policy.",
        "action": "Додайте відсутні заголовки в конфігурації сервера або CDN.",
        "consequence": "Частина стандартних налаштувань браузерного захисту не ввімкнена. Це не означає, що сайт зламано чи от-от зламають: такі заголовки прибирають окремі класи ризику й нічого не коштують у налаштуванні.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://pillowpa.org/"
        ],
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy"
          ],
          "present": [
            "permissions-policy"
          ],
          "page_importance": 1.0
        },
        "impact_points": 0,
        "impact_by_module": {
          "tech": 7
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 9,
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "Немає заголовка HSTS",
        "problem": "",
        "action": "Додайте `Strict-Transport-Security: max-age=31536000`.",
        "consequence": "Перший візит може пройти незахищеним каналом — невелика, але реальна дірка в безпеці.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://pillowpa.org"
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 5
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 10,
        "issue_key": "ai.llms_txt:missing",
        "module": "ai_ready",
        "severity": "low",
        "title": "Немає llms.txt",
        "problem": "llms.txt — це markdown-файл у корені, який у стислій формі описує сайт для мовних моделей: що це, ключові розділи, посилання на основні сторінки.",
        "action": "Створіть /llms.txt: H1 із назвою продукту, короткий опис, розділи `##` зі списками посилань на ключові сторінки.",
        "consequence": "ChatGPT, Perplexity та подібні сервіси не мають готового короткого опису вашого сайту й складають його самі з того, що знайдуть.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "status_code": 404
        },
        "impact_points": 0,
        "impact_by_module": {
          "ai_ready": 2
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 11,
        "issue_key": "seo.heading_hierarchy",
        "module": "seo",
        "severity": "low",
        "title": "Стрибок H1 → H3",
        "problem": "Пропуск рівня ускладнює машинне розуміння структури.",
        "action": "Не пропускайте рівні заголовків.",
        "consequence": "Структура сторінки виглядає нелогічно для програм, які її читають, — текст важче розібрати на змістовні блоки.",
        "scope": "page",
        "affected_pages": 2,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/"
        ],
        "evidence": {
          "heading": "Search",
          "level": 3,
          "previous": 1,
          "page_importance": 1.0,
          "occurrences": 2
        },
        "impact_points": 0,
        "impact_by_module": {
          "seo": 2
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 12,
        "issue_key": "seo.sitemap:coverage",
        "module": "seo",
        "severity": "low",
        "title": "4 знайдених сторінок відсутні в sitemap",
        "problem": "",
        "action": "Синхронізуйте генерацію sitemap із реальною структурою сайту.",
        "consequence": "Частина сторінок не потрапила в карту сайту, тож пошук дізнається про них пізніше або не дізнається взагалі.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "examples": [
            "https://pillowpa.org/",
            "https://pillowpa.org/about/",
            "https://pillowpa.org/contact-us/",
            "https://pillowpa.org/boro/"
          ],
          "sitemap_urls": 1
        },
        "impact_points": 0,
        "impact_by_module": {
          "seo": 2
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 13,
        "issue_key": "seo.thin_content",
        "module": "seo",
        "severity": "low",
        "title": "Лише 129 слів на сторінці",
        "problem": "Малий обсяг тексту — слабкий сигнал і для пошуку, і для цитування LLM. Можливо також, що контент рендериться на клієнті.",
        "action": "Доведіть основний текст до 250+ слів або перевірте SSR.",
        "consequence": "На сторінці замало тексту, щоб її вважали корисною: вона слабко ранжується і її майже нема за що цитувати.",
        "scope": "page",
        "affected_pages": 2,
        "affected_examples": [
          "https://pillowpa.org/",
          "https://pillowpa.org/about/"
        ],
        "evidence": {
          "word_count": 129,
          "page_importance": 1.0,
          "occurrences": 2
        },
        "impact_points": 1,
        "impact_by_module": {
          "seo": 4
        },
        "effort": "high",
        "confidence": "high"
      }
    ],
    "next_actions": [
      {
        "rank": 1,
        "issue_key": "tech.analytics:missing",
        "module": "tech",
        "action": "Підключіть Google Analytics 4 і підтвердьте сайт у Search Console. Обидва безкоштовні, налаштування — приблизно година.",
        "why": "Ви не знаєте, скільки людей приходить на сайт, звідки вони й на чому йдуть. Будь-яка зміна на сайті робиться навмання: перевірити, стало краще чи гірше, нема чим.",
        "expected_gain_points": 2,
        "expected_gain": "+2",
        "effort": "low",
        "affected_pages": 0
      },
      {
        "rank": 2,
        "issue_key": "perf.core_web_vitals:lcp",
        "module": "performance",
        "action": "Оптимізуйте hero-зображення (preload, сучасний формат), приберіть render-blocking CSS/JS.",
        "why": "Головне зображення чи заголовок зʼявляються надто пізно, і частина відвідувачів іде, не дочекавшись.",
        "expected_gain_points": 7,
        "expected_gain": "+7",
        "effort": "high",
        "affected_pages": 1
      },
      {
        "rank": 3,
        "issue_key": "ai.entity.sameas",
        "module": "ai_ready",
        "action": "Додайте sameAs із посиланнями на офіційні профілі бренду.",
        "why": "Немає підтвердження, що це той самий бренд, що у Wikipedia чи LinkedIn, — моделі менш упевнені у ваших даних.",
        "expected_gain_points": 2,
        "expected_gain": "+2",
        "effort": "low",
        "affected_pages": 1
      },
      {
        "rank": 4,
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "action": "Додайте опис, який вміщується у видимі ~160 символів.",
        "why": "Опис під посиланням у пошуку складеться автоматично з випадкового шматка тексту — це втрачена нагода пояснити, чим ви корисні.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "medium",
        "affected_pages": 3
      },
      {
        "rank": 5,
        "issue_key": "perf.third_party",
        "module": "performance",
        "action": "Пройдіться списком найважчих доменів у доказах. Те, що не потрібне на першому екрані, вантажте після нього; від того, чим ніхто не користується, відмовтесь.",
        "why": "Швидкість вашого сайту залежить від чужих серверів. Якщо в них сьогодні повільний день — повільний день і у ваших відвідувачів, а вплинути на це ви не можете.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "medium",
        "affected_pages": 1
      },
      {
        "rank": 6,
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "action": "Залиште один H1, решту переведіть у H2.",
        "why": "Кілька рівнозначних заголовків розмивають тему: незрозуміло, про що сторінка насправді.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "low",
        "affected_pages": 3
      },
      {
        "rank": 7,
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "action": "Додайте зображення 1200×630 у мета-тег og:image.",
        "why": "Посилання на сайт у месенджерах і соцмережах виглядатиме порожнім прямокутником, і на нього рідше клікають.",
        "expected_gain_points": 1,
        "expected_gain": "+1",
        "effort": "low",
        "affected_pages": 3
      }
    ],
    "findings": [
      {
        "id": null,
        "code": "perf.core_web_vitals",
        "issue_key": "perf.core_web_vitals:lcp",
        "module": "performance",
        "severity": "critical",
        "title": "LCP = 4.1 s (mobile)",
        "description": "Largest Contentful Paint — час до промальовування головного елемента. Поріг «добре» — 2500 s.",
        "recommendation": "Оптимізуйте hero-зображення (preload, сучасний формат), приберіть render-blocking CSS/JS.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "metric": "LCP",
          "value": 4126.042,
          "threshold_good": 2500,
          "rating": "poor",
          "strategy": "mobile",
          "source": "lab",
          "provider": "psi",
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "tech.analytics",
        "issue_key": "tech.analytics:missing",
        "module": "tech",
        "severity": "high",
        "title": "На сайті немає системи аналітики",
        "description": "Ми відкрили сторінку у справжньому браузері й виконали весь її JavaScript. Жодного лічильника — ні Google Analytics чи GTM, ні Plausible, Matomo, Segment, PostHog, ні власного скрипта вимірювання — не зʼявилося.",
        "recommendation": "Підключіть Google Analytics 4 і підтвердьте сайт у Search Console. Обидва безкоштовні, налаштування — приблизно година.",
        "page_url": null,
        "evidence": {
          "found": [],
          "checked_after_render": true
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.entity.sameas",
        "issue_key": "ai.entity.sameas",
        "module": "ai_ready",
        "severity": "medium",
        "title": "Немає sameAs (entity signals)",
        "description": "sameAs зв'язує ваш бренд із зовнішніми базами знань (Wikidata, LinkedIn, GitHub, Crunchbase) — головний сигнал ідентичності.",
        "recommendation": "Додайте sameAs із посиланнями на офіційні профілі бренду.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "found": null,
          "types": [
            "BreadcrumbList",
            "WebPage",
            "WebSite"
          ],
          "expected_property": "sameAs",
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.third_party",
        "issue_key": "perf.third_party",
        "module": "performance",
        "severity": "medium",
        "title": "Чужий код важить 72% сторінки (327 КБ)",
        "description": "Ми відкрили сторінку у справжньому браузері й зважили все, що вона завантажила. 72% усієї ваги припадає на файли з чужих доменів — віджети, чати, лічильники, реклама. Кожен із них має завантажитись, перш ніж сторінка стане повністю робочою.",
        "recommendation": "Пройдіться списком найважчих доменів у доказах. Те, що не потрібне на першому екрані, вантажте після нього; від того, чим ніхто не користується, відмовтесь.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "third_party_kb": 327,
          "total_kb": 455,
          "share": 0.72,
          "heaviest": [
            {
              "host": "i0.wp.com",
              "kb": 326
            },
            {
              "host": "stats.wp.com",
              "kb": 1
            },
            {
              "host": "pixel.wp.com",
              "kb": 0
            }
          ],
          "measured": true,
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.meta_description",
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Відсутній meta description",
        "description": "Без опису пошук складе його сам із випадкового шматка тексту.",
        "recommendation": "Додайте опис, який вміщується у видимі ~160 символів.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "Home - Pillow, PA",
          "og_description": "Welcome to Our Website!!! Thank you for visiting our website. Pillow is a small historic town of about 300 residents and 30 acres of land surrounded by the Mahantango Creek and the Mahantango Mountains. The town was founded in 1818 by John Snyder, and named Scheidershtettle. It was later incorporated as Uniontown and locally know […]",
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.meta_description",
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Відсутній meta description",
        "description": "Без опису пошук складе його сам із випадкового шматка тексту.",
        "recommendation": "Додайте опис, який вміщується у видимі ~160 символів.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "About - Pillow, PA",
          "og_description": "About PILLOW. Pillow was incorporated as a borough on April 20, 1864, as Uniontown. It is the northernmost town in Dauphin County, Pennsylvania. Prior to the incorporation the original town was called Snydertown (Schneidershtettle) after John Snyder the founder. He was a land developer, and died in Mercer County in 1855. No elections were held […]",
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.meta_description",
        "issue_key": "seo.meta_description:missing",
        "module": "seo",
        "severity": "medium",
        "title": "Відсутній meta description",
        "description": "Без опису пошук складе його сам із випадкового шматка тексту.",
        "recommendation": "Додайте опис, який вміщується у видимі ~160 символів.",
        "page_url": "https://pillowpa.org/boro/",
        "evidence": {
          "found": null,
          "expected_max_chars": 160,
          "title": "Boro Council - Pillow, PA",
          "og_description": "Borough Council The Pillow Borough Council is the governing body of the town. It is comprised of one mayor and six council members. With the exception of the secretary/treasurer, they are elected positions with four year terms. There are also three auditors who are elected to six year terms. The council holds public meetings […]",
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.llms_txt",
        "issue_key": "ai.llms_txt:missing",
        "module": "ai_ready",
        "severity": "low",
        "title": "Немає llms.txt",
        "description": "llms.txt — це markdown-файл у корені, який у стислій формі описує сайт для мовних моделей: що це, ключові розділи, посилання на основні сторінки.",
        "recommendation": "Створіть /llms.txt: H1 із назвою продукту, короткий опис, розділи `##` зі списками посилань на ключові сторінки.",
        "page_url": null,
        "evidence": {
          "status_code": 404
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.opengraph",
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "Немає og:image",
        "description": "",
        "recommendation": "Додайте зображення 1200×630 у мета-тег og:image.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.opengraph",
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "Немає og:image",
        "description": "",
        "recommendation": "Додайте зображення 1200×630 у мета-тег og:image.",
        "page_url": "https://pillowpa.org/boro/",
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "ai.opengraph",
        "issue_key": "ai.opengraph:image",
        "module": "ai_ready",
        "severity": "low",
        "title": "Немає og:image",
        "description": "",
        "recommendation": "Додайте зображення 1200×630 у мета-тег og:image.",
        "page_url": "https://pillowpa.org/contact-us/",
        "evidence": {
          "opengraph": [
            "og:description",
            "og:locale",
            "og:site_name",
            "og:title",
            "og:type",
            "og:url"
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.h1",
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Кілька H1 (2)",
        "description": "",
        "recommendation": "Залиште один H1, решту переведіть у H2.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "h1": [
            "Pillow, PA",
            "Home"
          ],
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.h1",
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Кілька H1 (3)",
        "description": "",
        "recommendation": "Залиште один H1, решту переведіть у H2.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "h1": [
            "Pillow, PA",
            "About",
            "About PILLOW."
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.h1",
        "issue_key": "seo.h1:multiple",
        "module": "seo",
        "severity": "low",
        "title": "Кілька H1 (2)",
        "description": "",
        "recommendation": "Залиште один H1, решту переведіть у H2.",
        "page_url": "https://pillowpa.org/boro/",
        "evidence": {
          "h1": [
            "Pillow, PA",
            "Boro Council"
          ],
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.heading_hierarchy",
        "issue_key": "seo.heading_hierarchy",
        "module": "seo",
        "severity": "low",
        "title": "Стрибок H1 → H3",
        "description": "Пропуск рівня ускладнює машинне розуміння структури.",
        "recommendation": "Не пропускайте рівні заголовків.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "heading": "Search",
          "level": 3,
          "previous": 1,
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.heading_hierarchy",
        "issue_key": "seo.heading_hierarchy",
        "module": "seo",
        "severity": "low",
        "title": "Стрибок H1 → H3",
        "description": "Пропуск рівня ускладнює машинне розуміння структури.",
        "recommendation": "Не пропускайте рівні заголовків.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "heading": "Search",
          "level": 3,
          "previous": 1,
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.https",
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "Немає заголовка HSTS",
        "description": "",
        "recommendation": "Додайте `Strict-Transport-Security: max-age=31536000`.",
        "page_url": null,
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://pillowpa.org"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.sitemap",
        "issue_key": "seo.sitemap:coverage",
        "module": "seo",
        "severity": "low",
        "title": "4 знайдених сторінок відсутні в sitemap",
        "description": "",
        "recommendation": "Синхронізуйте генерацію sitemap із реальною структурою сайту.",
        "page_url": null,
        "evidence": {
          "examples": [
            "https://pillowpa.org/",
            "https://pillowpa.org/about/",
            "https://pillowpa.org/contact-us/",
            "https://pillowpa.org/boro/"
          ],
          "sitemap_urls": 1
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.thin_content",
        "issue_key": "seo.thin_content",
        "module": "seo",
        "severity": "low",
        "title": "Лише 129 слів на сторінці",
        "description": "Малий обсяг тексту — слабкий сигнал і для пошуку, і для цитування LLM. Можливо також, що контент рендериться на клієнті.",
        "recommendation": "Доведіть основний текст до 250+ слів або перевірте SSR.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "word_count": 129,
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.thin_content",
        "issue_key": "seo.thin_content",
        "module": "seo",
        "severity": "low",
        "title": "Лише 176 слів на сторінці",
        "description": "Малий обсяг тексту — слабкий сигнал і для пошуку, і для цитування LLM. Можливо також, що контент рендериться на клієнті.",
        "recommendation": "Доведіть основний текст до 250+ слів або перевірте SSR.",
        "page_url": "https://pillowpa.org/about/",
        "evidence": {
          "word_count": 176,
          "page_importance": 0.663
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "tech.security_headers",
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "low",
        "title": "Бракує 4 заголовків безпеки",
        "description": "Не налаштовані: content-security-policy, x-frame-options, x-content-type-options, referrer-policy.",
        "recommendation": "Додайте відсутні заголовки в конфігурації сервера або CDN.",
        "page_url": "https://pillowpa.org/",
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy"
          ],
          "present": [
            "permissions-policy"
          ],
          "page_importance": 1.0
        },
        "verdict": null,
        "verdict_note": ""
      }
    ],
    "missing_data": [],
    "engine_versions": {
      "schema": "1",
      "crawler": "3",
      "detector": "9bed4b4719a4",
      "scoring": "3fdd28054fda",
      "config": "ff5dfefdd052",
      "model": null
    },
    "localization": {
      "locale": "uk",
      "fallback_locale": "en",
      "fell_back_strings": 0
    },
    "accessibility": {
      "available": true,
      "measured_url": "https://pillowpa.org/",
      "strategy": "mobile",
      "applicable": 27,
      "passed": 26,
      "failed": 1,
      "findings": [
        {
          "audit_id": "heading-order",
          "title": "Heading elements are not in a sequentially-descending order",
          "impact": "",
          "also_reported_as": "seo.heading_hierarchy",
          "also_reported_module": "seo"
        }
      ],
      "lighthouse_score": 98.0,
      "counts_toward_overall": true,
      "overall_weight": 0.1
    }
  };

const BLOCKED_EN: AuditResult = {
    "contract_version": 2,
    "audit_id": "9c2e1b40-0000-4000-8000-00000000a004",
    "site_id": null,
    "url": "https://www.unilever.com/",
    "origin": "https://www.unilever.com",
    "status": "partial",
    "generated_at": "2026-08-23T16:20:39.640797Z",
    "finished_at": "2026-08-21T09:14:00Z",
    "overall_score": null,
    "overall_band": "unknown",
    "potential_score": null,
    "modules": [
      {
        "module": "performance",
        "score": 65,
        "band": "medium",
        "weight": 0.5238095238095237,
        "issues_count": 3,
        "excluded": false,
        "partial": false
      },
      {
        "module": "seo",
        "score": null,
        "band": "unknown",
        "weight": 0.0,
        "issues_count": 1,
        "excluded": true,
        "partial": false
      },
      {
        "module": "ai_ready",
        "score": null,
        "band": "unknown",
        "weight": 0.0,
        "issues_count": 0,
        "excluded": true,
        "partial": false
      },
      {
        "module": "llm_visibility",
        "score": null,
        "band": "unknown",
        "weight": 0.0,
        "issues_count": 0,
        "excluded": true,
        "partial": false
      },
      {
        "module": "tech",
        "score": 37,
        "band": "critical",
        "weight": 0.23809523809523808,
        "issues_count": 2,
        "excluded": false,
        "partial": false
      }
    ],
    "summary": {
      "issues_total": 7,
      "by_severity": {
        "critical": 1,
        "high": 1,
        "medium": 3,
        "low": 1,
        "info": 1
      },
      "by_module": {
        "performance": 3,
        "seo": 1,
        "ai_ready": 0,
        "llm_visibility": 0,
        "tech": 2,
        "accessibility": 1
      },
      "coverage": {
        "state": "scored",
        "state_reasons": [],
        "pages_read": 0,
        "pages_fetched": 1,
        "pages_failed": 0,
        "urls_known": 1
      },
      "impact_is_independent": true
    },
    "priorities": [
      {
        "rank": 1,
        "issue_key": "tech.crawler_blocked",
        "module": "tech",
        "severity": "critical",
        "title": "The site answers robots with status 403 instead of a page",
        "problem": "Our agent received 403 and saw no page content at all. Bot protection treats GPTBot, ClaudeBot and PerplexityBot the same way — their requests also arrive from an unfamiliar browser. Google may still get through, because it is recognised separately.",
        "action": "In your protection settings (Cloudflare, WAF, fail2ban) allow search and AI crawlers by their user-agent strings and IP ranges. Verify the result with URL Inspection in Search Console.",
        "consequence": "ChatGPT and similar services cannot read your site — that is stated outright, so there is nothing to infer here. Which leaves them nothing to mention you from. The rest of the report rests only on what could be seen from outside.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "statuses": [
            403
          ],
          "urls": [
            "https://www.unilever.com/"
          ],
          "pages_attempted": 1
        },
        "impact_points": 0,
        "impact_by_module": {
          "tech": 32
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 2,
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "high",
        "title": "No security headers at all",
        "problem": "All 5 are missing: content-security-policy, x-frame-options, x-content-type-options, referrer-policy, permissions-policy.",
        "action": "Configure them at the server or CDN level — this is configuration, not code.",
        "consequence": "The browser gets no instructions about how to treat your page, so it does not stop the page being embedded in someone else’s site. This is a server setting, not a hole in your code.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy"
          ],
          "present": []
        },
        "impact_points": 0,
        "impact_by_module": {
          "tech": 7
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 3,
        "issue_key": "a11y.failures",
        "module": "accessibility",
        "severity": "medium",
        "title": "1 accessibility remarks",
        "problem": "An automated Lighthouse pass found places where content is harder to read or to reach with a keyboard. Nobody verifies full standard compliance automatically — that needs manual testing.",
        "action": "Work through the list in the evidence. Most of these are fixed with markup attributes, without redesigning anything.",
        "consequence": "People with poor eyesight, on older phones, or using a keyboard instead of a mouse find the site harder to use than it needs to be.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "audits": [
            "color-contrast"
          ],
          "titles": [
            "Background and foreground colors do not have a sufficient contrast ratio."
          ],
          "lighthouse_score": 96.0,
          "strategy": "mobile"
        },
        "impact_points": 0,
        "impact_by_module": {
          "accessibility": 33
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 4,
        "issue_key": "perf.core_web_vitals:inp",
        "module": "performance",
        "severity": "medium",
        "title": "INP = 344 ms (mobile)",
        "problem": "Interaction to Next Paint — response delay to a user action. The «good» threshold is 200 ms.",
        "action": "Break up long JS tasks and reduce the amount of hydration.",
        "consequence": "The page noticeably stalls in response to clicks — it feels sluggish.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "metric": "INP",
          "value": 344.0,
          "threshold_good": 200,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "impact_points": 0,
        "impact_by_module": {
          "performance": 14
        },
        "effort": "high",
        "confidence": "high"
      },
      {
        "rank": 5,
        "issue_key": "perf.core_web_vitals:ttfb",
        "module": "performance",
        "severity": "medium",
        "title": "TTFB = 944 ms (mobile)",
        "problem": "Time To First Byte — server response time. The «good» threshold is 800 ms.",
        "action": "Enable caching/CDN and optimise database queries.",
        "consequence": "The server takes a long time to answer, which delays everything else.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "metric": "TTFB",
          "value": 944.0,
          "threshold_good": 800,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "impact_points": 0,
        "impact_by_module": {
          "performance": 14
        },
        "effort": "high",
        "confidence": "high"
      },
      {
        "rank": 6,
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "No HSTS header",
        "problem": "",
        "action": "Add `Strict-Transport-Security: max-age=31536000`.",
        "consequence": "The first visit may travel over an unprotected connection — a small but real security gap.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://www.unilever.com"
        },
        "impact_points": 0,
        "impact_by_module": {},
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 7,
        "issue_key": "perf.lighthouse_score",
        "module": "performance",
        "severity": "info",
        "title": "Lighthouse performance 63 (mobile)",
        "problem": "A score below 90 means noticeable speed problems.",
        "action": "Start with the top items in the opportunities block.",
        "consequence": "The overall speed score is low — on a slow connection the site will be hard to use.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "score": 63.0,
          "top_opportunities": [
            {
              "id": "unused-javascript",
              "title": "Reduce unused JavaScript",
              "savings_ms": 2700,
              "description": "Reduce unused JavaScript and defer loading scripts until they are required to decrease bytes consumed by network activity. [Learn how to reduce unused JavaScript](https://developer.chrome.com/docs/lighthouse/performance/unused-javascript/)."
            }
          ]
        },
        "impact_points": 0,
        "impact_by_module": {},
        "effort": "high",
        "confidence": "high"
      }
    ],
    "next_actions": [
      {
        "rank": 1,
        "issue_key": "tech.crawler_blocked",
        "module": "tech",
        "action": "In your protection settings (Cloudflare, WAF, fail2ban) allow search and AI crawlers by their user-agent strings and IP ranges. Verify the result with URL Inspection in Search Console.",
        "why": "ChatGPT and similar services cannot read your site — that is stated outright, so there is nothing to infer here. Which leaves them nothing to mention you from. The rest of the report rests only on what could be seen from outside.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "medium",
        "affected_pages": 1
      },
      {
        "rank": 2,
        "issue_key": "tech.security_headers",
        "module": "tech",
        "action": "Configure them at the server or CDN level — this is configuration, not code.",
        "why": "The browser gets no instructions about how to treat your page, so it does not stop the page being embedded in someone else’s site. This is a server setting, not a hole in your code.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "low",
        "affected_pages": 1
      },
      {
        "rank": 3,
        "issue_key": "a11y.failures",
        "module": "accessibility",
        "action": "Work through the list in the evidence. Most of these are fixed with markup attributes, without redesigning anything.",
        "why": "People with poor eyesight, on older phones, or using a keyboard instead of a mouse find the site harder to use than it needs to be.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "medium",
        "affected_pages": 0
      },
      {
        "rank": 4,
        "issue_key": "perf.core_web_vitals:inp",
        "module": "performance",
        "action": "Break up long JS tasks and reduce the amount of hydration.",
        "why": "The page noticeably stalls in response to clicks — it feels sluggish.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "high",
        "affected_pages": 1
      },
      {
        "rank": 5,
        "issue_key": "perf.core_web_vitals:ttfb",
        "module": "performance",
        "action": "Enable caching/CDN and optimise database queries.",
        "why": "The server takes a long time to answer, which delays everything else.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "high",
        "affected_pages": 1
      }
    ],
    "findings": [
      {
        "id": null,
        "code": "tech.crawler_blocked",
        "issue_key": "tech.crawler_blocked",
        "module": "tech",
        "severity": "critical",
        "title": "The site answers robots with status 403 instead of a page",
        "description": "Our agent received 403 and saw no page content at all. Bot protection treats GPTBot, ClaudeBot and PerplexityBot the same way — their requests also arrive from an unfamiliar browser. Google may still get through, because it is recognised separately.",
        "recommendation": "In your protection settings (Cloudflare, WAF, fail2ban) allow search and AI crawlers by their user-agent strings and IP ranges. Verify the result with URL Inspection in Search Console.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "statuses": [
            403
          ],
          "urls": [
            "https://www.unilever.com/"
          ],
          "pages_attempted": 1
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "tech.security_headers",
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "high",
        "title": "No security headers at all",
        "description": "All 5 are missing: content-security-policy, x-frame-options, x-content-type-options, referrer-policy, permissions-policy.",
        "recommendation": "Configure them at the server or CDN level — this is configuration, not code.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy"
          ],
          "present": []
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "a11y.failures",
        "issue_key": "a11y.failures",
        "module": "accessibility",
        "severity": "medium",
        "title": "1 accessibility remarks",
        "description": "An automated Lighthouse pass found places where content is harder to read or to reach with a keyboard. Nobody verifies full standard compliance automatically — that needs manual testing.",
        "recommendation": "Work through the list in the evidence. Most of these are fixed with markup attributes, without redesigning anything.",
        "page_url": null,
        "evidence": {
          "audits": [
            "color-contrast"
          ],
          "titles": [
            "Background and foreground colors do not have a sufficient contrast ratio."
          ],
          "lighthouse_score": 96.0,
          "strategy": "mobile"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.core_web_vitals",
        "issue_key": "perf.core_web_vitals:inp",
        "module": "performance",
        "severity": "medium",
        "title": "INP = 344 ms (mobile)",
        "description": "Interaction to Next Paint — response delay to a user action. The «good» threshold is 200 ms.",
        "recommendation": "Break up long JS tasks and reduce the amount of hydration.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "metric": "INP",
          "value": 344.0,
          "threshold_good": 200,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.core_web_vitals",
        "issue_key": "perf.core_web_vitals:ttfb",
        "module": "performance",
        "severity": "medium",
        "title": "TTFB = 944 ms (mobile)",
        "description": "Time To First Byte — server response time. The «good» threshold is 800 ms.",
        "recommendation": "Enable caching/CDN and optimise database queries.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "metric": "TTFB",
          "value": 944.0,
          "threshold_good": 800,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.https",
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "No HSTS header",
        "description": "",
        "recommendation": "Add `Strict-Transport-Security: max-age=31536000`.",
        "page_url": null,
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://www.unilever.com"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.lighthouse_score",
        "issue_key": "perf.lighthouse_score",
        "module": "performance",
        "severity": "info",
        "title": "Lighthouse performance 63 (mobile)",
        "description": "A score below 90 means noticeable speed problems.",
        "recommendation": "Start with the top items in the opportunities block.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "score": 63.0,
          "top_opportunities": [
            {
              "id": "unused-javascript",
              "title": "Reduce unused JavaScript",
              "savings_ms": 2700,
              "description": "Reduce unused JavaScript and defer loading scripts until they are required to decrease bytes consumed by network activity. [Learn how to reduce unused JavaScript](https://developer.chrome.com/docs/lighthouse/performance/unused-javascript/)."
            }
          ]
        },
        "verdict": null,
        "verdict_note": ""
      }
    ],
    "missing_data": [
      {
        "scope": "crawl",
        "kind": "collector_failed",
        "reason": "the site returned no page with content (response statuses: [403])",
        "affects": [
          "seo_score",
          "ai_ready_score",
          "llm_visibility_score"
        ],
        "note": "the module is excluded from the overall score; its weight is spread across the rest"
      }
    ],
    "engine_versions": {
      "schema": "1",
      "crawler": "3",
      "detector": "9bed4b4719a4",
      "scoring": "3fdd28054fda",
      "config": "ff5dfefdd052",
      "model": null
    },
    "localization": {
      "locale": "en",
      "fallback_locale": "en",
      "fell_back_strings": 0
    },
    "accessibility": {
      "available": false,
      "measured_url": null,
      "strategy": "mobile",
      "applicable": null,
      "passed": null,
      "failed": null,
      "findings": [],
      "lighthouse_score": null,
      "counts_toward_overall": false,
      "overall_weight": null
    }
  };

const BLOCKED_UK: AuditResult = {
    "contract_version": 2,
    "audit_id": "9c2e1b40-0000-4000-8000-00000000a004",
    "site_id": null,
    "url": "https://www.unilever.com/",
    "origin": "https://www.unilever.com",
    "status": "partial",
    "generated_at": "2026-08-23T16:20:39.640797Z",
    "finished_at": "2026-08-21T09:14:00Z",
    "overall_score": null,
    "overall_band": "unknown",
    "potential_score": null,
    "modules": [
      {
        "module": "performance",
        "score": 65,
        "band": "medium",
        "weight": 0.5238095238095237,
        "issues_count": 3,
        "excluded": false,
        "partial": false
      },
      {
        "module": "seo",
        "score": null,
        "band": "unknown",
        "weight": 0.0,
        "issues_count": 1,
        "excluded": true,
        "partial": false
      },
      {
        "module": "ai_ready",
        "score": null,
        "band": "unknown",
        "weight": 0.0,
        "issues_count": 0,
        "excluded": true,
        "partial": false
      },
      {
        "module": "llm_visibility",
        "score": null,
        "band": "unknown",
        "weight": 0.0,
        "issues_count": 0,
        "excluded": true,
        "partial": false
      },
      {
        "module": "tech",
        "score": 37,
        "band": "critical",
        "weight": 0.23809523809523808,
        "issues_count": 2,
        "excluded": false,
        "partial": false
      }
    ],
    "summary": {
      "issues_total": 7,
      "by_severity": {
        "critical": 1,
        "high": 1,
        "medium": 3,
        "low": 1,
        "info": 1
      },
      "by_module": {
        "performance": 3,
        "seo": 1,
        "ai_ready": 0,
        "llm_visibility": 0,
        "tech": 2,
        "accessibility": 1
      },
      "coverage": {
        "state": "scored",
        "state_reasons": [],
        "pages_read": 0,
        "pages_fetched": 1,
        "pages_failed": 0,
        "urls_known": 1
      },
      "impact_is_independent": true
    },
    "priorities": [
      {
        "rank": 1,
        "issue_key": "tech.crawler_blocked",
        "module": "tech",
        "severity": "critical",
        "title": "Сайт відповідає роботам кодом 403 замість сторінки",
        "problem": "Наш агент отримав 403 і не побачив жодної сторінки з вмістом. Так само поводиться захист від ботів із роботами GPTBot, ClaudeBot і PerplexityBot: їхні запити теж приходять із невідомого браузера. Google при цьому може заходити вільно — його впізнають окремо.",
        "action": "У налаштуваннях захисту (Cloudflare, WAF, fail2ban) дозвольте роботів пошукових систем і ШІ-сервісів за списком їхніх user-agent і діапазонів IP. Перевірити можна через «Перевірку URL» у Search Console.",
        "consequence": "ChatGPT і подібні сервіси не можуть прочитати ваш сайт і не згадують вас у відповідях. Решту звіту побудовано лише на тому, що вдалося побачити ззовні.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "statuses": [
            403
          ],
          "urls": [
            "https://www.unilever.com/"
          ],
          "pages_attempted": 1
        },
        "impact_points": 0,
        "impact_by_module": {
          "tech": 32
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 2,
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "high",
        "title": "Немає жодного заголовка безпеки",
        "problem": "Відсутні всі 5: content-security-policy, x-frame-options, x-content-type-options, referrer-policy, permissions-policy.",
        "action": "Налаштуйте їх на рівні сервера або CDN — це конфігурація, а не зміни в коді.",
        "consequence": "Браузер не отримує вказівок, як поводитися з вашою сторінкою, тож не заважає вбудувати її в чужий сайт. Це налаштування сервера, а не діра в коді.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy"
          ],
          "present": []
        },
        "impact_points": 0,
        "impact_by_module": {
          "tech": 7
        },
        "effort": "low",
        "confidence": "high"
      },
      {
        "rank": 3,
        "issue_key": "a11y.failures",
        "module": "accessibility",
        "severity": "medium",
        "title": "1 зауважень до доступності",
        "problem": "Автоматична перевірка Lighthouse знайшла місця, де вміст важче прочитати або пройти клавіатурою. Повну відповідність стандарту автоматично не перевіряє ніхто — це вимагає ручного тестування.",
        "action": "Пройдіться переліком у доказах. Більшість виправляється атрибутами в розмітці, без переробки дизайну.",
        "consequence": "Людям із поганим зором, на старих телефонах або з клавіатурою замість миші користуватися сайтом складніше, ніж могло б бути.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "audits": [
            "color-contrast"
          ],
          "titles": [
            "Background and foreground colors do not have a sufficient contrast ratio."
          ],
          "lighthouse_score": 96.0,
          "strategy": "mobile"
        },
        "impact_points": 0,
        "impact_by_module": {
          "accessibility": 33
        },
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 4,
        "issue_key": "perf.core_web_vitals:inp",
        "module": "performance",
        "severity": "medium",
        "title": "INP = 344 ms (mobile)",
        "problem": "Interaction to Next Paint — затримка відгуку на дію користувача. Поріг «добре» — 200 ms.",
        "action": "Розбийте довгі JS-задачі, зменшіть обсяг гідратації.",
        "consequence": "Сторінка помітно «підвисає» у відповідь на кліки — відчуття гальмування.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "metric": "INP",
          "value": 344.0,
          "threshold_good": 200,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "impact_points": 0,
        "impact_by_module": {
          "performance": 14
        },
        "effort": "high",
        "confidence": "high"
      },
      {
        "rank": 5,
        "issue_key": "perf.core_web_vitals:ttfb",
        "module": "performance",
        "severity": "medium",
        "title": "TTFB = 944 ms (mobile)",
        "problem": "Time To First Byte — час відповіді сервера. Поріг «добре» — 800 ms.",
        "action": "Увімкніть кешування/CDN, оптимізуйте запити до БД.",
        "consequence": "Сервер довго думає перед відповіддю, і це затримує геть усе інше.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "metric": "TTFB",
          "value": 944.0,
          "threshold_good": 800,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "impact_points": 0,
        "impact_by_module": {
          "performance": 14
        },
        "effort": "high",
        "confidence": "high"
      },
      {
        "rank": 6,
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "Немає заголовка HSTS",
        "problem": "",
        "action": "Додайте `Strict-Transport-Security: max-age=31536000`.",
        "consequence": "Перший візит може пройти незахищеним каналом — невелика, але реальна дірка в безпеці.",
        "scope": "site",
        "affected_pages": 0,
        "affected_examples": [],
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://www.unilever.com"
        },
        "impact_points": 0,
        "impact_by_module": {},
        "effort": "medium",
        "confidence": "high"
      },
      {
        "rank": 7,
        "issue_key": "perf.lighthouse_score",
        "module": "performance",
        "severity": "info",
        "title": "Lighthouse performance 63 (mobile)",
        "problem": "Скор нижче 90 означає відчутні проблеми зі швидкістю.",
        "action": "Почніть із топ-можливостей у блоці opportunities.",
        "consequence": "Загальна оцінка швидкості низька — на повільному інтернеті сайтом буде важко користуватися.",
        "scope": "page",
        "affected_pages": 1,
        "affected_examples": [
          "https://www.unilever.com/"
        ],
        "evidence": {
          "score": 63.0,
          "top_opportunities": [
            {
              "id": "unused-javascript",
              "title": "Reduce unused JavaScript",
              "savings_ms": 2700,
              "description": "Reduce unused JavaScript and defer loading scripts until they are required to decrease bytes consumed by network activity. [Learn how to reduce unused JavaScript](https://developer.chrome.com/docs/lighthouse/performance/unused-javascript/)."
            }
          ]
        },
        "impact_points": 0,
        "impact_by_module": {},
        "effort": "high",
        "confidence": "high"
      }
    ],
    "next_actions": [
      {
        "rank": 1,
        "issue_key": "tech.crawler_blocked",
        "module": "tech",
        "action": "У налаштуваннях захисту (Cloudflare, WAF, fail2ban) дозвольте роботів пошукових систем і ШІ-сервісів за списком їхніх user-agent і діапазонів IP. Перевірити можна через «Перевірку URL» у Search Console.",
        "why": "ChatGPT і подібні сервіси не можуть прочитати ваш сайт і не згадують вас у відповідях. Решту звіту побудовано лише на тому, що вдалося побачити ззовні.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "medium",
        "affected_pages": 1
      },
      {
        "rank": 2,
        "issue_key": "tech.security_headers",
        "module": "tech",
        "action": "Налаштуйте їх на рівні сервера або CDN — це конфігурація, а не зміни в коді.",
        "why": "Браузер не отримує вказівок, як поводитися з вашою сторінкою, тож не заважає вбудувати її в чужий сайт. Це налаштування сервера, а не діра в коді.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "low",
        "affected_pages": 1
      },
      {
        "rank": 3,
        "issue_key": "a11y.failures",
        "module": "accessibility",
        "action": "Пройдіться переліком у доказах. Більшість виправляється атрибутами в розмітці, без переробки дизайну.",
        "why": "Людям із поганим зором, на старих телефонах або з клавіатурою замість миші користуватися сайтом складніше, ніж могло б бути.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "medium",
        "affected_pages": 0
      },
      {
        "rank": 4,
        "issue_key": "perf.core_web_vitals:inp",
        "module": "performance",
        "action": "Розбийте довгі JS-задачі, зменшіть обсяг гідратації.",
        "why": "Сторінка помітно «підвисає» у відповідь на кліки — відчуття гальмування.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "high",
        "affected_pages": 1
      },
      {
        "rank": 5,
        "issue_key": "perf.core_web_vitals:ttfb",
        "module": "performance",
        "action": "Увімкніть кешування/CDN, оптимізуйте запити до БД.",
        "why": "Сервер довго думає перед відповіддю, і це затримує геть усе інше.",
        "expected_gain_points": 0,
        "expected_gain": "0 (модуль уже на мінімумі)",
        "effort": "high",
        "affected_pages": 1
      }
    ],
    "findings": [
      {
        "id": null,
        "code": "tech.crawler_blocked",
        "issue_key": "tech.crawler_blocked",
        "module": "tech",
        "severity": "critical",
        "title": "Сайт відповідає роботам кодом 403 замість сторінки",
        "description": "Наш агент отримав 403 і не побачив жодної сторінки з вмістом. Так само поводиться захист від ботів із роботами GPTBot, ClaudeBot і PerplexityBot: їхні запити теж приходять із невідомого браузера. Google при цьому може заходити вільно — його впізнають окремо.",
        "recommendation": "У налаштуваннях захисту (Cloudflare, WAF, fail2ban) дозвольте роботів пошукових систем і ШІ-сервісів за списком їхніх user-agent і діапазонів IP. Перевірити можна через «Перевірку URL» у Search Console.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "statuses": [
            403
          ],
          "urls": [
            "https://www.unilever.com/"
          ],
          "pages_attempted": 1
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "tech.security_headers",
        "issue_key": "tech.security_headers",
        "module": "tech",
        "severity": "high",
        "title": "Немає жодного заголовка безпеки",
        "description": "Відсутні всі 5: content-security-policy, x-frame-options, x-content-type-options, referrer-policy, permissions-policy.",
        "recommendation": "Налаштуйте їх на рівні сервера або CDN — це конфігурація, а не зміни в коді.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "missing": [
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy"
          ],
          "present": []
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "a11y.failures",
        "issue_key": "a11y.failures",
        "module": "accessibility",
        "severity": "medium",
        "title": "1 зауважень до доступності",
        "description": "Автоматична перевірка Lighthouse знайшла місця, де вміст важче прочитати або пройти клавіатурою. Повну відповідність стандарту автоматично не перевіряє ніхто — це вимагає ручного тестування.",
        "recommendation": "Пройдіться переліком у доказах. Більшість виправляється атрибутами в розмітці, без переробки дизайну.",
        "page_url": null,
        "evidence": {
          "audits": [
            "color-contrast"
          ],
          "titles": [
            "Background and foreground colors do not have a sufficient contrast ratio."
          ],
          "lighthouse_score": 96.0,
          "strategy": "mobile"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.core_web_vitals",
        "issue_key": "perf.core_web_vitals:inp",
        "module": "performance",
        "severity": "medium",
        "title": "INP = 344 ms (mobile)",
        "description": "Interaction to Next Paint — затримка відгуку на дію користувача. Поріг «добре» — 200 ms.",
        "recommendation": "Розбийте довгі JS-задачі, зменшіть обсяг гідратації.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "metric": "INP",
          "value": 344.0,
          "threshold_good": 200,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.core_web_vitals",
        "issue_key": "perf.core_web_vitals:ttfb",
        "module": "performance",
        "severity": "medium",
        "title": "TTFB = 944 ms (mobile)",
        "description": "Time To First Byte — час відповіді сервера. Поріг «добре» — 800 ms.",
        "recommendation": "Увімкніть кешування/CDN, оптимізуйте запити до БД.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "metric": "TTFB",
          "value": 944.0,
          "threshold_good": 800,
          "rating": "needs-improvement",
          "strategy": "mobile",
          "source": "field",
          "provider": "psi"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "seo.https",
        "issue_key": "seo.https:no_hsts",
        "module": "seo",
        "severity": "low",
        "title": "Немає заголовка HSTS",
        "description": "",
        "recommendation": "Додайте `Strict-Transport-Security: max-age=31536000`.",
        "page_url": null,
        "evidence": {
          "found": null,
          "expected": "Strict-Transport-Security: max-age=31536000",
          "origin": "https://www.unilever.com"
        },
        "verdict": null,
        "verdict_note": ""
      },
      {
        "id": null,
        "code": "perf.lighthouse_score",
        "issue_key": "perf.lighthouse_score",
        "module": "performance",
        "severity": "info",
        "title": "Lighthouse performance 63 (mobile)",
        "description": "Скор нижче 90 означає відчутні проблеми зі швидкістю.",
        "recommendation": "Почніть із топ-можливостей у блоці opportunities.",
        "page_url": "https://www.unilever.com/",
        "evidence": {
          "score": 63.0,
          "top_opportunities": [
            {
              "id": "unused-javascript",
              "title": "Reduce unused JavaScript",
              "savings_ms": 2700,
              "description": "Reduce unused JavaScript and defer loading scripts until they are required to decrease bytes consumed by network activity. [Learn how to reduce unused JavaScript](https://developer.chrome.com/docs/lighthouse/performance/unused-javascript/)."
            }
          ]
        },
        "verdict": null,
        "verdict_note": ""
      }
    ],
    "missing_data": [
      {
        "scope": "crawl",
        "kind": "collector_failed",
        "reason": "сайт не віддав жодної сторінки з контентом (статуси відповіді: [403])",
        "affects": [
          "seo_score",
          "ai_ready_score",
          "llm_visibility_score"
        ],
        "note": "модуль виключено з overall, ваги перерозподілені між рештою"
      }
    ],
    "engine_versions": {
      "schema": "1",
      "crawler": "3",
      "detector": "9bed4b4719a4",
      "scoring": "3fdd28054fda",
      "config": "ff5dfefdd052",
      "model": null
    },
    "localization": {
      "locale": "uk",
      "fallback_locale": "en",
      "fell_back_strings": 0
    },
    "accessibility": {
      "available": false,
      "measured_url": null,
      "strategy": "mobile",
      "applicable": null,
      "passed": null,
      "failed": null,
      "findings": [],
      "lighthouse_score": null,
      "counts_toward_overall": false,
      "overall_weight": null
    }
  };

/**
 * Результат під мову інтерфейсу.
 *
 * У продукті мова — параметр запиту до API, і зміна мови означає новий
 * запит, а не переклад на клієнті. Макет повторює цю залежність, щоб її
 * було видно на екрані.
 */
export function mockResult(id: string, locale: Locale): AuditResult {
  const uk = locale === "uk";
  if (id === "9c2e1b40-0000-4000-8000-00000000a001") return uk ? SCORED_UK : SCORED_EN;
  if (id === "9c2e1b40-0000-4000-8000-00000000a004") return uk ? BLOCKED_UK : BLOCKED_EN;
  return uk ? SCORED_UK : SCORED_EN;
}

/** Аудит, який не дав бала: сайт віддав 403 на все. */
export const BLOCKED_AUDIT_ID = "9c2e1b40-0000-4000-8000-00000000a004";
