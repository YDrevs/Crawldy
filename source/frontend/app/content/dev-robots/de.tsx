/**
 * robots.txt — німецька довідкова сторінка.
 *
 * Одна з трьох, які німецькою виправдані окремою сторінкою. Решта тем
 * закриті на хабі: порожні діти заради симетрії URL гірші за один
 * сильний батько.
 *
 * Файл згенерований: `scratchpad/gen_dev_de.py`.
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
        eyebrow="robots.txt"
        title="Was robots.txt tatsächlich steuert"
        lead="Eine Textdatei an einer festen Adresse, fast vor allem anderen gelesen — und regelmäßig gebeten, zwei Aufgaben zu erfüllen, die sie nicht erfüllen kann."
        primary={{ href: "/result", label: "Website prüfen" }}
      />

      <Section>
        <Heading title="Wie es funktioniert" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Sie regelt das Abrufen, nicht das Indexieren",
                detail:
                  "Eine gesperrte URL kann trotzdem in Ergebnissen auftauchen, wenn genug externe Links auf sie zeigen: der Crawler befolgt die Regel und indexiert die Adresse ohne den Inhalt. Um eine Seite aus dem Index zu halten, muss sie abrufbar sein und mit einer noindex-Anweisung antworten.",
              },
              {
                term: "Regeln gelten je User Agent",
                detail:
                  "Gruppen werden über den spezifischsten passenden Agenten zugeordnet, und nur diese Gruppe wird verwendet. Ein Agent mit eigener Gruppe erbt nichts aus der Wildcard-Gruppe.",
              },
              {
                term: "Sie ist keine Zugriffskontrolle",
                detail:
                  "Sie ist eine Bitte, die sich gutartige Clients zu Herzen nehmen. Was nicht lesbar sein darf, braucht Authentifizierung und keine Zeile in einer Textdatei.",
              },
              {
                term: "Sitemap-Zeilen stehen für sich",
                detail:
                  "Eine Sitemap-Angabe gehört zu keiner User-Agent-Gruppe und darf überall in der Datei stehen.",
              },
            ]}
          />
        </div>
      </Section>

      <Section>
        <Heading
          title="Wo es meistens schiefgeht"
          lead="Jeder dieser Punkte ist etwas, das Crawldy auf echten Websites meldet — nichts Hypothetisches."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Eine Fehlerseite mit Status 200",
                detail:
                  "Der häufigste unsichtbare Fehler. Ihr Server beantwortet die Anfrage nach robots.txt mit einer gestalteten HTML-Fehlerseite und einem Erfolgscode; der Client parst HTML als Anweisungen, findet keine und fährt fort, als wäre alles erlaubt. Prüfen Sie Status und Content-Type, nicht nur, dass etwas zurückkam.",
              },
              {
                term: "Ressourcen sperren",
                detail:
                  "CSS oder JavaScript zu sperren verhindert, dass das Rendering Ihre Seite nachbildet. Der Crawler beurteilt dann eine Fassung, die niemand sieht.",
              },
              {
                term: "Staging-Regeln erreichen die Produktion",
                detail:
                  "Ein pauschales Disallow, das mit dem Deployment mitgereist ist. Von außen nicht von einer bewussten Entscheidung zu unterscheiden — deshalb meldet eine Prüfung es und bittet um Bestätigung, statt es einen Fehler zu nennen.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Passend dazu"
        links={[
          {
            href: "/de/entwickler/crawling",
            label: "Crawling",
            text: "Was nach einem erlaubten Abruf passiert.",
          },
          {
            href: "/de/entwickler/ki-crawler",
            label: "KI-Crawler",
            text: "Entscheidungen je Agent, die nicht eine Entscheidung sind.",
          },
          {
            href: "/de/technisches-seo-audit",
            label: "Technisches SEO-Audit",
            text: "All das gegen Ihre Website geprüft.",
          },
        ]}
      />
    </>
  );
}

export const de: LocalizedPage = {
  slug: "robots",
  title: "robots.txt — was sie steuert und der Fehler, den niemand sieht",
  h1: "Was robots.txt tatsächlich steuert",
  description:
    "Regeln je User Agent, der Unterschied zwischen Crawling und Indexierung, die Fehlerseite mit Status 200, und warum robots.txt ein Crawler-Signal ist und keine Zugriffskontrolle.",
  navLabel: "robots.txt",
  Body,
};
