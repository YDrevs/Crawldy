/**
 * technical-seo-audit — es. Структура затвердженої пропозиції E2
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
  const cta = ctaOf("es");
  return (
    <>
      <Hero
        eyebrow={"Auditoría técnica del sitio"}
        title={"Qué impide técnicamente que el sitio funcione bien"}
        lead={"Esta parte del análisis compara lo que devuelve el servidor con el resultado tras ejecutar los scripts y muestra dónde no coinciden."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Velocidad y estabilidad"} lead={"Comprobamos el tiempo de respuesta del servidor, el peso de las páginas, los recursos que bloquean la carga, los scripts de terceros y los Core Web Vitals cuando hay datos de usuarios reales. Cada número del informe lleva su fuente: datos de campo o medición de laboratorio."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. HTTPS, redirecciones y protección básica"} lead={"Comprobamos el certificado, las transiciones entre HTTP y HTTPS y entre las versiones con y sin www, las cadenas de redirecciones largas o cíclicas, las cabeceras de seguridad, la caché y los recursos sin proteger en páginas protegidas. Son señales visibles, no una búsqueda de vulnerabilidades."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Respuesta del servidor frente al DOM renderizado"} lead={"Comparamos la respuesta HTML del servidor con el DOM tras ejecutar JavaScript. Así detectamos contenido, enlaces, navegación o datos estructurados presentes solo en una de las dos versiones de la página, y mostramos en cuál."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"4. Formularios y gestión de errores"} lead={"Comprobamos con qué método envían los datos los formularios de contacto y si hay señales visibles de protección frente al spam automatizado. También comprobamos cómo responde el sitio a direcciones inexistentes. Una página de error debe devolver un código de error, no la respuesta «todo correcto»."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"5. Accesibilidad y usabilidad"} lead={"Comprobamos los obstáculos habituales para quienes usan el sitio de otra manera: contraste, etiquetas de los controles, estructura de los encabezados, zoom en el teléfono y si un número de teléfono se puede tocar. Es una comprobación automática, no una certificación WCAG."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Pruebas y recomendaciones en el informe"} lead={"Para cada problema el informe muestra la dirección de la página, el resultado esperado, la respuesta real y la prueba técnica. Eso da al desarrollador un punto de partida concreto."} />
        <p className="mt-4 max-w-measure text-sm text-muted">{"Es una comprobación técnica automática, no una prueba de penetración, una búsqueda de vulnerabilidades ni una certificación de accesibilidad."}</p>
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
  slug: "auditoria-seo-tecnica",
  title: "Auditoría técnica del sitio — servidor, HTTPS, JavaScript, velocidad",
  h1: "Qué impide técnicamente que el sitio funcione bien",
  description:
    "Razones técnicas concretas por las que un sitio no funciona bien: respuestas del servidor, HTTPS y redirecciones, contenido renderizado, velocidad y ajustes básicos, con pruebas.",
  navLabel: "Auditoría técnica del sitio",
  Body,
};
