/**
 * Methodik — Deutsch. Aufbau nach Eigentümer-Entscheidung (Bildschirm 06):
 * Abdeckung → geprüfte Daten → Belege → Bewertung → Prioritäten, dazu
 * die kompakten «Exakten Rechenregeln» aus dem Scoring-Schnappschuss.
 */

import { ScoringRules } from "../../components/ScoringRules";
import { Heading, Hero, Prose, Section } from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("de");
  return (
    <>
      <Hero
        eyebrow="Methodik"
        title={"Wie Crawldy zu den Prüfergebnissen kommt"}
        lead={"Crawldy zieht Schlüsse nur aus dem, was tatsächlich geprüft werden konnte. Zu jedem gefundenen Problem zeigt der Bericht die Belege, den Kontext und die Logik seiner Priorität."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title="Zuerst bestimmen wir die Abdeckung" />
            <Prose
              paragraphs={[
                "Crawldy findet die Seiten der Website und prüft, welche davon geladen und analysiert werden konnten. Der Bericht zeigt die Zahl der gefundenen, geprüften und unerreichbaren Seiten.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Nur geprüfte Daten zählen" />
            <Prose
              paragraphs={[
                "Konnte ein Teil der Website oder ein einzelner Messwert nicht geprüft werden, setzt Crawldy dafür keine Null und erfindet kein Ergebnis. Solche Daten bleiben außerhalb der Berechnung. Reicht die Abdeckung nicht, wird kein Gesamtwert angezeigt.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Jedes Problem wird belegt" />
            <Prose
              paragraphs={[
                "Zu jedem Befund zeigt der Bericht, was geprüft wurde, was gefunden wurde und auf welchen Seiten. So lässt sich die Schlussfolgerung prüfen und verstehen, was genau zu beheben ist.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Die Bewertung entsteht" />
            <Prose
              paragraphs={[
                "Probleme wirken unterschiedlich auf das Ergebnis. Schwere Verstöße wiegen mehr als geringe. Wiederholt sich ein Problem auf vielen Seiten, wird das berücksichtigt — sein Einfluss wird aber nicht unbegrenzt vervielfacht.",
                "Der Gesamtwert entsteht nur aus den Richtungen mit ausreichend Daten.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Was zuerst zu beheben ist" />
            <Prose
              paragraphs={[
                "Crawldy berücksichtigt die Schwere des Problems, das erwartete Ergebnis, den Aufwand der Behebung und die Bedeutung der Seite. So zeigt der Bericht sofort, womit Sie beginnen sollten.",
              ]}
            />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title="Exakte Rechenregeln" />
        <ScoringRules
          locale="de"
          strings={{
            caption: "Bewertungsregeln",
            weightsTitle: "Gewichte der Richtungen",
            severityTitle: "Schweregrad-Multiplikatoren",
            limitsTitle: "Begrenzungen",
            modules: {
              seo: "Sichtbarkeit in der Suche",
              performance: "Tempo & Bedienung",
              ai_ready: "KI-Bereitschaft",
              tech: "Sicherheitsgrundlagen",
              llm_visibility: "Verwendbarkeit als Quelle",
              accessibility: "Barrierefreiheit",
            },
            severities: {
              critical: "Kritisch",
              high: "Hoch",
              medium: "Mittel",
              low: "Niedrig",
              info: "Hinweis",
            },
            minCoverageLabel: "Mindesttext für die Inhaltsbewertung",
            minCoverageValue: "{n} Wörter auf der gesamten Website",
            repetitionLabel: "Wiederholung eines Problems",
            repetitionValue: "höchstens ×{n} eines einzelnen Befunds",
            shareLabel: "Einfluss eines Problems auf eine Richtung",
            shareValue: "höchstens {p} der Halbskala der Richtung",
          }}
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
  slug: "methodik",
  title: "Methodik — wie Crawldy zu den Prüfergebnissen kommt",
  h1: "Wie Crawldy zu den Prüfergebnissen kommt",
  description:
    "Abdeckung, geprüfte Daten, Belege, Bewertung und Prioritäten: wie Crawldy eine Website misst — mit den exakten Rechenregeln.",
  navLabel: "Methodik",
  Body,
};
