/**
 * about — de. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { CardGrid, Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("de");
  return (
    <>
      {/* Прикладу звіту тут немає навмисно. Той, що стояв, показував
          сайт `example-shop.com` із балом 62, покриттям і критичною
          знахідкою — усе вигадане. Сторінка «Про нас» — це те місце,
          де читач вирішує, чи вірити нашим числам узагалі; вигадане
          число саме тут коштує найдорожче. Справжній зразок зʼявиться
          після розміщення: ним стане звіт Crawldy про самого себе. */}
      <Hero
        eyebrow={"ÜBER UNS"}
        title={"Wir helfen zu verstehen, wie Suche und KI Ihre Website sehen"}
        lead={"Crawldy ist ein Analysedienst für Websites, der Sichtbarkeit in der Suche, KI-Bereitschaft, den technischen Zustand der Website und tatsächliche Erwähnungen in KI-Assistenten in einem verständlichen Bericht vereint."}
      />

      <Section>
        <Heading title={"Warum Crawldy entstanden ist"} lead={"Crawldy macht aus den gefundenen Problemen einen verständlichen Plan. Im Bericht sind Umfang des Problems, Belege und Priorität der Korrektur zu sehen."} />
      </Section>

      <Section>
        <Heading title={"Unser Ziel"} lead={"Die Sichtbarkeit einer Website in Suche und KI verständlich und messbar zu machen. Wer eine Website betreibt, soll nicht nur technische Kennzahlen sehen, sondern konkrete Probleme, ihre Wirkung und die nächsten Schritte."} />
      </Section>

      <Section bordered={false}>
        <Heading title={"Für wen Crawldy gemacht ist"} />
        <CardGrid
          cards={[
            {
              title: "Website-Betreibern",
              text: "Um zu verstehen, was Kunden, Suchmaschinen und KI daran hindert, Ihre Website zu finden.",
            },
            {
              title: "Marketing-Teams",
              text: "Um Probleme mit Sichtbarkeit, Inhalten und Indexierung zu sehen und Prioritäten zu setzen.",
            },
            {
              title: "Webagenturen",
              text: "Um Kundenwebsites nach einer einheitlichen Methodik zu prüfen und einen verständlichen Bericht mit Belegen zu übergeben.",
            },
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
  slug: "ueber-uns",
  title: "Über Crawldy — Website-Analyse für Suche und KI",
  h1: "Wir helfen zu verstehen, wie Suche und KI Ihre Website sehen",
  description:
    "Crawldy vereint Sichtbarkeit in der Suche, KI-Bereitschaft, den technischen Zustand und tatsächliche KI-Erwähnungen in einem Bericht. Warum es entstanden ist und für wen.",
  navLabel: "Über uns",
  Body,
};
