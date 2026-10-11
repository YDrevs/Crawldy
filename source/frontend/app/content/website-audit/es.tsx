/**
 * Qué comprobamos — español. Estructura como en en.tsx (журнал правок,
 * екран 02): introducción → seis direcciones (tarjetas no interactivas)
 * → cómo se forma la puntuación → qué corregir primero → pie.
 */

import {
  CardGrid,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("es");
  return (
    <>
      <Hero
        eyebrow="Auditoría web"
        title="Análisis del sitio web para buscadores e IA"
        lead="Crawldy comprueba tu sitio en seis dimensiones y muestra qué conviene corregir primero. Para cada problema el informe incluye las pruebas y las páginas a las que afecta."
      />

      <Section>
        <Heading
          title="Las seis dimensiones del análisis"
          lead="Crawldy comprueba la visibilidad del sitio en buscadores e IA, su velocidad, la seguridad básica y la accesibilidad."
        />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Visibilidad en buscadores",
              text: "Comprobamos si los buscadores pueden encontrar y leer tus páginas, si hay señales técnicas que puedan dificultar la indexación y si hay problemas en la estructura del sitio y en los enlaces.",
            },
            {
              icon: "clock",
              title: "Velocidad y uso",
              text: "Comprobamos con qué rapidez cargan las páginas, cómo responde el servidor y qué puede ralentizar el sitio. Si hay datos de usuarios reales, también los tenemos en cuenta.",
            },
            {
              icon: "globe",
              title: "Preparación para la IA",
              text: "Comprobamos si la IA puede reconocer correctamente tu negocio, sus páginas, contactos y otra información importante.",
            },
            {
              icon: "link",
              title: "Utilizable como fuente",
              text: "Comprobamos si el sitio contiene respuestas claras, autoría indicada y contexto suficiente para que la IA pueda usarlo como fuente.",
            },
            {
              icon: "alert",
              title: "Seguridad básica",
              text: "Comprobamos HTTPS, la configuración de seguridad, la protección de formularios y el manejo correcto de errores técnicos. No es una búsqueda de vulnerabilidades.",
            },
            {
              icon: "user",
              title: "Accesibilidad",
              text: "Comprobamos problemas típicos que pueden impedir a las personas usar el sitio. Es una comprobación automática, no una certificación WCAG.",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Cómo se forma la puntuación del sitio"
          lead="El resultado depende no solo de los problemas encontrados, sino también de qué parte del sitio se pudo comprobar. Por eso Crawldy muestra la cobertura junto a la puntuación."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "La cobertura se ve de inmediato",
                detail:
                  "Mostramos cuántas páginas se encontraron, se cargaron y se comprobaron, y a cuántas no se pudo acceder.",
              },
              {
                term: "Lo no medido no baja la puntuación",
                detail:
                  "La puntuación se calcula solo con las dimensiones que se pudieron medir. Si faltan datos, Crawldy lo dice directamente en lugar de poner un cero.",
              },
              {
                term: "Si los datos no bastan, no hay puntuación",
                detail:
                  "Si se comprobó una parte demasiado pequeña del sitio, Crawldy no muestra una puntuación general poco fiable. Los hallazgos disponibles quedan en el informe como observaciones.",
              },
              {
                term: "Cada conclusión se puede verificar",
                detail:
                  "Para cada problema mostramos qué esperábamos encontrar, qué encontramos y en qué páginas. Eso ayuda a verificar el resultado y corregirlo antes.",
              },
            ]}
          />
        </div>
      </Section>

      <Section bordered={false}>
        <Heading
          title="Qué corregir primero"
          lead="Crawldy ordena los problemas por prioridad, teniendo en cuenta su gravedad, el efecto esperado, el esfuerzo de la corrección y la importancia de la página. Ves de inmediato por dónde empezar."
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
  slug: "auditoria-web",
  title: "Auditoría web: un informe, seis dimensiones y pruebas",
  h1: "Análisis del sitio web para buscadores e IA",
  description:
    "Auditoría web completa: visibilidad en buscadores, preparación para la IA, velocidad, seguridad básica y accesibilidad en un solo informe, con cobertura y una prueba bajo cada hallazgo.",
  navLabel: "Qué comprobamos",
  Body,
};
