/**
 * about — en. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { CardGrid, Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("en");
  return (
    <>
      {/* Прикладу звіту тут немає навмисно. Той, що стояв, показував
          сайт `example-shop.com` із балом 62, покриттям і критичною
          знахідкою — усе вигадане. Сторінка «Про нас» — це те місце,
          де читач вирішує, чи вірити нашим числам узагалі; вигадане
          число саме тут коштує найдорожче. Справжній зразок зʼявиться
          після розміщення: ним стане звіт Crawldy про самого себе. */}
      <Hero
        eyebrow={"ABOUT US"}
        title={"We help you understand how search and AI see your site"}
        lead={"Crawldy is a website analysis service that brings search visibility, AI readiness, the technical state of the site and actual mentions in AI assistants together in one clear report."}
      />

      <Section>
        <Heading title={"Why Crawldy was built"} lead={"Crawldy turns the problems it finds into a clear plan. The report shows the scale of a problem, the evidence and the priority of the fix."} />
      </Section>

      <Section>
        <Heading title={"Our goal"} lead={"To make a site's visibility in search and AI understandable and measurable. A site owner should see not just technical metrics but specific problems, their impact and the next steps."} />
      </Section>

      <Section bordered={false}>
        <Heading title={"Who Crawldy is for"} />
        <CardGrid
          cards={[
            {
              title: "Site owners",
              text: "To understand what stops customers, search engines and AI from finding your site.",
            },
            {
              title: "Marketers",
              text: "To see visibility, content and indexing problems and set work priorities.",
            },
            {
              title: "Web agencies",
              text: "To check client sites with a single method and hand over a clear report with evidence.",
            },
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
  slug: "about",
  title: "About Crawldy — website analysis for search and AI",
  h1: "We help you understand how search and AI see your site",
  description:
    "Crawldy brings search visibility, AI readiness, the technical state of a site and actual AI mentions together in one clear report. Why it was built and who it is for.",
  navLabel: "About",
  Body,
};
