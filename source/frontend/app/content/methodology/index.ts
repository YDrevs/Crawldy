/**
 * methodology — одна сторінка, кілька мов.
 *
 * Мова зʼявляється в переліку тоді, коли її текст написаний. Порожньо
 * означає «сторінки цією мовою немає», а не «поки не переклали»: такої
 * адреси не існує, вона не в перемикачі й не в hreflang.
 */

import type { PageDefinition } from "../../lib/page-types";
import { de } from "./de";
import { en } from "./en";
import { uk } from "./uk";
import { ru } from "./ru";
import { es } from "./es";
import { fr } from "./fr";

export const methodology: PageDefinition = {
  key: "methodology",
  // Погоджена архітектура футера 2026-09-03: «Методологія» — другий
  // пункт колонки «Продукт», одразу після «Що перевіряємо», і той самий
  // порядок повторює шапка.
  group: "product",
  schema: "web_page",
  navOrder: 2,
  inHeader: true,
  locales: { en, de, fr, es, ru, uk },
};
