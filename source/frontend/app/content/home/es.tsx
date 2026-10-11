/**
 * Portada — español. Estructura y límites de afirmaciones como en en.tsx.
 * Trato — «tú»: coherente con el resto de páginas en español.
 */

import { HeroAuditForm } from "../../components/HeroAuditForm";
import { ScorePreview } from "../../components/ScorePreview";
import {
  CardGrid,
  Heading,
  Hero,
  More,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        title="¿De verdad te ven los buscadores y la IA?"
        action={
          <HeroAuditForm
            lang="es"
            placeholder="tu-sitio.com"
            cta="Análisis gratis"
            invalid="Introduce la dirección de un sitio web, por ejemplo example.com."
          />
        }
        aside={<ScorePreview locale="es" />}
      />

      <Section>
        <Heading title="Un solo análisis del sitio responde a las tres preguntas clave sobre tu visibilidad en buscadores e IA." />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "¿Te encuentra el buscador?",
              text: "Comprobamos si Google y otros buscadores pueden encontrar y leer tus páginas.",
              href: "/es/auditoria-seo",
            },
            {
              icon: "globe",
              title: "¿Entiende la IA tu sitio?",
              text: "Comprobamos si la IA puede leer tu sitio y entender la información sobre tu negocio.",
              href: "/es/visibilidad-en-ia",
            },
            {
              icon: "link",
              title: "¿Menciona la IA tu marca?",
              text: "Comprobamos si ChatGPT, Claude, Perplexity y Gemini nombran tu marca en las respuestas sobre tu nicho.",
              href: "/es/visibilidad-en-ia",
            },
          ]}
        />
        <More href="/es/auditoria-web" label="Todos los componentes del análisis" />
      </Section>

      <Section bordered={false}>
        <Heading
          title="Una puntuación transparente del sitio"
          lead="Ves qué páginas se comprobaron, qué se pudo medir y en qué se basa la puntuación final."
        />
        <More href="/es/metodologia" label="Cómo funciona la medición" />
      </Section>
    </>
  );
}

export const es: LocalizedPage = {
  slug: "",
  title: "Crawldy — ¿te ven los buscadores y la IA?",
  h1: "¿De verdad te ven los buscadores y la IA?",
  description:
    "Crawldy muestra qué impide que tu sitio sea visible en buscadores y en la IA — y qué corregir primero.",
  navLabel: "Inicio",
  Body,
};
