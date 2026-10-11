/**
 * seo-audit — es. Структура затвердженої пропозиції E2 (2026-09-05):
 * надзаголовок, H1 і одне речення підводки → три етапи, кожен — питання
 * і два речення (що перевіряємо / що покаже звіт) → «Що дає звіт» двома
 * реченнями → спільний нижній CTA. Три етапи більше не називаються тричі.
 *
 * Розведено те, що спостерігається: доступність для обходу й сигнали
 * індексованості. Фактичну індексацію Crawldy не бачить — сторінка каже
 * це прямо й не називає виключену сторінку «випадково» виключеною:
 * сигнал ми читаємо, намір — ні.
 */

import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("es");
  return (
    <>
      <Hero
        eyebrow={"Auditoría SEO"}
        title={"¿Pueden los buscadores encontrar y entender tu sitio?"}
        lead={"Esta parte del análisis responde a tres preguntas en orden: si el buscador llega a la página, si la página lleva señales contra la indexación y si queda claro de qué trata."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. ¿Puede el buscador llegar a las páginas?"} lead={"Comprobamos robots.txt, los enlaces internos, la profundidad de las páginas, las respuestas del servidor, HTTPS y las cadenas de redirecciones. El informe muestra las direcciones concretas a las que un buscador puede no llegar, con el motivo de cada una."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. ¿Hay señales que dificulten la indexación?"} lead={"Comprobamos noindex, canonical, el mapa del sitio y las contradicciones entre estas señales. Muestran si hay indicios técnicos que puedan dificultar la indexación. Si una página está indexada de hecho, Crawldy no lo determina."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. ¿Queda claro de qué trata la página?"} lead={"Comprobamos los títulos, las descripciones, el H1, la estructura del texto, los textos de los enlaces y las páginas con muy poco contenido. Para cada problema el informe muestra en qué páginas se encontró."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Qué te da el informe"} lead={"Bajo cada hallazgo mostramos qué esperábamos ver, qué vimos en realidad y en qué páginas se encontró. Ordenamos los problemas por prioridad teniendo en cuenta la gravedad, el efecto esperado, el esfuerzo de corrección y la importancia de la página."} />
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

export const es: LocalizedPage = {
  slug: "auditoria-seo",
  title: "Auditoría SEO — rastreo, indexación y comprensión de tus páginas",
  h1: "¿Pueden los buscadores encontrar y entender tu sitio?",
  description:
    "Tres etapas de la visibilidad en buscadores en un informe: si pueden llegar a tus páginas, indexarlas y entenderlas, con pruebas de cada hallazgo.",
  navLabel: "Auditoría SEO",
  Body,
};
