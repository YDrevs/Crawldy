/**
 * Entwickler-Hub — німецька версія, і вона змістовніша за англійську.
 *
 * ## Чому хаб тут несе більше
 *
 * Німецькою окремі довідкові сторінки виправдані лише для трьох тем із
 * семи: `Crawling` (3 600/міс), доступ AI-краулерів і robots.txt.
 * Решта — рендеринг, індексованість, розмітка, скоринг — власного
 * попиту німецькою не має, а тема нікуди не дівається.
 *
 * Тому хаб не перелік посилань, як в англійській, а сам дає відповідь
 * по кожній темі: короткий, але справжній абзац. Порожні діти заради
 * симетрії URL були б гіршими за один сильний батько — і за нашими ж
 * правилами, і по суті.
 */

import {
  CardGrid,
  Definitions,
  Heading,
  Hero,
  More,
  Prose,
  Related,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        eyebrow="Für Entwickler"
        title="Wie Suchmaschinen und KI-Crawler eine Website tatsächlich lesen"
        lead="Notizen zur Mechanik: was ein Crawler bekommt, was er parsen kann und wo die beiden Publika auseinandergehen. Aus dem, was Crawldy auf echten Websites beobachtet, nicht aus dem, was Spezifikationen versprechen."
        primary={{ href: "/result", label: "Website prüfen" }}
      />

      <Section>
        <Heading
          title="Eine Anfrage, zwei sehr verschiedene Leser"
          lead="Beide holen dieselbe URL. Was danach passiert, ist nicht dasselbe — und fast jeder technische Befund einer Prüfung lebt in dieser Lücke."
        />
        <Prose
          paragraphs={[
            "Ein Suchcrawler stellt Ihre Seite zum Rendern in eine Warteschlange, führt JavaScript aus und indexiert, was der Browser erzeugt hat. Ein KI-Crawler tut davon möglicherweise nichts — viele holen das HTML, parsen es und ziehen weiter. Keines der beiden Verhalten ist allgemeingültig, und Anbieter ändern es ohne Ankündigung.",
            "Die praktische Frage lautet also nicht „funktioniert meine Website“, sondern „wie viel von ihr übersteht welchen Weg“.",
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Eigene Seiten"
          lead="Drei Themen sind ausführlich genug für eine eigene Seite."
        />
        <CardGrid
          cards={[
            {
              icon: "globe",
              title: "Crawling",
              text: "Wie ein Crawler Seiten findet, was ihn begrenzt, und warum eine Sitemap ein Hinweis ist und keine Anweisung.",
              href: "/de/entwickler/crawling",
            },
            {
              icon: "link",
              title: "KI-Crawler",
              text: "Welche Agenten für Antwortmaschinen holen, wie sie sich von Suche unterscheiden, und warum das Sperren des einen das andere nicht sperrt.",
              href: "/de/entwickler/ki-crawler",
            },
            {
              icon: "list",
              title: "robots.txt",
              text: "Was sie kann und was nicht, der Fehler mit Status 200 und HTML-Körper, und Regeln je User Agent.",
              href: "/de/entwickler/robots",
            },
          ]}
        />
      </Section>

      {/* Розділ, якого немає в англійській: чотири теми без окремої
          сторінки німецькою, але з повноцінною відповіддю тут. */}
      <Section>
        <Heading
          title="Kurz erklärt"
          lead="Diese vier Themen haben im Deutschen keine eigene Nachfrage, die eine eigene Seite trägt. Verschwinden sollen sie deswegen nicht."
        />
        <Definitions
          items={[
            {
              term: "JavaScript-Rendering",
              detail:
                "Von jeder Seite existieren zwei Fassungen: das HTML, das Ihr Server ausliefert, und der DOM, nachdem Skripte gelaufen sind. Suchmaschinen können rendern; viele KI-Crawler möglicherweise nicht. Prüfen lässt sich das, indem Sie die URL ohne Browser abrufen und den sichtbaren Text vergleichen. Typisch fehlen in der statischen Fassung drei Dinge: Fließtext nach Hydration, per Skript eingefügtes JSON-LD und Navigation, die das Framework zeichnet.",
            },
            {
              term: "Indexierbarkeit",
              detail:
                "Erreichbar heißt nicht indexiert. Vier Wege führen daran vorbei: eine noindex-Anweisung, die Sie vielleicht nicht gemeint haben; ein Canonical, das Sitemap oder Weiterleitung widerspricht; Statuscodes, die etwas anderes sagen als gemeint — eine Fehlerseite mit 200 erzeugt eine indexierbare Seite ohne Inhalt; und einfaches HTTP, das jedes andere Signal auf der Seite untergräbt.",
            },
            {
              term: "Strukturierte Daten",
              detail:
                "JSON-LD im HTML, nicht per Skript nachgeliefert. Organization ist der Anker, sameAs verbindet Sie mit dem, was anderswo schon bekannt ist, und stabile Bezeichner machen aus einzelnen Blöcken einen Graphen statt mehrerer unverbundener Dinge. Markup, das dem Sichtbaren widerspricht, ist schlechter als keines — FAQ-Auszeichnung ohne sichtbare FAQ sammelt Abstrafungen statt Sichtbarkeit.",
            },
            {
              term: "Bewertung",
              detail:
                "Strafpunkte sind Gewicht mal Schweregrad; zwei Obergrenzen begrenzen, was ein einzelnes Problem kosten kann; die Skala ist hyperbolisch und erreicht nie null. Eine nicht messbare Dimension verlässt die Rechnung, statt null zu werden. Die genauen Gewichte stehen in der Methodik.",
            },
          ]}
        />
        <More href="/de/methodik" label="Bewertung ausführlich in der Methodik" />
      </Section>

      <Section>
        <Heading
          title="Unser eigener Crawler"
          lead="Wenn Sie in Ihre Logs schauen: das sind wir — und das erlauben wir auf unserer eigenen Website."
        />
        <Prose
          paragraphs={[
            "Unser Crawler weist sich im User-Agent aus und befolgt robots.txt. Er folgt Weiterleitungen bis zu einer kleinen Grenze, begrenzt die Antwortgröße und sendet nie etwas. Wurde er abgewiesen, sagt Ihr Bericht das, statt Inhalte zu erraten, die er nie bekommen hat.",
            "Auf crawldy.ai erlauben wir Such- und Discovery-Crawler, erlauben KI-Agenten, die zum Beantworten einer Frage holen, und weisen Agenten ab, die Inhalte für Modelltraining sammeln. Google-Extended behandeln wir als eigene Entscheidung und nicht als Teil der Suche — es zu sperren kostet in der Google-Suche nichts, und beides zu verwechseln ist ein verbreiteter und teurer Fehler.",
          ]}
        />
      </Section>

      <Related
        title="Passend dazu"
        links={[
          {
            href: "/de/methodik",
            label: "Methodik",
            text: "Wie Messung, Abdeckung und Sicherheit zusammenspielen.",
          },
          {
            href: "/de/technisches-seo-audit",
            label: "Technisches SEO-Audit",
            text: "Dieselbe Mechanik, gegen Ihre Website geprüft.",
          },
          {
            href: "/de/ki-sichtbarkeit",
            label: "KI-Sichtbarkeit",
            text: "Zugriff, Verständnis und Verwendbarkeit als Quelle.",
          },
        ]}
      />
    </>
  );
}

export const de: LocalizedPage = {
  slug: "entwickler",
  title: "Für Entwickler — wie Suchmaschinen und KI-Crawler Websites lesen",
  h1: "Wie Suchmaschinen und KI-Crawler eine Website tatsächlich lesen",
  description:
    "Mechanik für Entwickler: Crawling, robots.txt, KI-Crawler-Zugriff, JavaScript-Rendering, Indexierbarkeit, strukturierte Daten und Bewertung — aus dem, was Crawldy auf echten Websites beobachtet.",
  navLabel: "Entwickler",
  Body,
};
