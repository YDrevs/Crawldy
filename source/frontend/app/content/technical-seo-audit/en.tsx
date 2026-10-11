/**
 * technical-seo-audit — en. Структура затвердженої пропозиції E2
 * (2026-09-05): надзаголовок, H1 і одне речення підводки → пʼять блоків
 * (швидкість і стабільність; HTTPS, редиректи й базовий захист; відповідь
 * сервера проти відрендереного DOM — окремим розділом; форми й обробка
 * помилок; доступність і зручність) → докази й рекомендації із
 * застереженням → спільний нижній CTA.
 *
 * Слова обмежені тим, що вимірюється: порівнюється відрендерений DOM, а не
 * «те, що бачить відвідувач»; доказ дає розробнику точку, з якої почати,
 * а не знімає подальшу діагностику; це не пентест і не сертифікація.
 */

import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("en");
  return (
    <>
      <Hero
        eyebrow={"Technical site audit"}
        title={"What technically stops the site from working correctly"}
        lead={"This part of the check compares what the server returns with the result after scripts run, and shows where the two do not match."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Speed and stability"} lead={"We check server response time, page weight, resources that block loading, third-party scripts and Core Web Vitals when real-user data is available. Every number in the report carries its source: field data or a lab measurement."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. HTTPS, redirects and basic protection"} lead={"We check the certificate, the transitions between HTTP and HTTPS and between the www and non-www versions, long or looping redirect chains, security headers, caching and unprotected resources on protected pages. These are visible signs, not a vulnerability scan."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Server response versus rendered DOM"} lead={"We compare the server's HTML response with the DOM after JavaScript runs. That reveals content, links, navigation or structured data present in only one of the two versions of the page, and we show which one."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"4. Forms and error handling"} lead={"We check which method lead forms use to send data and whether visible signs of protection against automated spam are present. We also check how the site answers addresses that do not exist. An error page must return an error code, not an \"everything is fine\" response."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"5. Accessibility and usability"} lead={"We check for common obstacles for people who use the site differently: contrast, labels on controls, heading structure, zooming on a phone and whether a phone number can be tapped. This is an automated check, not a WCAG certification."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Evidence and recommendations in the report"} lead={"For every problem the report shows the page address, the expected result, the actual response and the technical evidence. That gives a developer a concrete starting point."} />
        <p className="mt-4 max-w-measure text-sm text-muted">{"This is an automated technical check, not a penetration test, a vulnerability scan or an accessibility certification."}</p>
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
  slug: "technical-seo-audit",
  title: "Technical site audit — server, HTTPS, JavaScript, speed",
  h1: "What technically stops the site from working correctly",
  description:
    "Concrete technical reasons a site does not work correctly: server responses, HTTPS and redirects, rendered content, speed and basic settings — with evidence for each finding.",
  navLabel: "Technical site audit",
  Body,
};
