/**
 * AI crawlers — довідкова сторінка для розробника.
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
        eyebrow="AI crawler access"
        title="AI crawlers are not one audience, and not one decision"
        lead="Three different things arrive at your server and all get called AI crawlers. Treating them as one policy is the most common way sites lose visibility they meant to keep."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Answer-engine fetching",
                detail:
                  "An agent retrieves your page because someone asked a question it wants to answer, often citing the source. This is closest to search: the referral and the attribution are the point of allowing it.",
              },
              {
                term: "Training collection",
                detail:
                  "An agent gathers content into a dataset. No question, no citation, no visit. Allowing it is a legitimate choice, but it is a different choice, and it deserves to be made deliberately.",
              },
              {
                term: "Search crawlers that also feed AI surfaces",
                detail:
                  "The same crawler that indexes for search may also supply an AI feature in the same product. Blocking it costs you search.",
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
                term: "Treating Google-Extended as a search control",
                detail:
                  "It is not. It governs use of your content in Google AI products; it does not affect Googlebot, indexing or ranking. Sites block Googlebot believing they are opting out of AI, and lose search instead.",
              },
              {
                term: "Assuming JavaScript will run",
                detail:
                  "Many agents fetch and parse HTML without executing scripts. If your content appears only after rendering, it is absent for them — and no markup fixes content that was never received.",
              },
              {
                term: "Assuming a rule stays true",
                detail:
                  "User-agent strings change, new agents appear, and behaviour is documented inconsistently. A policy written once and never revisited slowly stops meaning what it meant.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/developers/robots",
            label: "robots.txt",
            text: "How to express per-agent rules.",
          },
          {
            href: "/developers/javascript-rendering",
            label: "JavaScript rendering",
            text: "What exists before scripts run.",
          },
          {
            href: "/ai-visibility",
            label: "AI visibility",
            text: "What we measure on your site, and what we do not.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "ai-crawlers",
  title: "AI crawler access — answer engines, training, and the difference",
  h1: "AI crawlers are not one audience, and not one decision",
  description:
    "Which agents fetch on behalf of answer engines, how they differ from search crawlers and from training collectors, and why one rule cannot express all three decisions.",
  navLabel: "AI crawlers",
  Body,
};
