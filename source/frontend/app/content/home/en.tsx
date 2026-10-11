/**
 * Головна сторінка — по одній на мову.
 *
 * ## Побудова після проходу 2026-09-03 (журнал правок, екран 01)
 *
 * Питання → форма адреси → три спрощені питання → прозора оцінка.
 * Без надзаголовка й пояснення під питанням: поле і кнопка роблять
 * наступну дію очевидною. Без внутрішньої термінології (Actual AI
 * Presence) і умов оплати — це мова продукту, не першого екрана.
 *
 * ## Мови — не переклади одна одної
 *
 * Спільні факти про продукт, власні речення кожною мовою.
 */

import { HeroAuditForm } from "../../components/HeroAuditForm";
import { ScorePreview } from "../../components/ScorePreview";
import {
  CardGrid,
  Heading,
  Hero,
  More,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        title="Can search engines and AI actually see your site?"
        action={
          <HeroAuditForm
            placeholder="your-site.com"
            cta="Run a free check"
            invalid="Enter a website address like example.com."
          />
        }
        aside={<ScorePreview locale="en" />}
      />

      <Section>
        <Heading title="One website analysis answers the three key questions about your visibility in search and AI." />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Can search find you?",
              text: "We check whether Google and other search engines can find and read your pages.",
              href: "/seo-audit",
            },
            {
              icon: "globe",
              title: "Does AI understand your site?",
              text: "We check whether AI can read your site and understand the information about your business.",
              href: "/ai-visibility",
            },
            {
              icon: "link",
              title: "Does AI mention your brand?",
              text: "We check whether ChatGPT, Claude, Perplexity and Gemini name your brand in answers about your niche.",
              href: "/ai-visibility",
            },
          ]}
        />
        <More href="/website-audit" label="All parts of the check" />
      </Section>

      <Section bordered={false}>
        <Heading
          title="A transparent site score"
          lead="You see which pages were checked, what could be measured, and what the final score is based on."
        />
        <More href="/methodology" label="How the measurement works" />
      </Section>
    </>
  );
}

export const en: LocalizedPage = {
  slug: "",
  title: "Crawldy — can search engines and AI actually see your site?",
  h1: "Can search engines and AI actually see your site?",
  description:
    "Crawldy shows what keeps your site from being visible in search and AI — and what to fix first.",
  navLabel: "Home",
  Body,
};
