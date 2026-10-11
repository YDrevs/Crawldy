/**
 * Методологія — англійська. Побудова за рішенням власника (екран 06):
 * покриття → перевірені дані → докази → оцінка → пріоритети, і
 * компактні «Точні правила розрахунку» зі знімка реального скорингу.
 */

import { ScoringRules } from "../../components/ScoringRules";
import { Heading, Hero, Prose, Section } from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("en");
  return (
    <>
      <Hero
        eyebrow="Methodology"
        title={"How Crawldy arrives at the results of an analysis"}
        lead={"Crawldy draws conclusions only from what it could actually check. For every problem found, the report shows the evidence, the context and the logic behind its priority."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title="First we establish coverage" />
            <Prose
              paragraphs={[
                "Crawldy finds the site's pages and checks which of them could be fetched and analysed. The report shows how many pages were found, checked and unreachable.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Only verified data counts" />
            <Prose
              paragraphs={[
                "If part of the site or an individual signal could not be checked, Crawldy does not score it as zero and does not invent a result. Such data stays out of the calculation. When coverage is insufficient, no overall score is shown.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Every problem is backed by evidence" />
            <Prose
              paragraphs={[
                "For every finding the report shows what was checked, what was found and on which pages. That lets you verify the conclusion and understand what exactly needs fixing.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Forming the score" />
            <Prose
              paragraphs={[
                "Problems affect the result differently. Serious violations weigh more than minor ones. A problem repeated across many pages is counted, but its impact is not multiplied without limit.",
                "The overall score is formed only from the dimensions with enough data.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Deciding what to fix first" />
            <Prose
              paragraphs={[
                "Crawldy weighs the severity of a problem, the expected result, the effort of the fix and the importance of the page. So the report shows right away where to start.",
              ]}
            />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title="Exact calculation rules" />
        <ScoringRules
          locale="en"
          strings={{
            caption: "Scoring rules",
            weightsTitle: "Dimension weights",
            severityTitle: "Severity multipliers",
            limitsTitle: "Limits",
            modules: {
              seo: "Search visibility",
              performance: "Speed & UX",
              ai_ready: "AI readiness",
              tech: "Security basics",
              llm_visibility: "AI citability",
              accessibility: "Accessibility",
            },
            severities: {
              critical: "Critical",
              high: "High",
              medium: "Medium",
              low: "Low",
              info: "Informational",
            },
            minCoverageLabel: "Minimum text for content scoring",
            minCoverageValue: "{n} words across the site",
            repetitionLabel: "Repetition of one problem",
            repetitionValue: "at most ×{n} of a single finding",
            shareLabel: "One problem's impact on a dimension",
            shareValue: "at most {p} of the dimension's half-scale",
          }}
        />
      </Section>

      <SiteCta
        title={cta.title}
        text={cta.text}
        cta={cta.cta}
        href={cta.href}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "methodology",
  title: "Methodology — how Crawldy arrives at the results of an analysis",
  h1: "How Crawldy arrives at the results of an analysis",
  description:
    "Coverage, verified data, evidence, score and priorities: how Crawldy measures a site — with the exact calculation rules it uses.",
  navLabel: "Methodology",
  Body,
};
