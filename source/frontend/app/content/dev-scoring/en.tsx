/**
 * Scoring — довідкова сторінка для розробника.
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
        eyebrow="Scoring"
        title="How findings become a number"
        lead="Stated as mechanics rather than principles. The reasoning behind each choice is on the methodology page; this is what the arithmetic does."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Penalty is weight times severity",
                detail:
                  "Each finding carries a weight; each severity level a multiplier. Their product is the penalty a finding contributes to its dimension.",
              },
              {
                term: "Two ceilings per issue",
                detail:
                  "The first caps repetition relative to the finding itself, so one problem on twenty pages cannot zero a dimension. The second caps any single issue share of the dimension. A single occurrence always counts in full — the ceilings restrain repetition, not severity.",
              },
              {
                term: "The scale is hyperbolic",
                detail:
                  "A dimension score is derived from its penalty through a curve that is monotonic and never reaches zero. A linear scale with clamping produced sites stuck at zero that showed no movement after fixing half their problems.",
              },
              {
                term: "Dimensions are weighted, then combined",
                detail:
                  "Search visibility and speed carry the most; security basics and accessibility the least. Exact figures are published on the methodology page.",
              },
              {
                term: "Excluded is not zero",
                detail:
                  "A dimension that could not be measured leaves the calculation entirely and the remaining weights are redistributed. If too little was measured, there is no overall score.",
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
                term: "Adding up the point gains",
                detail:
                  "Each gain is measured independently against the same starting score. The ceilings and the curve make the combined effect non-linear, so a sum is always too high — which is why no total is printed.",
              },
              {
                term: "Comparing two audits across a version change",
                detail:
                  "Every audit records the detector and scoring versions that produced it. When either changed, the difference is explained by both the site and by us, and the report says so.",
              },
              {
                term: "Reading a low score as a ranking prediction",
                detail:
                  "It measures what machines can access, parse and use. That correlates with visibility; it is not a forecast of position.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/methodology",
            label: "Methodology",
            text: "Why the rules are what they are.",
          },
          {
            href: "/website-audit",
            label: "Website audit",
            text: "The report these numbers appear in.",
          },
          {
            href: "/developers",
            label: "Developer reference",
            text: "The rest of the technical notes.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "scoring",
  title: "Scoring — how findings become a number",
  h1: "How findings become a number",
  description:
    "The mechanics: weights per dimension, severity multipliers, two ceilings per issue, a hyperbolic scale, and why excluded dimensions are not zeros.",
  navLabel: "Scoring",
  Body,
};
