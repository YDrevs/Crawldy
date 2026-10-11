/**
 * Developer hub — вхід у технічну частину.
 *
 * ## Не SEO-наповнювач
 *
 * Розробник приходить сюди з конкретним питанням і йде, щойно отримає
 * відповідь. Тому хаб — це маршрутизатор, а не есе: коротка теза про
 * різницю між читачами й сім посилань, кожне з яких відповідає на своє
 * питання.
 *
 * ## Публічного API тут немає
 *
 * Сторінки `/developers/api` не існує, поки немає самого API.
 * Індексована порожня сторінка з написом «незабаром» — це обіцянка, яку
 * пошук покаже людині, що шукала документацію.
 */

import {
  CardGrid,
  Heading,
  Hero,
  More,
  Prose,
  Related,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        eyebrow="For developers"
        title="How search engines and AI crawlers actually read a site"
        lead="Reference notes on the mechanics: what a crawler receives, what it can parse, and where the two audiences diverge. Written from what Crawldy observes on real sites rather than from what the specifications promise."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading
          title="One request, two very different readers"
          lead="Both fetch the same URL. What happens next is not the same, and almost every technical finding in an audit lives in that gap."
        />
        <Prose
          paragraphs={[
            "A search crawler will queue your page for rendering, execute JavaScript, and index what the browser produced. An AI crawler may do none of that — many fetch the HTML, parse it, and move on. Neither behaviour is universal, and vendors change it without announcing anything.",
            "So the practical question is not “does my site work” but “how much of my site survives each path”. These pages cover the parts of that answer you can control.",
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Reference"
          lead="Each page answers one question and links back to the measurement it belongs to."
        />
        <CardGrid
          cards={[
            {
              icon: "globe",
              title: "Crawling",
              text: "How a crawler discovers pages, what limits it, and why a sitemap is a hint rather than an instruction.",
              href: "/developers/crawling",
            },
            {
              icon: "link",
              title: "AI crawler access",
              text: "Which agents fetch on behalf of answer engines, how they differ from search, and why blocking one does not block the other.",
              href: "/developers/ai-crawlers",
            },
            {
              icon: "list",
              title: "robots.txt",
              text: "What it can and cannot do, the failure that returns 200 with an HTML body, and per-agent rules.",
              href: "/developers/robots",
            },
            {
              icon: "clock",
              title: "JavaScript rendering",
              text: "What exists before scripts run, how to measure the difference, and who never sees the rendered version.",
              href: "/developers/javascript-rendering",
            },
            {
              icon: "search",
              title: "Indexability",
              text: "noindex, canonical, redirects and status codes — the four ways a reachable page still fails to be indexed.",
              href: "/developers/indexability",
            },
            {
              icon: "check",
              title: "Structured data",
              text: "JSON-LD that machines can connect: Organization, sameAs, a linked graph, and the markup not worth adding.",
              href: "/developers/structured-data",
            },
          ]}
        />
        {/* Шість карток, а не сім: у сітці на три колонки сьома лишає
            дві порожні клітинки, і сірий прямокутник читається як
            поламана верстка. Скоринг стоїть окремим посиланням і по суті
            — він не сусід механіки краулера, а місток до методології. */}
        <More href="/developers/scoring" label="How findings become a number" />
      </Section>

      <Section>
        <Heading
          title="Crawldy's own crawler"
          lead="If you are looking at your logs, this is us — and this is what we allow on our own site."
        />
        <Prose
          paragraphs={[
            "Our crawler identifies itself in the User-Agent and follows robots.txt. It respects redirects up to a small limit, caps response size, and never posts anything. If it was refused, your report says so instead of guessing at content it never received.",
            "On crawldy.ai we allow search and discovery crawlers, allow AI agents that fetch to answer a question, and refuse agents that collect content for model training. Google-Extended is treated as its own decision rather than part of search — blocking it costs nothing in Google Search, and conflating the two is a common and expensive mistake.",
          ]}
        />
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/methodology",
            label: "Methodology",
            text: "How measurement, coverage and confidence fit together.",
          },
          {
            href: "/technical-seo-audit",
            label: "Technical SEO audit",
            text: "The same mechanics, run against your site with evidence.",
          },
          {
            href: "/ai-visibility",
            label: "AI visibility",
            text: "Access, understanding and usability as a source.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "developers",
  title: "For developers — how search engines and AI crawlers read a site",
  h1: "How search engines and AI crawlers actually read a site",
  description:
    "Reference notes on crawling, robots.txt, AI crawler access, JavaScript rendering, indexability, structured data and scoring — from what Crawldy observes on real sites.",
  navLabel: "Developers",
  Body,
};
