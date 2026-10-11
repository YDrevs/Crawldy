/**
 * GEO audit — намір є, магії немає.
 *
 * ## Чому це окрема сторінка, а не синонім AI visibility
 *
 * За матрицею «GEO audit» має власний обсяг і низьку складність у трьох
 * ринках із шести. Люди шукають саме це слово, і сторінка, якої немає,
 * не відповідає їм узагалі.
 *
 * Але намір інший, а не лише слово. Той, хто набирає «GEO audit», уже
 * прочитав про генеративну оптимізацію й питає: **що з цього взагалі
 * можна перевірити**. Тому сторінка побудована як розмежування —
 * перевірне проти неперевірного, — а не як друга посадкова про AI.
 *
 * ## Окремого бала GEO немає й не буде вигаданого
 *
 * Найлегший спосіб продати цю сторінку — намалювати «GEO Score». Він не
 * вимірював би нічого нового: під ним лежать ті самі доступність,
 * розмітка й структура. Тому тут прямо сказано, що окремого числа немає.
 */

import {
  CardGrid,
  Definitions,
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
        eyebrow="GEO audit"
        title="Generative engine optimisation, minus the parts nobody can measure"
        lead="GEO is a name for an old question in a new setting: can a machine get your content, understand it, and use it in an answer. Crawldy checks the part of that which lives on your site — and says plainly which part does not."
        primary={{ href: "/result", label: "Check my site" }}
      />

      <Section>
        <Heading
          title="There is no separate GEO score, and that is deliberate"
          lead="Underneath the term are the same technical facts an audit already measures. A distinct number would not measure anything new — it would relabel what is already there and imply a second, independent judgement."
        />
        <Prose
          paragraphs={[
            "What people mean by GEO breaks into three things: whether an AI crawler can retrieve your page, whether your markup explains who you are, and whether your content is shaped so a specific answer can be lifted out of it. Crawldy measures all three, and reports them as AI readiness and AI citability.",
            "So this page is not a different product. It is the same measurement, explained for someone who arrived with a different word.",
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="What is checkable on your own site"
          lead="Everything here produces a finding with evidence: what we expected, what we found, and where."
        />
        <CardGrid
          cards={[
            {
              icon: "globe",
              title: "Retrieval",
              text: "Whether an AI agent is refused by a rule or a filter, and how much of the page exists before JavaScript runs.",
            },
            {
              icon: "list",
              title: "Understanding",
              text: "Structured data that says who you are, what you offer and how to reach you — and whether those pieces reference one another rather than sitting apart.",
            },
            {
              icon: "link",
              title: "Usability as a source",
              text: "Whether a page answers a question directly, states who wrote it, and makes claims that are actually present rather than implied.",
              href: "/ai-visibility",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="What is not checkable by reading your site"
          lead="This is the line worth being precise about, because most of the category's marketing crosses it."
        />
        <Definitions
          items={[
            {
              term: "Whether an assistant recommends you",
              detail:
                "That requires asking the assistant, repeatedly, across phrasings and over time. It is a real measurement and a genuinely different one — it observes an external system, not your website. Crawldy does it as Actual AI Presence, included with paid analyses, and its numbers are reported apart from your site audit score — never as a stand-in for it.",
            },
            {
              term: "Whether a specific model has your content",
              detail:
                "What a model absorbed during training is not observable from outside, and it does not change when you fix your site. What does change is whether a retrieval-based system can fetch and use your pages now.",
            },
            {
              term: "Rankings inside generated answers",
              detail:
                "There is no stable list to hold a position in. Answers are assembled per question, and the same query an hour later can cite different sources.",
            },
          ]}
        />
        <Prose
          paragraphs={[
            "External mention measurement exists as Actual AI Presence: defined prompts, repeated runs against the provider APIs, results reported as observations with denominators. It is described as what it is — querying other systems — and kept separate from anything measured on your site.",
          ]}
        />
        <More href="/methodology" label="How the measurable part is measured" />
      </Section>

      <Section>
        <Heading
          title="Where to start if you have done no GEO work"
          lead="In practice the order is almost always the same, because the first item makes the rest irrelevant when it is wrong."
        />
        <Definitions
          items={[
            {
              term: "1. Make sure the content arrives",
              detail:
                "Check that agents are not refused and that your text exists in the HTML before scripts run. Markup cannot help with content that was never received.",
            },
            {
              term: "2. Say who you are, in data",
              detail:
                "Organization markup and links to your profiles elsewhere. This is what lets a system connect a mention on your site to what it knows from other sources.",
            },
            {
              term: "3. Answer the question near the top",
              detail:
                "A page that states its answer before the preamble is a page a system can quote a paragraph from. This is content work, not markup, and it is the part most sites skip.",
            },
          ]}
        />
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/ai-visibility",
            label: "AI visibility",
            text: "The full picture: access, understanding, usability as a source.",
          },
          {
            href: "/methodology",
            label: "Methodology",
            text: "How findings, coverage and confidence fit together.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "geo-audit",
  title: "GEO audit — what generative engine optimisation can actually be measured",
  h1: "Generative engine optimisation, minus the parts nobody can measure",
  description:
    "What a GEO audit can check on your own site — retrieval, structured data, answerable content — and what it cannot, including whether assistants currently mention you.",
  navLabel: "GEO audit",
  Body,
};
