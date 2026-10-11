/**
 * Crawling — німецька довідкова сторінка.
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
        eyebrow="Crawling"
        title="Wie ein Crawler entscheidet, was er holt — und was ihn stoppt"
        lead="Discovery ist ein Graphenlauf mit Budget. Sitemaps, Prioritäten und Crawl-Rate verändern diesen Lauf, sie ersetzen ihn nicht."
        primary={{ href: "/result", label: "Website prüfen" }}
      />

      <Section>
        <Heading title="Wie es funktioniert" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Links sind die eigentliche Karte",
                detail:
                  "Ein Crawler beginnt irgendwo und folgt dem, was er findet. Eine Seite, auf die nichts verlinkt, ist nur erreichbar, wenn etwas anderes dem Crawler sagt, dass es sie gibt — dafür ist eine Sitemap da, und deshalb verhält sich eine verwaiste Seite in der Sitemap trotzdem anders als eine verlinkte.",
              },
              {
                term: "Eine Sitemap ist ein Hinweis",
                detail:
                  "Enthalten zu sein garantiert keinen Abruf, und zu fehlen verhindert keinen. Änderungsdaten nützen nur, wenn sie etwas bedeuten: eine Datei, in der jeder Eintrag den heutigen Tag behauptet, trägt keine Information.",
              },
              {
                term: "Budgets sind real und endlich",
                detail:
                  "Niemand liest eine große Website bei jedem Durchgang vollständig. Gelesen wird eine Stichprobe, und welche, macht enorm viel aus — der Anfang einer Sitemap ist üblicherweise das, was das CMS zuerst geschrieben hat, in einem Shop also Tausende Produkt-URLs und keine der Seiten, die das Geschäft erklären.",
              },
              {
                term: "Tiefe kostet Auffindbarkeit",
                detail:
                  "Seiten viele Klicks vom Einstieg entfernt werden später und seltener geholt. Das ist keine Ranking-Regel, sondern Arithmetik: ein Lauf mit Budget erreicht Nahes zuerst.",
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
                term: "Facettierte URLs fressen das Budget",
                detail:
                  "Filter- und Sortierparameter vervielfachen eine Seite zu Hunderten. Von außen sehen sie aus wie eigenständige URLs mit fast gleichem Inhalt, und der Crawler verbraucht sein Budget mit dem Nachweis, dass sie dasselbe sind.",
              },
              {
                term: "Langsame Antworten sehen aus wie Abweisung",
                detail:
                  "Ein Crawler mit Zeitlimit behandelt eine langsame Seite wie eine nicht verfügbare. Die Antwortzeit des Servers ist nicht nur eine Tempo-Kennzahl — ab einem Punkt wird sie zu einem Auffindbarkeitsproblem.",
              },
              {
                term: "Weiterleitungsketten",
                detail:
                  "Jeder Sprung kostet eine Anfrage, und manche Clients geben vor dem Ende auf. Eine Kette aus drei Sprüngen, die in einer 404 endet, ist im Browser unsichtbar — dort sieht sie aus wie ein gewöhnlicher toter Link.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="Passend dazu"
        links={[
          {
            href: "/de/entwickler/robots",
            label: "robots.txt",
            text: "Was einen Abruf verhindern kann und was nicht.",
          },
          {
            href: "/de/technisches-seo-audit",
            label: "Technisches SEO-Audit",
            text: "Dieselbe Mechanik, gegen Ihre Website geprüft.",
          },
          {
            href: "/de/entwickler",
            label: "Für Entwickler",
            text: "Die übrigen technischen Notizen.",
          },
        ]}
      />
    </>
  );
}

export const de: LocalizedPage = {
  slug: "crawling",
  title: "Crawling — wie Crawler Ihre Seiten finden und abrufen",
  h1: "Wie ein Crawler entscheidet, was er holt — und was ihn stoppt",
  description:
    "Wie Discovery funktioniert, warum eine Sitemap ein Hinweis und keine Anweisung ist, was ein Seitenbudget bei großen Websites bedeutet, und wie ein Crawl still endet.",
  navLabel: "Crawling",
  Body,
};
