/**
 * seo-audit — de. Структура затвердженої пропозиції E2 (2026-09-05):
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
  const cta = ctaOf("de");
  return (
    <>
      <Hero
        eyebrow={"SEO-Audit"}
        title={"Können Suchmaschinen Ihre Website finden und verstehen?"}
        lead={"Dieser Teil der Prüfung beantwortet der Reihe nach drei Fragen: ob die Suche eine Seite erreicht, ob die Seite Signale gegen die Indexierung trägt und ob klar ist, worum es auf ihr geht."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Kann die Suche Ihre Seiten erreichen"} lead={"Wir prüfen robots.txt, interne Links, Seitentiefe, Serverantworten, HTTPS und Weiterleitungsketten. Der Bericht nennt die konkreten Adressen, die eine Suchmaschine womöglich nicht erreicht — mit dem Grund für jede."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. Gibt es Signale, die die Indexierung behindern"} lead={"Wir prüfen noindex, canonical, die Sitemap und Widersprüche zwischen diesen Signalen. Sie zeigen, ob es technische Anzeichen gibt, die die Indexierung behindern können. Ob eine Seite tatsächlich indexiert ist, stellt Crawldy nicht fest."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Ist klar, worum es auf der Seite geht"} lead={"Wir prüfen Seitentitel, Beschreibungen, H1, Textstruktur, Linktexte und Seiten mit zu wenig Inhalt. Zu jedem Problem zeigt der Bericht, auf welchen Seiten es gefunden wurde."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Was der Bericht liefert"} lead={"Unter jedem Befund zeigen wir, was wir erwartet haben, was wir tatsächlich gesehen haben und auf welchen Seiten es gefunden wurde. Die Probleme ordnen wir nach Priorität — unter Berücksichtigung von Schwere, erwartetem Effekt, Aufwand der Behebung und Bedeutung der Seite."} />
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

export const de: LocalizedPage = {
  slug: "seo-audit",
  title: "SEO-Audit — Crawling, Indexierung und Verständnis Ihrer Seiten",
  h1: "Können Suchmaschinen Ihre Website finden und verstehen?",
  description:
    "Drei Stufen der Suchsichtbarkeit in einem Bericht: ob Suchmaschinen Ihre Seiten erreichen, indexieren und verstehen können — mit Beleg zu jedem Befund.",
  navLabel: "SEO-Audit",
  Body,
};
