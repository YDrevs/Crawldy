/**
 * about — одна сторінка, кілька мов.
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

export const about: PageDefinition = {
  key: "about",
  group: "company",
  schema: "web_page",
  navOrder: 3,
  locales: { en, de, fr, es, ru, uk },
};
