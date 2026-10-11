/**
 * What we check — English.
 *
 * Структура — рішення власника (журнал правок, екран 02): вступ → шість
 * напрямів (неінтерактивні картки) → як формується оцінка → що
 * виправляти насамперед → футер. Без повторного блоку запуску, без
 * прикладу звіту, без «Related»: ці переходи вже є на головній і в
 * меню футера. Порівняльного наміру («best …») тут як не було, так і
 * немає — у нього інша сторінка видачі.
 */

import {
  CardGrid,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("en");
  return (
    <>
      <Hero
        eyebrow="Website audit"
        title="Website analysis for Search and AI"
        lead="Crawldy checks your site across six dimensions and shows what is worth fixing first. For every problem the report carries the evidence and the pages it concerns."
      />

      <Section>
        <Heading
          title="The six dimensions of the check"
          lead="Crawldy checks your site's visibility in search and AI, its speed, security basics and accessibility."
        />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Search visibility",
              text: "We check whether search engines can find and read your pages, whether there are technical signals that may hinder indexing, and whether the site structure and links have problems.",
            },
            {
              icon: "clock",
              title: "Speed & UX",
              text: "We check how fast pages load, how the server responds and what may slow the site down. Where real-user data is available, we take it into account too.",
            },
            {
              icon: "globe",
              title: "AI readiness",
              text: "We check whether AI can correctly recognise your business, its pages, contacts and other key information.",
            },
            {
              icon: "link",
              title: "AI citability",
              text: "We check whether the site offers clear answers, stated authorship and enough context for AI to use it as a source.",
            },
            {
              icon: "alert",
              title: "Security basics",
              text: "We check HTTPS, security settings, form protection and correct handling of technical errors. This is not a vulnerability scan.",
            },
            {
              icon: "user",
              title: "Accessibility",
              text: "We check for common problems that may keep people from using the site. This is an automated check, not a WCAG certification.",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="How the site score is formed"
          lead="The result depends not only on the problems found but also on how much of the site could be checked. That is why Crawldy shows coverage next to the score."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Coverage is visible right away",
                detail:
                  "We show how many pages were found, fetched and checked, and how many could not be reached.",
              },
              {
                term: "What was not measured does not lower the score",
                detail:
                  "The score is calculated only for the dimensions we could measure. When data is missing, Crawldy says so directly instead of scoring a zero.",
              },
              {
                term: "Not enough data — no score",
                detail:
                  "If too little of the site was checked, Crawldy does not show an unreliable overall score. The available findings stay in the report as observations.",
              },
              {
                term: "Every conclusion can be verified",
                detail:
                  "For every problem we show what we expected to find, what we found and on which pages. That helps you verify the result and fix it faster.",
              },
            ]}
          />
        </div>
      </Section>

      <Section bordered={false}>
        <Heading
          title="What to fix first"
          lead="Crawldy orders problems by priority, weighing their severity, expected effect, fix effort and how important the page is. You see right away where to start."
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
  slug: "website-audit",
  title: "Website Audit Tool — six dimensions, evidence, priorities",
  h1: "Website analysis for Search and AI",
  description:
    "Crawl your site and get one prioritised report across search visibility, AI readiness, citability, speed, security basics and accessibility — with coverage and evidence for every finding.",
  navLabel: "What we check",
  Body,
};
