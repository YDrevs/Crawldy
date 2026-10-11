/**
 * Crawling — довідкова сторінка для розробника.
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
        eyebrow="Crawling"
        title="How a crawler decides what to fetch, and what stops it"
        lead="Discovery is a graph walk with a budget. Sitemaps, priorities and crawl rate adjust that walk rather than replacing it."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Links are the primary map",
                detail:
                  "A crawler starts somewhere and follows what it finds. A page nothing links to is reachable only if something else tells the crawler it exists — which is what a sitemap is for, and why an orphan page in a sitemap still behaves differently from a linked one.",
              },
              {
                term: "A sitemap is a hint",
                detail:
                  "Being listed does not guarantee a fetch, and being absent does not prevent one. Last-modified dates are only useful if they mean something: a file where every entry claims today carries no information and gets treated accordingly.",
              },
              {
                term: "Budgets are real and finite",
                detail:
                  "Nobody reads a large site exhaustively on every pass. What gets read is a sample, and which sample matters enormously — the beginning of a sitemap is usually whatever the CMS wrote first, which on a shop is thousands of product URLs and none of the pages that explain the business.",
              },
              {
                term: "Depth costs discovery",
                detail:
                  "Pages many clicks from the entry point are fetched later and less often. This is not a ranking rule, it is arithmetic: a walk with a budget reaches near things first.",
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
                term: "Faceted URLs eating the budget",
                detail:
                  "Filter and sort parameters multiply one page into hundreds. From outside they look like distinct URLs with near-identical content, and a crawler spends its budget proving they are the same.",
              },
              {
                term: "Slow responses that look like refusal",
                detail:
                  "A crawler with a timeout treats a slow page as an unavailable one. Server response time is not only a speed metric — past a point it becomes a discovery problem.",
              },
              {
                term: "Redirect chains",
                detail:
                  "Each hop costs a request and some clients give up before the end. A chain of three that ends in a 404 is invisible from a browser, where it looks like an ordinary broken link.",
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
            text: "What can and cannot stop a fetch.",
          },
          {
            href: "/developers/indexability",
            label: "Indexability",
            text: "Fetched is not the same as indexed.",
          },
          {
            href: "/technical-seo-audit",
            label: "Technical SEO audit",
            text: "The same mechanics, run against your site.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "crawling",
  title: "Crawling — how crawlers discover and fetch your pages",
  h1: "How a crawler decides what to fetch, and what stops it",
  description:
    "How discovery works, why a sitemap is a hint and not an instruction, what a page budget means for large sites, and the ways a crawl quietly ends early.",
  navLabel: "Crawling",
  Body,
};
