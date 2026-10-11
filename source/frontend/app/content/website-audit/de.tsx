/**
 * Was wir prüfen — Deutsch. Struktur wie in en.tsx (журнал правок,
 * екран 02): Einstieg → sechs Richtungen (nicht klickbare Karten) →
 * wie die Bewertung entsteht → was zuerst zu beheben ist → Footer.
 */

import {
  CardGrid,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("de");
  return (
    <>
      <Hero
        eyebrow="Website-Check"
        title="Website-Analyse für Suche und KI"
        lead="Crawldy prüft Ihre Website in sechs Dimensionen und zeigt, was zuerst behoben werden sollte. Zu jedem Problem enthält der Bericht die Belege und die betroffenen Seiten."
      />

      <Section>
        <Heading
          title="Die sechs Prüfrichtungen"
          lead="Crawldy prüft die Sichtbarkeit Ihrer Website in Suche und KI, ihre Geschwindigkeit, grundlegende Sicherheit und Barrierefreiheit."
        />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Sichtbarkeit in der Suche",
              text: "Wir prüfen, ob Suchmaschinen Ihre Seiten finden und lesen können, ob es technische Signale gibt, die die Indexierung behindern können, und ob Struktur und Links der Website Probleme haben.",
            },
            {
              icon: "clock",
              title: "Tempo & Bedienung",
              text: "Wir prüfen, wie schnell Seiten laden, wie der Server antwortet und was die Website verlangsamen kann. Liegen Daten echter Nutzer vor, beziehen wir sie ein.",
            },
            {
              icon: "globe",
              title: "KI-Bereitschaft",
              text: "Wir prüfen, ob KI Ihr Unternehmen, seine Seiten, Kontakte und andere wichtige Informationen korrekt erkennen kann.",
            },
            {
              icon: "link",
              title: "Verwendbarkeit als Quelle",
              text: "Wir prüfen, ob die Website klare Antworten, ausgewiesene Autorschaft und genug Kontext bietet, damit KI sie als Quelle nutzen kann.",
            },
            {
              icon: "alert",
              title: "Sicherheitsgrundlagen",
              text: "Wir prüfen HTTPS, Sicherheitseinstellungen, Formularschutz und die korrekte Behandlung technischer Fehler. Dies ist keine Schwachstellensuche.",
            },
            {
              icon: "user",
              title: "Barrierefreiheit",
              text: "Wir prüfen auf typische Probleme, die Menschen an der Nutzung der Website hindern können. Dies ist eine automatische Prüfung, keine WCAG-Zertifizierung.",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Wie die Website-Bewertung entsteht"
          lead="Das Ergebnis hängt nicht nur von den gefundenen Problemen ab, sondern auch davon, wie viel der Website geprüft werden konnte. Deshalb zeigt Crawldy die Abdeckung neben dem Wert."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Abdeckung sofort sichtbar",
                detail:
                  "Wir zeigen, wie viele Seiten gefunden, geladen und geprüft wurden — und auf wie viele kein Zugriff möglich war.",
              },
              {
                term: "Nichtgemessenes senkt den Wert nicht",
                detail:
                  "Der Wert wird nur für die messbaren Richtungen berechnet. Fehlen Daten, zeigt Crawldy das offen an, statt eine Null zu setzen.",
              },
              {
                term: "Zu wenig Daten — kein Wert",
                detail:
                  "Wurde ein zu kleiner Teil der Website geprüft, zeigt Crawldy keinen unzuverlässigen Gesamtwert. Verfügbare Befunde bleiben als Beobachtungen im Bericht.",
              },
              {
                term: "Jede Schlussfolgerung ist nachprüfbar",
                detail:
                  "Zu jedem Problem zeigen wir, was wir erwartet haben, was wir gefunden haben und auf welchen Seiten. So lässt sich das Ergebnis prüfen und schneller beheben.",
              },
            ]}
          />
        </div>
      </Section>

      <Section bordered={false}>
        <Heading
          title="Was zuerst zu beheben ist"
          lead="Crawldy ordnet Probleme nach Priorität — nach Schwere, erwartetem Effekt, Aufwand der Behebung und Bedeutung der Seite. Sie sehen sofort, womit Sie anfangen sollten."
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
  slug: "website-check",
  title: "Website Check: Was auf Ihrer Website nicht stimmt — mit Belegen",
  h1: "Website-Analyse für Suche und KI",
  description:
    "Website prüfen lassen: ein Bericht über Sichtbarkeit in der Suche, KI-Bereitschaft, Tempo, Sicherheitsgrundlagen und Barrierefreiheit — mit Abdeckung und Beleg zu jedem Befund.",
  navLabel: "Was wir prüfen",
  Body,
};
