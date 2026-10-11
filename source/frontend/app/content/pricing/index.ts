/**
 * pricing — сторінка цін.
 *
 * Написана всіма шістьма мовами публічного сайту: він дубльований
 * повністю, і сторінка цін — не виняток (правило «en/uk досить»
 * стосується лише кабінету). Кожна мова — власний текст, не переклад.
 *
 * Числа на сторінці живі: їх рендерить <PricingCards/> з комерційної
 * конфігурації бекенда. У вмісті сторінки цін немає жодної ціни — і
 * тест це стереже для всіх мов одразу.
 */

import type { PageDefinition } from "../../lib/page-types";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { ru } from "./ru";
import { uk } from "./uk";

export const pricing: PageDefinition = {
  key: "pricing",
  group: "product",
  schema: "pricing",
  // Третій пункт колонки «Продукт» і шапки: Що перевіряємо →
  // Методологія → Ціни (погоджена архітектура 2026-09-03).
  navOrder: 3,
  inHeader: true,
  locales: { en, de, fr, es, ru, uk },
};
