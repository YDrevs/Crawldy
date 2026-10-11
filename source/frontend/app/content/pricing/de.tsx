/**
 * Ціни — de. Композиція повернута до стану `164a74d` (рішення власника
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
      <Hero title="Was kostet eine Website-Analyse?" compact lead="Bei allen Optionen erhalten Sie denselben vollständigen Bericht. Sie können eine einzelne Analyse bezahlen, ein Paket zu einem niedrigeren Preis pro Website kaufen oder einen Monatsplan wählen." />

      <Section tight>
        <PricingCards
          locale="de"
          strings={{
            free: {
              heading: "Kostenlose Vorschau",
              bullets: [
                "Gesamtbewertung der Website",
                "Abdeckung der Prüfung",
                "Drei Probleme mit dem größten Einfluss",
              ],
              cta: "Website prüfen",
            },
            single: {
              kind: "Einzelanalyse",
              analyses: {
                one: "{n} vollständige Website-Analyse",
                other: "{n} vollständige Website-Analysen",
              },
              scores: "Bewertungen für jeden geprüften Bereich",
              issues: "Alle gefundenen Probleme mit Nachweisen",
              pages: "Betroffene Seiten für jedes Problem",
              order: "Was in welcher Reihenfolge zu beheben ist",
              download: "Vollständiger Bericht zum Herunterladen",
              presence: {
                one: "Actual AI Presence: {n} Prüfung",
                other: "Actual AI Presence: {n} Prüfungen",
              },
              note: "Ohne Registrierung",
              cta: "Bericht erhalten",
            },
            pack: {
              kind: "Analysepaket",
              analyses: {
                one: "{n} vollständige Website-Analyse",
                other: "{n} vollständige Website-Analysen",
              },
              includesSingle: "Derselbe vollständige Bericht für jede Analyse",
              presence: {
                one: "Actual AI Presence: {n} Prüfung",
                other: "Actual AI Presence: {n} Prüfungen",
              },
              unitPrice: "{unit_price} pro Analyse",
              noExpiry: "Kein Ablaufdatum",
              manage: "Analysen und Guthaben im Kundenbereich verwalten",
              note: "Ein Crawldy-Konto ist erforderlich",
              cta: "Paket kaufen",
            },
            monthly: {
              badge: "Für regelmäßige Nutzung",
              kind: "Monatsplan",
              unlimited: "Unbegrenzte vollständige Website-Analysen",
              analysesPerMonth: {
                one: "{n} vollständige Website-Analyse pro Monat",
                other: "{n} vollständige Website-Analysen pro Monat",
              },
              includesSingle: "Derselbe vollständige Bericht für jede Analyse",
              presencePerMonth: {
                one: "Actual AI Presence: {n} Prüfung pro Monat",
                other: "Actual AI Presence: {n} Prüfungen pro Monat",
              },
              renews: "Kontingente werden monatlich erneuert",
              manage: "Analysen und Guthaben im Kundenbereich verwalten",
              note: "Ein Crawldy-Konto ist erforderlich",
              cta: "Abonnieren",
            },
            perMonth: "/ Monat",
            priceOnRequest: "Preis auf Anfrage",
            loadFailed: "Die aktuellen Angebote konnten nicht geladen werden. Der kostenlose Check funktioniert trotzdem — versuchen Sie es später erneut.",
          }}
        />
      </Section>
    </>
  );
}

export const de: LocalizedPage = {
  slug: "preise",
  title: "Crawldy Preise — eine Website-Analyse, drei Zahlungsoptionen",
  h1: "Was kostet eine Website-Analyse?",
  description:
    "Eine einmalige Analyse, ein Paket ohne Verfall oder ein Monatsplan — jede Option ist dieselbe vollständige Website-Analyse für Suche und KI, mit Actual AI Presence in den bezahlten Formaten.",
  navLabel: "Preise",
  Body,
};
