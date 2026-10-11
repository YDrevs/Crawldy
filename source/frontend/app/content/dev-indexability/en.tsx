/**
 * Indexability — довідкова сторінка для розробника.
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
        eyebrow="Indexability"
        title="Four ways a reachable page still fails to be indexed"
        lead="Being fetched is the beginning. A page can be reachable, fast and well written and still never be indexed, for reasons that are all invisible in a browser."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "A noindex directive is an instruction, not a defect",
                detail:
                  "It is honoured, and it is often correct: staging areas, internal variants, thin archives. What matters is whether it was intended — which only you can say. A page you also link to prominently is the case worth a second look.",
              },
              {
                term: "Canonical is a strong hint about identity",
                detail:
                  "It tells a client which address represents this content. Conflicting signals — a canonical pointing one way, a redirect another, a sitemap a third — leave the decision to the crawler, and the choice may not be yours.",
              },
              {
                term: "Status codes carry meaning",
                detail:
                  "A not-found page returned with 200 creates an indexable page that says nothing. A temporary redirect where a permanent one was meant leaves both addresses alive.",
              },
              {
                term: "HTTPS is not optional any more",
                detail:
                  "A page served over plain HTTP is a critical problem, not a note: browsers warn about it, and it undermines every other signal on the page.",
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
                term: "Linking to a page you have forbidden",
                detail:
                  "An internal link pointing at a page you told search engines to skip is a contradiction visible only when both signals are checked together — which is why it takes two observations to find.",
              },
              {
                term: "Sitemap and canonical disagreeing",
                detail:
                  "Listing one address while it canonicalises to another tells the crawler two different things about the same content.",
              },
              {
                term: "Parameters creating identity",
                detail:
                  "Tracking and sorting parameters produce distinct URLs for the same document unless canonical says otherwise.",
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
            text: "Getting fetched in the first place.",
          },
          {
            href: "/developers/robots",
            label: "robots.txt",
            text: "Why disallow is not the way to deindex.",
          },
          {
            href: "/technical-seo-audit",
            label: "Technical SEO audit",
            text: "All of this checked against your site.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "indexability",
  title: "Indexability — noindex, canonical, redirects and status codes",
  h1: "Four ways a reachable page still fails to be indexed",
  description:
    "Why a page that answers with 200 can still be absent from an index: robots directives, canonical conflicts, redirect behaviour and status codes that do not mean what they appear to.",
  navLabel: "Indexability",
  Body,
};
