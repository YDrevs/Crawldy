/**
 * robots.txt — довідкова сторінка для розробника.
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
        eyebrow="robots.txt"
        title="What robots.txt actually controls"
        lead="A plain text file at one fixed address, read before almost anything else — and routinely asked to do two jobs it cannot do."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "It governs fetching, not indexing",
                detail:
                  "A disallowed URL can still appear in results if enough external links point at it: the crawler obeys the rule and indexes the address without the content. To keep a page out of an index, let it be fetched and answer with a noindex directive.",
              },
              {
                term: "Rules are per user agent",
                detail:
                  "Groups are matched by the most specific agent that applies, and only that group is used. An agent matched by its own block inherits nothing from the wildcard group.",
              },
              {
                term: "It is not access control",
                detail:
                  "It is a request that well-behaved clients honour. Anything that must not be readable needs authentication, not a line in a text file.",
              },
              {
                term: "Sitemap lines stand alone",
                detail:
                  "A sitemap declaration is not scoped to any user-agent group and can appear anywhere in the file.",
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
                term: "An error page served with status 200",
                detail:
                  "The most common invisible failure. Your server answers the robots.txt request with a styled HTML error page and a success code; the client parses HTML as directives, finds none, and proceeds as if everything were allowed. Check the status and the content type, not just that something came back.",
              },
              {
                term: "Blocking assets",
                detail:
                  "Disallowing CSS or JavaScript prevents rendering from reproducing your page. The crawler then judges a version of the site nobody sees.",
              },
              {
                term: "Staging rules reaching production",
                detail:
                  "A blanket disallow copied with the deployment. From outside it is indistinguishable from a deliberate decision, which is why an audit reports it and asks you to confirm rather than calling it a defect.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/developers/crawling",
            label: "Crawling",
            text: "What happens after a fetch is allowed.",
          },
          {
            href: "/developers/ai-crawlers",
            label: "AI crawlers",
            text: "Per-agent decisions that are not one decision.",
          },
          {
            href: "/developers/indexability",
            label: "Indexability",
            text: "Why a fetched page can still be missing.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "robots",
  title: "robots.txt — what it controls, and the failure nobody sees",
  h1: "What robots.txt actually controls",
  description:
    "Per-agent rules, the difference between crawling and indexing, the error page served with status 200, and why robots.txt is a crawler signal rather than access control.",
  navLabel: "robots.txt",
  Body,
};
