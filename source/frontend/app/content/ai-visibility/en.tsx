/**
 * ai-visibility — en. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { PresenceModels } from "../../components/PresenceModels";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import {
  Bullets,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("en");
  return (
    <>
      <Hero
        eyebrow={"AI visibility"}
        title={"Can AI systems see and mention you?"}
        lead={"Crawldy checks whether AI can retrieve your pages, understand the information about your company and use the site as a source. In the full report, Actual AI Presence also shows whether ChatGPT, Claude, Perplexity and Gemini mention your brand."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"Access for AI"} lead={"We check whether AI systems can load your pages and retrieve the main content. We take into account restrictions on AI crawlers, server responses and how much the site depends on JavaScript."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Understanding your business"} lead={"We check whether the pages make it clear who you are, what you offer and how to contact you. For that we analyse the content structure, company details, contacts and the relevant markup."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Suitability as a source"} lead={"We check whether the site contains clear answers, enough context, stated authorship and claims that AI can use correctly in an answer."} />
          </div>
        </div>
      </Section>

      <Section>
        <Heading title={"Actual presence in answers"} />
        <PresenceModels
          intro={"For each check, Crawldy uses the models selected as the most representative of the current user experience on each AI platform."}
          note={"AI platform models change over time, and different models may mention brands, recommend companies and use sources differently. An Actual AI Presence result therefore refers to the models listed for that specific check."}
        />
      </Section>

      <Section bordered={false}>
        <Heading title={"What you will see in the report"} />
        <Bullets
          items={[
            "problems that stop AI from retrieving or understanding your content",
            "the pages and the evidence behind every conclusion",
            "brand mentions and links in assistants' answers",
            "the other domains assistants named instead of you",
            "priorities for fixing",
          ]}
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
  slug: "ai-visibility",
  title: "AI visibility — can AI retrieve, understand and mention your site?",
  h1: "Can AI systems see and mention you?",
  description:
    "Whether AI systems can access your pages, understand your business and use the site as a source — plus the actual brand mentions in ChatGPT, Claude, Perplexity and Gemini answers.",
  navLabel: "AI visibility",
  Body,
};
