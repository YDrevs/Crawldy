/**
 * Structured data — довідкова сторінка для розробника.
 *
 * Форма однакова в усіх семи: теза, факти, типові хиби, посилання назад
 * до вимірювання. Розробник приходить із конкретним питанням і йде,
 * щойно отримає відповідь.
 *
 * Жодне твердження не претендує на універсальність поведінки краулерів:
 * вона різна у вендорів і змінюється без попередження. Там, де ми не
 * впевнені, стоїть «може», а не «не робить».
 *
 * Файл згенерований: `scratchpad/gen_dev_pages.py`.
 */

import {
  Definitions,
  Heading,
  Hero,
  Related,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        eyebrow="Structured data"
        title="Markup that machines can actually connect"
        lead="Structured data answers a question your prose answers badly: who is this, and what is this page. The value is in the connections, not the volume."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "JSON-LD in the HTML",
                detail:
                  "One script block, present in the source rather than injected later. Markup added after render does not exist for clients that do not render.",
              },
              {
                term: "Organization is the anchor",
                detail:
                  "Name, address of the site, description — as data. Everything else refers back to it, which is what makes the pieces one entity rather than several.",
              },
              {
                term: "sameAs connects you to what is already known",
                detail:
                  "Links from your markup to your profiles elsewhere: Wikidata, LinkedIn, GitHub, Crunchbase. A common way systems link references to the same brand across sources they did not get from you.",
              },
              {
                term: "A graph, not a pile",
                detail:
                  "Stable identifiers letting the site, the organisation and page-level types reference one another. Independent blocks that never point at each other describe several unrelated things.",
              },
            ]}
          />
        </div>
      </Section>

      <Section>
        <Heading
          title="Where it usually goes wrong"
          lead="Each of these is something Crawldy reports on real sites, not a hypothetical."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Markup that contradicts the page",
                detail:
                  "A type claiming something the visible content does not support. Worse than no markup: it makes the rest less trustworthy.",
              },
              {
                term: "FAQ markup without a visible FAQ",
                detail:
                  "The markup describes content that has to be on the page. Adding it because it once produced rich results is how a site collects penalties instead of visibility.",
              },
              {
                term: "Review and rating markup you cannot substantiate",
                detail:
                  "Aggregate ratings for yourself, about yourself, with no source. Cheap to add, and exactly the signal that gets discounted.",
              },
              {
                term: "Requiring properties nobody consumes",
                detail:
                  "Not every optional field earns its place. A missing locale hint is not a defect — consumers assume a default — while a missing title genuinely costs you.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/developers/javascript-rendering",
            label: "JavaScript rendering",
            text: "Why markup has to be in the HTML.",
          },
          {
            href: "/ai-visibility",
            label: "AI visibility",
            text: "What entity signals are for.",
          },
          {
            href: "/geo-audit",
            label: "GEO audit",
            text: "Where structured data fits into generative visibility.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "structured-data",
  title: "Structured data — markup that machines can connect",
  h1: "Markup that machines can actually connect",
  description:
    "JSON-LD in practice: Organization, sameAs, a linked entity graph, breadcrumbs, and the markup that is not worth adding.",
  navLabel: "Structured data",
  Body,
};
