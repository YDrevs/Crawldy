/**
 * ai-visibility — de. Структура другого проходу (журнал правок): без
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
  const cta = ctaOf("de");
  return (
    <>
      <Hero
        eyebrow={"KI-Sichtbarkeit"}
        title={"Sehen und erwähnen KI-Systeme Sie?"}
        lead={"Crawldy prüft, ob KI Ihre Seiten abrufen, die Informationen über Ihr Unternehmen verstehen und die Website als Quelle nutzen kann. Im vollständigen Bericht zeigt Actual AI Presence zusätzlich, ob ChatGPT, Claude, Perplexity und Gemini Ihre Marke nennen."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"Zugang für KI"} lead={"Wir prüfen, ob KI-Systeme Ihre Seiten laden und den Hauptinhalt abrufen können. Dabei berücksichtigen wir Einschränkungen für KI-Crawler, Serverantworten und die Abhängigkeit der Website von JavaScript."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Verständnis Ihres Unternehmens"} lead={"Wir prüfen, ob aus den Seiten klar wird, wer Sie sind, was Sie anbieten und wie man Sie erreicht. Dafür analysieren wir die Inhaltsstruktur, Unternehmensangaben, Kontakte und die passende Auszeichnung."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Eignung als Quelle"} lead={"Wir prüfen, ob die Website klare Antworten, ausreichenden Kontext, ausgewiesene Autorschaft und Aussagen enthält, die KI in einer Antwort korrekt verwenden kann."} />
          </div>
        </div>
      </Section>

      <Section>
        <Heading title={"Tatsächliche Präsenz in Antworten"} />
        <PresenceModels
          intro={"Für die Prüfung verwendet Crawldy die Modelle, die als am repräsentativsten für die aktuelle Nutzererfahrung der jeweiligen KI-Plattform ausgewählt wurden."}
          note={"Die Modelle der KI-Plattformen ändern sich, und verschiedene Modelle können Marken unterschiedlich nennen, Unternehmen unterschiedlich empfehlen und Quellen unterschiedlich verwenden. Ein Ergebnis von Actual AI Presence bezieht sich daher auf die für diese konkrete Prüfung angegebenen Modelle."}
        />
      </Section>

      <Section bordered={false}>
        <Heading title={"Was Sie im Bericht sehen"} />
        <Bullets
          items={[
            "Probleme, die KI daran hindern, Inhalte abzurufen oder zu verstehen",
            "die Seiten und Belege zu jeder Schlussfolgerung",
            "Markenerwähnungen und Links in den Antworten der Assistenten",
            "die anderen Domains, die Assistenten statt Ihrer genannt haben",
            "Prioritäten für die Behebung",
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

export const de: LocalizedPage = {
  slug: "ki-sichtbarkeit",
  title: "KI-Sichtbarkeit — ruft, versteht und erwähnt KI Ihre Website?",
  h1: "Sehen und erwähnen KI-Systeme Sie?",
  description:
    "Ob KI-Systeme Ihre Seiten abrufen, Ihr Unternehmen verstehen und die Website als Quelle nutzen können — und ob ChatGPT, Claude, Perplexity und Gemini Ihre Marke nennen.",
  navLabel: "KI-Sichtbarkeit",
  Body,
};
