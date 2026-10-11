/**
 * Metodología — español. Estructura según la decisión del propietario
 * (pantalla 06): cobertura → datos comprobados → pruebas → puntuación →
 * prioridades, más las «Reglas exactas de cálculo» del snapshot real.
 */

import { ScoringRules } from "../../components/ScoringRules";
import { Heading, Hero, Prose, Section } from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("es");
  return (
    <>
      <Hero
        eyebrow="Metodología"
        title={"Cómo obtiene Crawldy los resultados del análisis"}
        lead={"Crawldy extrae conclusiones solo de lo que pudo comprobar realmente. Para cada problema detectado, el informe muestra las pruebas, el contexto y la lógica de su prioridad."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title="Primero determinamos la cobertura" />
            <Prose
              paragraphs={[
                "Crawldy encuentra las páginas del sitio y comprueba cuáles se pudieron cargar y analizar. En el informe se ve cuántas páginas se encontraron, se comprobaron y quedaron inaccesibles.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Solo cuentan los datos comprobados" />
            <Prose
              paragraphs={[
                "Si una parte del sitio o un indicador concreto no se pudo comprobar, Crawldy no le pone un cero ni inventa un resultado. Esos datos quedan fuera del cálculo. Si la cobertura es insuficiente, no se muestra la puntuación general.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Confirmamos cada problema" />
            <Prose
              paragraphs={[
                "Para cada hallazgo el informe muestra qué se comprobó, qué se encontró y en qué páginas. Eso permite verificar la conclusión y entender qué hay que corregir exactamente.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Formamos la puntuación" />
            <Prose
              paragraphs={[
                "Los problemas influyen en el resultado de forma distinta. Las infracciones graves pesan más que las menores. Si un problema se repite en muchas páginas, se tiene en cuenta, pero su impacto no se multiplica sin límite.",
                "La puntuación general se forma solo con las dimensiones que tienen datos suficientes.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Decidimos qué corregir primero" />
            <Prose
              paragraphs={[
                "Crawldy pondera la gravedad del problema, el resultado esperado, el esfuerzo de la corrección y la importancia de la página. Por eso el informe muestra de inmediato por dónde empezar.",
              ]}
            />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title="Reglas exactas de cálculo" />
        <ScoringRules
          locale="es"
          strings={{
            caption: "Reglas de puntuación",
            weightsTitle: "Pesos de las direcciones",
            severityTitle: "Multiplicadores de gravedad",
            limitsTitle: "Límites",
            modules: {
              seo: "Visibilidad en buscadores",
              performance: "Velocidad y uso",
              ai_ready: "Preparación para la IA",
              tech: "Seguridad básica",
              llm_visibility: "Utilizable como fuente",
              accessibility: "Accesibilidad",
            },
            severities: {
              critical: "Crítica",
              high: "Alta",
              medium: "Media",
              low: "Baja",
              info: "Informativa",
            },
            minCoverageLabel: "Texto mínimo para puntuar el contenido",
            minCoverageValue: "{n} palabras en todo el sitio",
            repetitionLabel: "Repetición de un problema",
            repetitionValue: "como máximo ×{n} de un solo hallazgo",
            shareLabel: "Impacto de un problema en una dirección",
            shareValue: "como máximo el {p} de la media escala de la dirección",
          }}
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
  slug: "metodologia",
  title: "Metodología — cómo obtiene Crawldy los resultados del análisis",
  h1: "Cómo obtiene Crawldy los resultados del análisis",
  description:
    "Cobertura, datos comprobados, pruebas, puntuación y prioridades: cómo mide Crawldy un sitio, con las reglas exactas de cálculo.",
  navLabel: "Metodología",
  Body,
};
