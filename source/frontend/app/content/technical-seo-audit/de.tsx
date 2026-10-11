/**
 * technical-seo-audit — de. Структура затвердженої пропозиції E2
 * (2026-09-05): надзаголовок, H1 і одне речення підводки → пʼять блоків
 * (швидкість і стабільність; HTTPS, редиректи й базовий захист; відповідь
 * сервера проти відрендереного DOM — окремим розділом; форми й обробка
 * помилок; доступність і зручність) → докази й рекомендації із
 * застереженням → спільний нижній CTA.
 *
 * Слова обмежені тим, що вимірюється: порівнюється відрендерений DOM, а не
 * «те, що бачить відвідувач»; доказ дає розробнику точку, з якої почати,
 * а не знімає подальшу діагностику; це не пентест і не сертифікація.
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
        eyebrow={"Technisches Website-Audit"}
        title={"Was die Website technisch am korrekten Arbeiten hindert"}
        lead={"Dieser Teil der Prüfung vergleicht, was der Server zurückgibt, mit dem Ergebnis nach der Ausführung der Skripte und zeigt, wo beides nicht übereinstimmt."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Geschwindigkeit und Stabilität"} lead={"Wir prüfen die Antwortzeit des Servers, das Seitengewicht, ladeblockierende Ressourcen, Skripte von Drittanbietern und die Core Web Vitals, sofern Daten echter Nutzer vorliegen. Jede Zahl im Bericht trägt ihre Quelle: Felddaten oder Labormessung."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. HTTPS, Weiterleitungen und grundlegender Schutz"} lead={"Wir prüfen das Zertifikat, die Übergänge zwischen HTTP und HTTPS sowie zwischen der Version mit und ohne www, lange oder zyklische Weiterleitungsketten, Sicherheits-Header, Caching und ungeschützte Ressourcen auf geschützten Seiten. Das sind sichtbare Anzeichen, keine Schwachstellensuche."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Serverantwort gegen gerendertes DOM"} lead={"Wir vergleichen die HTML-Antwort des Servers mit dem DOM nach der Ausführung von JavaScript. So finden wir Inhalte, Links, Navigation oder strukturierte Daten, die nur in einer der beiden Fassungen der Seite vorhanden sind, und wir zeigen, in welcher."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"4. Formulare und Fehlerbehandlung"} lead={"Wir prüfen, mit welcher Methode Anfrageformulare Daten senden und ob sichtbare Anzeichen für einen Schutz vor automatisiertem Spam vorhanden sind. Außerdem prüfen wir, wie die Website auf nicht vorhandene Adressen antwortet. Eine Fehlerseite muss einen Fehlercode liefern, nicht die Antwort „alles in Ordnung“."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"5. Barrierefreiheit und Bedienbarkeit"} lead={"Wir prüfen auf typische Hindernisse für Menschen, die die Website anders nutzen: Kontrast, Beschriftung der Bedienelemente, Überschriftenstruktur, Zoomen auf dem Telefon und ob sich eine Telefonnummer antippen lässt. Das ist eine automatische Prüfung, keine WCAG-Zertifizierung."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Belege und Empfehlungen im Bericht"} lead={"Zu jedem Problem zeigt der Bericht die Seitenadresse, das erwartete Ergebnis, die tatsächliche Antwort und den technischen Beleg. Das gibt Entwicklern einen konkreten Ausgangspunkt."} />
        <p className="mt-4 max-w-measure text-sm text-muted">{"Dies ist eine automatische technische Prüfung — kein Penetrationstest, keine Schwachstellensuche und keine Zertifizierung der Barrierefreiheit."}</p>
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
  slug: "technisches-seo-audit",
  title: "Technisches Website-Audit — Server, HTTPS, JavaScript, Tempo",
  h1: "Was die Website technisch am korrekten Arbeiten hindert",
  description:
    "Konkrete technische Gründe, warum eine Website nicht korrekt arbeitet: Serverantworten, HTTPS und Weiterleitungen, gerenderter Inhalt, Tempo und Grundeinstellungen — mit Beleg zu jedem Befund.",
  navLabel: "Technisches Website-Audit",
  Body,
};
