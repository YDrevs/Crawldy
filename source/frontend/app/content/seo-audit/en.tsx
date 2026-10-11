/**
 * seo-audit — en. Структура затвердженої пропозиції E2 (2026-09-05):
 * надзаголовок, H1 і одне речення підводки → три етапи, кожен — питання
 * і два речення (що перевіряємо / що покаже звіт) → «Що дає звіт» двома
 * реченнями → спільний нижній CTA. Три етапи більше не називаються тричі.
 *
 * Розведено те, що спостерігається: доступність для обходу й сигнали
 * індексованості. Фактичну індексацію Crawldy не бачить — сторінка каже
 * це прямо й не називає виключену сторінку «випадково» виключеною:
 * сигнал ми читаємо, намір — ні.
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
        eyebrow={"SEO audit"}
        title={"Can search engines find and understand your site?"}
        lead={"This part of the check answers three questions in order: whether search can reach a page, whether the page carries signals against indexing, and whether it is clear what the page is about."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Can search reach your pages"} lead={"We check robots.txt, internal links, page depth, server responses, HTTPS and redirect chains. The report lists the exact addresses a search engine may not reach, with the reason for each."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. Are there signals that hinder indexing"} lead={"We check noindex, canonical, the sitemap and contradictions between these signals. They show whether there are technical signs that may hinder indexing. Whether a page is actually indexed, Crawldy does not determine."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Is it clear what the page is about"} lead={"We check page titles, descriptions, H1, text structure, link texts and pages with too little content. For every problem the report shows which pages it was found on."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"What the report gives you"} lead={"Under every finding we show what we expected to see, what we actually saw and on which pages it was found. We order problems by priority, taking into account severity, expected effect, fix effort and how important the page is."} />
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
  slug: "seo-audit",
  title: "SEO audit — crawling, indexing and understanding your pages",
  h1: "Can search engines find and understand your site?",
  description:
    "Three stages of search visibility in one report: whether search engines can reach your pages, index them and understand what they are about — with evidence for every finding.",
  navLabel: "SEO audit",
  Body,
};
