/**
 * Startseite — Deutsch. Aufbau und Aussagegrenzen wie in en.tsx.
 * Ansprache — «Sie»: durchgängig auf allen deutschen Seiten.
 */

import { HeroAuditForm } from "../../components/HeroAuditForm";
import { ScorePreview } from "../../components/ScorePreview";
import {
  CardGrid,
  Heading,
  Hero,
  More,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        title="Sehen Suchmaschinen und KI Ihre Website wirklich?"
        action={
          <HeroAuditForm
            lang="de"
            placeholder="ihre-website.de"
            cta="Kostenlose Prüfung starten"
            invalid="Geben Sie eine Website-Adresse ein, z. B. example.com."
          />
        }
        aside={<ScorePreview locale="de" />}
      />

      <Section>
        <Heading title="Eine Website-Analyse beantwortet die drei Schlüsselfragen zu Ihrer Sichtbarkeit in Suche und KI." />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Findet die Suche Sie?",
              text: "Wir prüfen, ob Google und andere Suchmaschinen Ihre Seiten finden und lesen können.",
              href: "/de/seo-audit",
            },
            {
              icon: "globe",
              title: "Versteht KI Ihre Website?",
              text: "Wir prüfen, ob KI Ihre Website lesen und die Informationen über Ihr Unternehmen verstehen kann.",
              href: "/de/ki-sichtbarkeit",
            },
            {
              icon: "link",
              title: "Erwähnt KI Ihre Marke?",
              text: "Wir prüfen, ob ChatGPT, Claude, Perplexity und Gemini Ihre Marke in Antworten zu Ihrer Nische nennen.",
              href: "/de/ki-sichtbarkeit",
            },
          ]}
        />
        <More href="/de/website-check" label="Alle Bestandteile der Prüfung" />
      </Section>

      <Section bordered={false}>
        <Heading
          title="Eine transparente Website-Bewertung"
          lead="Sie sehen, welche Seiten geprüft wurden, was gemessen werden konnte und worauf der Gesamtwert beruht."
        />
        <More href="/de/methodik" label="Wie die Messung funktioniert" />
      </Section>
    </>
  );
}

export const de: LocalizedPage = {
  slug: "",
  title: "Crawldy — sehen Suchmaschinen und KI Ihre Website?",
  h1: "Sehen Suchmaschinen und KI Ihre Website wirklich?",
  description:
    "Crawldy zeigt, was Ihre Website daran hindert, in Suche und KI sichtbar zu sein — und was zuerst zu beheben ist.",
  navLabel: "Start",
  Body,
};
