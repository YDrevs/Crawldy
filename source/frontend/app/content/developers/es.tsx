/**
 * Para desarrolladores — іспанська версія.
 *
 * Дочірніх сторінок немає навмисно: іспанські розробники шукають ці
 * теми переважно англійською, і окрема сторінка на кожну була б
 * тонкою. Хаб покриває їх повними абзацами, а не анонсами.
 *
 * Файл згенерований із каркаса `scratchpad/core_template.py`: спільною є
 * лише структура, слова написані під цю мову окремо.
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
        eyebrow="Para desarrolladores"
        title="La mecánica, sin un sitio concreto delante"
        lead="Referencia sobre el funcionamiento de rastreadores y agentes. Sin producto de por medio: si solo necesitas entender por qué una página no aparece, esto basta."
        primary={{ href: "/result", label: "Auditar un sitio" }}
      />

      <Section>
        <Heading
          title="Rastreo: cómo se decide qué se obtiene"
          lead="El descubrimiento es un recorrido de grafo con presupuesto. El sitemap orienta ese recorrido, no lo sustituye."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Los enlaces son el mapa principal",
                detail:
                  "Un rastreador parte de algún sitio y sigue lo que encuentra. Una página a la que no apunta nada solo es alcanzable si algo más señala su existencia — para eso sirve el sitemap, y por eso una página huérfana listada en él sigue comportándose de otra manera que una enlazada.",
              },
              {
                term: "El sitemap es una indicación, no una orden",
                detail:
                  "Estar en él no garantiza la obtención y faltar en él no la impide. Las fechas de modificación solo aportan algo si significan algo: un archivo donde todas las entradas dicen hoy no transmite información.",
              },
              {
                term: "Los presupuestos son reales y finitos",
                detail:
                  "Nadie lee entero un sitio grande en cada pasada. Lo leído es una muestra, y cuál sea importa mucho: el principio de un sitemap es lo que el gestor de contenidos escribió primero, es decir miles de URL de producto en una tienda y ninguna de las páginas que explican el negocio.",
              },
              {
                term: "Las URL con facetas se comen el presupuesto",
                detail:
                  "Los parámetros de filtro y orden multiplican una página en cientos. Desde fuera son URL distintas con contenido casi idéntico, y el rastreador gasta su presupuesto en demostrar que son lo mismo.",
              },
            ]}
          />
        </div>
      </Section>

      <Section>
        <Heading
          title="Indexabilidad: por qué una página obtenida puede no indexarse"
          lead="Ser obtenida es solo el principio, y las razones del fallo son invisibles en un navegador."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Una directiva noindex es una instrucción, no un defecto",
                detail:
                  "Se respeta, y a menudo es correcta: entornos de pruebas, variantes internas, archivos escasos. Lo que importa es si era intencionada — y eso solo lo sabes tú. El caso que merece una segunda mirada es una página que además enlazas de forma destacada.",
              },
              {
                term: "Canonical es una indicación fuerte sobre la identidad",
                detail:
                  "Dice qué dirección representa ese contenido. Señales contradictorias — una canonical por un lado, una redirección por otro, un sitemap por un tercero — dejan la decisión al rastreador, y puede no elegir la tuya.",
              },
              {
                term: "Los códigos de estado significan algo",
                detail:
                  "Una página inexistente devuelta con un 200 crea una página indexable que no dice nada. Una redirección temporal donde se quería una permanente deja vivas las dos direcciones.",
              },
              {
                term: "HTTPS ya no es opcional",
                detail:
                  "Una página servida por HTTP simple es un problema crítico, no una observación: los navegadores advierten, y eso socava el resto de señales de la página.",
              },
            ]}
          />
        </div>
      </Section>

      <Section>
        <Heading
          title="Renderizado: el mismo sitio, dos versiones"
          lead="Cada página se obtiene dos veces, y la diferencia entre ambas es un hallazgo en sí misma."
        />
        <Prose
          paragraphs={[
            "Los buscadores ejecutan JavaScript, así que la visibilidad en búsqueda se juzga sobre la página renderizada. Muchos agentes de IA no lo ejecutan, así que la versión estática se juzga por separado. El mismo hecho tiene un valor distinto para cada uno de los dos públicos, y por eso se informan como dos cosas.",
            "En la práctica la diferencia aparece en tres sitios: texto que solo existe tras la hidratación, JSON-LD insertado por un script y navegación que dibuja el framework. Los tres son invisibles en un navegador y decisivos para uno de los dos lectores.",
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Agentes de IA: tres decisiones, no una"
          lead="Tratarlos como una sola política es la forma más común de perder una visibilidad que se quería conservar."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Obtención para responder",
                detail:
                  "Un agente obtiene tu página porque alguien ha hecho una pregunta que quiere responder, a menudo citando la fuente. Es lo más parecido a la búsqueda: la referencia y la atribución son la razón para permitirlo.",
              },
              {
                term: "Recopilación para entrenamiento",
                detail:
                  "Un agente reúne contenido en un conjunto de datos. Sin pregunta, sin cita, sin visita. Permitirlo es una decisión legítima, pero es otra decisión, y merece tomarse a propósito.",
              },
              {
                term: "Rastreadores de búsqueda que además alimentan la IA",
                detail:
                  "El rastreador que indexa para búsqueda puede alimentar también una función de IA del mismo producto. Bloquearlo te cuesta la búsqueda. Google-Extended es un caso claro: regula el uso de tu contenido en los productos de IA de Google, y no afecta ni a Googlebot ni a la indexación ni al posicionamiento.",
              },
            ]}
          />
        </div>
        <More href="/es/visibilidad-en-ia" label="Qué medimos de todo esto en tu sitio" />
      </Section>
      <Related
        title="Relacionado"
        links={[
          {
            href: "/es/auditoria-seo-tecnica",
            label: "Auditoría SEO técnica",
            text: "Todo esto comprobado sobre tu sitio, con pruebas.",
          },
          {
            href: "/es/metodologia",
            label: "Metodología",
            text: "Cómo los hallazgos se convierten en una puntuación.",
          },
          {
            href: "/es/visibilidad-en-ia",
            label: "Visibilidad en IA",
            text: "Acceso, comprensión y aptitud para ser citado.",
          },
        ]}
      />
    </>
  );
}

export const es: LocalizedPage = {
  slug: "desarrolladores",
  title: "Para desarrolladores — rastreo, indexabilidad, renderizado y agentes de IA",
  h1: "La mecánica, sin un sitio concreto delante",
  description:
    "Notas técnicas sobre cómo se descubren y obtienen las páginas, qué impide que una página obtenida se indexe, qué cambia el renderizado y en qué se diferencian los agentes de IA de los rastreadores de búsqueda.",
  navLabel: "Para desarrolladores",
  Body,
};
