/**
 * JavaScript rendering — довідкова сторінка для розробника.
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
        eyebrow="JavaScript rendering"
        title="What your page contains before any script runs"
        lead="Two versions of every page exist: the HTML your server sends, and what the DOM looks like after scripts finish. Different readers see different ones."
        primary={{ href: "/result", label: "Audit a site" }}
      />

      <Section>
        <Heading title="How it works" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Search engines can render",
                detail:
                  "Rendering is queued and costs resources, so it can lag, but the rendered version is generally what search judges. This is why client-side sites can rank at all.",
              },
              {
                term: "Many AI crawlers may not",
                detail:
                  "A fetch-and-parse client sees only the first version. If your text, headings and structured data are injected by scripts, none of it exists for that reader.",
              },
              {
                term: "The gap is measurable",
                detail:
                  "Fetch the URL without a browser and compare the visible text against what you see on screen. Crawldy does this on every page and reports the difference as its own finding, because it matters to one audience and not the other.",
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
                term: "An empty shell with a loading state",
                detail:
                  "The static HTML contains a container and a spinner. For a rendering client this is invisible; for everyone else it is the whole page.",
              },
              {
                term: "Structured data added by script",
                detail:
                  "Markup injected after load does not exist for clients that never run the script — precisely the clients most likely to need it.",
              },
              {
                term: "Calls to action drawn by the framework",
                detail:
                  "Buttons and links that only exist after hydration are absent from the static version too, which changes what a parser concludes the page is for.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Related"
        links={[
          {
            href: "/developers/ai-crawlers",
            label: "AI crawlers",
            text: "Who never sees the rendered version.",
          },
          {
            href: "/developers/structured-data",
            label: "Structured data",
            text: "Markup that has to be in the HTML.",
          },
          {
            href: "/seo-audit",
            label: "SEO audit",
            text: "How the gap is reported for search.",
          },
        ]}
      />
    </>
  );
}

export const en: LocalizedPage = {
  slug: "javascript-rendering",
  title: "JavaScript rendering — what exists before scripts run",
  h1: "What your page contains before any script runs",
  description:
    "How to see the version of your page a non-rendering client receives, why search and AI crawlers differ here, and which parts of a page most often disappear.",
  navLabel: "JavaScript rendering",
  Body,
};
