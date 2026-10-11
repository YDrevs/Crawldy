/**
 * about — es. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { CardGrid, Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("es");
  return (
    <>
      {/* Прикладу звіту тут немає навмисно. Той, що стояв, показував
          сайт `example-shop.com` із балом 62, покриттям і критичною
          знахідкою — усе вигадане. Сторінка «Про нас» — це те місце,
          де читач вирішує, чи вірити нашим числам узагалі; вигадане
          число саме тут коштує найдорожче. Справжній зразок зʼявиться
          після розміщення: ним стане звіт Crawldy про самого себе. */}
      <Hero
        eyebrow={"SOBRE NOSOTROS"}
        title={"Ayudamos a entender cómo ven tu sitio los buscadores y la IA"}
        lead={"Crawldy es un servicio de análisis de sitios web que reúne la visibilidad en buscadores, la preparación para la IA, el estado técnico del sitio y las menciones reales en asistentes de IA en un solo informe claro."}
      />

      <Section>
        <Heading title={"Por qué se creó Crawldy"} lead={"Crawldy convierte los problemas encontrados en un plan claro. En el informe se ven la escala del problema, las pruebas y la prioridad de la corrección."} />
      </Section>

      <Section>
        <Heading title={"Nuestro objetivo"} lead={"Hacer que la visibilidad de un sitio en los buscadores y en la IA sea comprensible y medible. Quien tiene un sitio debe ver no solo métricas técnicas, sino problemas concretos, su impacto y los siguientes pasos."} />
      </Section>

      <Section bordered={false}>
        <Heading title={"Para quién se creó Crawldy"} />
        <CardGrid
          cards={[
            {
              title: "Propietarios de sitios",
              text: "Para entender qué impide que clientes, buscadores y la IA encuentren tu sitio.",
            },
            {
              title: "Profesionales de marketing",
              text: "Para ver problemas de visibilidad, contenido e indexación y fijar prioridades de trabajo.",
            },
            {
              title: "Agencias web",
              text: "Para revisar los sitios de clientes con una metodología única y entregar un informe claro con pruebas.",
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

export const es: LocalizedPage = {
  slug: "sobre-nosotros",
  title: "Sobre Crawldy — análisis de sitios para buscadores e IA",
  h1: "Ayudamos a entender cómo ven tu sitio los buscadores y la IA",
  description:
    "Crawldy reúne visibilidad en buscadores, preparación para la IA, estado técnico y menciones reales en la IA en un informe. Por qué se creó y para quién.",
  navLabel: "Sobre nosotros",
  Body,
};
