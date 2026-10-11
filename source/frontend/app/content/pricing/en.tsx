/**
 * Ціни — en. Композиція повернута до стану `164a74d` (рішення власника
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
      <Hero title="How much does a website analysis cost?" compact lead="Every option gives you the same full report. You can pay for a single analysis, buy a pack at a lower price per site, or choose a monthly plan." />

      <Section tight>
        <PricingCards
          locale="en"
          strings={{
            free: {
              heading: "Free Preview",
              bullets: [
                "Overall website score",
                "Analysis coverage",
                "Three issues with the greatest impact",
              ],
              cta: "Check your site",
            },
            single: {
              kind: "Single analysis",
              analyses: {
                one: "{n} full website analysis",
                other: "{n} full website analyses",
              },
              scores: "Scores for each audited area",
              issues: "All detected issues with evidence",
              pages: "Pages affected by each issue",
              order: "What to fix and in what order",
              download: "Downloadable full report",
              presence: {
                one: "Actual AI Presence: {n} check",
                other: "Actual AI Presence: {n} checks",
              },
              note: "No account needed",
              cta: "Get the report",
            },
            pack: {
              kind: "Analysis pack",
              analyses: {
                one: "{n} full website analysis",
                other: "{n} full website analyses",
              },
              includesSingle: "The same full report for every analysis",
              presence: {
                one: "Actual AI Presence: {n} check",
                other: "Actual AI Presence: {n} checks",
              },
              unitPrice: "{unit_price} per analysis",
              noExpiry: "Does not expire",
              manage: "Manage analyses and balance in your account",
              note: "A Crawldy account is required",
              cta: "Buy the pack",
            },
            monthly: {
              badge: "For regular use",
              kind: "Monthly plan",
              unlimited: "Unlimited full website analyses",
              analysesPerMonth: {
                one: "{n} full website analysis per month",
                other: "{n} full website analyses per month",
              },
              includesSingle: "The same full report for every analysis",
              presencePerMonth: {
                one: "Actual AI Presence: {n} check per month",
                other: "Actual AI Presence: {n} checks per month",
              },
              renews: "Allowances renew monthly",
              manage: "Manage analyses and balance in your account",
              note: "A Crawldy account is required",
              cta: "Subscribe",
            },
            perMonth: "/ month",
            priceOnRequest: "Price on request",
            loadFailed: "Could not load the current offers. The free check works regardless — try this page again later.",
          }}
        />
      </Section>
    </>
  );
}

export const en: LocalizedPage = {
  slug: "pricing",
  title: "Crawldy pricing — one website analysis, three ways to pay",
  h1: "How much does a website analysis cost?",
  description:
    "A one-time analysis, a pack that does not expire, or a monthly plan — each is the same full website analysis for search and AI, with Actual AI Presence included in the paid formats.",
  navLabel: "Pricing",
  Body,
};
