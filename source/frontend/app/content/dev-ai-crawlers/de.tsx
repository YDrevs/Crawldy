/**
 * KI-Crawler — німецька довідкова сторінка.
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
        eyebrow="KI-Crawler"
        title="KI-Crawler sind kein Publikum und keine einzelne Entscheidung"
        lead="Drei verschiedene Dinge treffen bei Ihrem Server ein und heißen alle KI-Crawler. Sie als eine Politik zu behandeln ist der häufigste Weg, Sichtbarkeit zu verlieren, die man behalten wollte."
        primary={{ href: "/result", label: "Website prüfen" }}
      />

      <Section>
        <Heading title="Wie es funktioniert" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Abruf für eine Antwort",
                detail:
                  "Ein Agent holt Ihre Seite, weil jemand eine Frage gestellt hat, die er beantworten will — oft mit Quellenangabe. Das ist der Suche am nächsten: der Verweis und die Nennung sind der Grund, es zu erlauben.",
              },
              {
                term: "Sammeln für Training",
                detail:
                  "Ein Agent sammelt Inhalte in einen Datensatz. Keine Frage, keine Nennung, kein Besuch. Es zu erlauben ist eine legitime Entscheidung — aber eine andere, und sie verdient es, bewusst getroffen zu werden.",
              },
              {
                term: "Suchcrawler, die auch KI-Oberflächen speisen",
                detail:
                  "Derselbe Crawler, der für die Suche indexiert, kann im selben Produkt auch eine KI-Funktion versorgen. Ihn zu sperren kostet Sie die Suche.",
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
                term: "Google-Extended für eine Such-Einstellung halten",
                detail:
                  "Ist es nicht. Es regelt die Nutzung Ihrer Inhalte in Googles KI-Produkten; auf Googlebot, Indexierung und Ranking hat es keinen Einfluss. Websites sperren Googlebot in der Annahme, sich gegen KI zu entscheiden, und verlieren stattdessen die Suche.",
              },
              {
                term: "Annehmen, dass JavaScript ausgeführt wird",
                detail:
                  "Viele Agenten holen HTML und parsen es, ohne Skripte auszuführen. Erscheint Ihr Inhalt erst nach dem Rendering, fehlt er ihnen — und kein Markup repariert Inhalt, der nie angekommen ist.",
              },
              {
                term: "Annehmen, dass eine Regel wahr bleibt",
                detail:
                  "User-Agent-Kennungen ändern sich, neue Agenten kommen dazu, und das Verhalten ist uneinheitlich dokumentiert. Eine einmal geschriebene und nie überprüfte Politik bedeutet irgendwann nicht mehr, was sie bedeutete.",
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
            text: "Wie man Regeln je Agent ausdrückt.",
          },
          {
            href: "/de/ki-sichtbarkeit",
            label: "KI-Sichtbarkeit",
            text: "Was wir auf Ihrer Website messen — und was nicht.",
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
  slug: "ki-crawler",
  title: "KI-Crawler — Antwortmaschinen, Training und der Unterschied",
  h1: "KI-Crawler sind kein Publikum und keine einzelne Entscheidung",
  description:
    "Welche Agenten für Antwortmaschinen abrufen, wie sie sich von Suchcrawlern und von Trainingssammlern unterscheiden, und warum eine Regel nicht alle drei Entscheidungen ausdrücken kann.",
  navLabel: "KI-Crawler",
  Body,
};
