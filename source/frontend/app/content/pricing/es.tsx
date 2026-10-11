/**
 * Ціни — es. Композиція повернута до стану `164a74d` (рішення власника
 * 2026-09-05): H1 → одне пояснювальне речення → чотири рівні блоки в ряд:
 * Безкоштовне превʼю, Разова, Пакет, Місячний план. Перебудова «смуга
 * превʼю + три картки» була пропозицією без затвердження і знята.
 *
 * Рядки — затверджений вміст блоків; числа — ціни, кількість перевірок,
 * кількість Actual AI Presence — рендерить <PricingCards/> з комерційної
 * конфігурації бекенда; у цьому файлі їх немає, і тест це стереже для
 * всіх мов одразу. Форми множини постачає ця сторінка: закінчень у коді
 * компонента не зашито.
 */

import { PricingCards } from "../../components/PricingCards";
import { Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero title="¿Cuánto cuesta analizar un sitio web?" compact lead="Todas las opciones incluyen el mismo informe completo. Puedes pagar un análisis individual, comprar un paquete con un precio más bajo por sitio o elegir un plan mensual." />

      <Section tight>
        <PricingCards
          locale="es"
          strings={{
            free: {
              heading: "Vista previa gratuita",
              bullets: [
                "Puntuación general del sitio",
                "Cobertura del análisis",
                "Tres problemas con mayor impacto",
              ],
              cta: "Comprobar el sitio",
            },
            single: {
              kind: "Análisis individual",
              analyses: {
                one: "{n} análisis completo del sitio",
                other: "{n} análisis completos de sitios",
              },
              scores: "Puntuación de cada área analizada",
              issues: "Todos los problemas detectados con pruebas",
              pages: "Páginas afectadas por cada problema",
              order: "Qué corregir y en qué orden",
              download: "Informe completo descargable",
              presence: {
                one: "Actual AI Presence: {n} comprobación",
                other: "Actual AI Presence: {n} comprobaciones",
              },
              note: "Sin registro",
              cta: "Obtener el informe",
            },
            pack: {
              kind: "Paquete de análisis",
              analyses: {
                one: "{n} análisis completo del sitio",
                other: "{n} análisis completos de sitios",
              },
              includesSingle: "El mismo informe completo para cada análisis",
              presence: {
                one: "Actual AI Presence: {n} comprobación",
                other: "Actual AI Presence: {n} comprobaciones",
              },
              unitPrice: "{unit_price} por análisis",
              noExpiry: "No caduca",
              manage: "Gestión de análisis y saldo desde tu cuenta",
              note: "Requiere una cuenta de Crawldy",
              cta: "Comprar el paquete",
            },
            monthly: {
              badge: "Para uso habitual",
              kind: "Plan mensual",
              unlimited: "Análisis completos de sitios ilimitados",
              analysesPerMonth: {
                one: "{n} análisis completo al mes",
                other: "{n} análisis completos al mes",
              },
              includesSingle: "El mismo informe completo para cada análisis",
              presencePerMonth: {
                one: "Actual AI Presence: {n} comprobación al mes",
                other: "Actual AI Presence: {n} comprobaciones al mes",
              },
              renews: "Los límites se renuevan cada mes",
              manage: "Gestión de análisis y saldo desde tu cuenta",
              note: "Requiere una cuenta de Crawldy",
              cta: "Suscribirse",
            },
            perMonth: "/ mes",
            priceOnRequest: "Precio a consultar",
            loadFailed: "No se pudieron cargar las ofertas actuales. La comprobación gratuita funciona de todos modos — vuelve a intentarlo más tarde.",
          }}
        />
      </Section>
    </>
  );
}

export const es: LocalizedPage = {
  slug: "precios",
  title: "Precios de Crawldy — un análisis del sitio, tres formas de pago",
  h1: "¿Cuánto cuesta analizar un sitio web?",
  description:
    "Un análisis único, un pack que no caduca o un plan mensual — cada opción es el mismo análisis completo del sitio para buscadores e IA, con Actual AI Presence incluido en los formatos de pago.",
  navLabel: "Precios",
  Body,
};
