/**
 * ai-visibility — es. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { PresenceModels } from "../../components/PresenceModels";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import {
  Bullets,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("es");
  return (
    <>
      <Hero
        eyebrow={"Visibilidad en la IA"}
        title={"¿Te ven y te mencionan los sistemas de IA?"}
        lead={"Crawldy comprueba si la IA puede obtener tus páginas, entender la información sobre tu empresa y usar el sitio como fuente. En el informe completo, Actual AI Presence también muestra si ChatGPT, Claude, Perplexity y Gemini mencionan tu marca."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"Acceso para la IA"} lead={"Comprobamos si los sistemas de IA pueden cargar tus páginas y obtener el contenido principal. Tenemos en cuenta las restricciones a los rastreadores de IA, las respuestas del servidor y la dependencia del sitio de JavaScript."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Comprensión de tu negocio"} lead={"Comprobamos si en las páginas queda claro quién eres, qué ofreces y cómo contactarte. Para ello analizamos la estructura del contenido, los datos de la empresa, los contactos y el marcado correspondiente."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Aptitud como fuente"} lead={"Comprobamos si el sitio contiene respuestas claras, contexto suficiente, autoría indicada y afirmaciones que la IA pueda usar correctamente en una respuesta."} />
          </div>
        </div>
      </Section>

      <Section>
        <Heading title={"Presencia real en las respuestas"} />
        <PresenceModels
          intro={"Para cada comprobación, Crawldy utiliza los modelos seleccionados como los más representativos de la experiencia de usuario actual en cada plataforma de IA."}
          note={"Los modelos de las plataformas de IA cambian con el tiempo, y modelos distintos pueden mencionar marcas, recomendar empresas y usar fuentes de forma diferente. Por eso, el resultado de Actual AI Presence se refiere a los modelos indicados para esa comprobación concreta."}
        />
      </Section>

      <Section bordered={false}>
        <Heading title={"Qué verás en el informe"} />
        <Bullets
          items={[
            "problemas que impiden a la IA obtener o entender el contenido",
            "las páginas y las pruebas de cada conclusión",
            "menciones de marca y enlaces en las respuestas de los asistentes",
            "los otros dominios que los asistentes nombraron en tu lugar",
            "prioridades para corregir",
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

export const es: LocalizedPage = {
  slug: "visibilidad-en-ia",
  title: "Visibilidad en la IA — ¿obtiene, entiende y menciona la IA tu sitio?",
  h1: "¿Te ven y te mencionan los sistemas de IA?",
  description:
    "Si los sistemas de IA pueden obtener tus páginas, entender tu negocio y usar el sitio como fuente, y si ChatGPT, Claude, Perplexity y Gemini mencionan tu marca.",
  navLabel: "Visibilidad en la IA",
  Body,
};
