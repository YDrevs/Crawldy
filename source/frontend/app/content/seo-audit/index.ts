/**
 * seo_audit — одна сторінка, кілька мов.
 *
 * Кожна мова живе у власному файлі: локалізація тут не переклад, а
 * окремий редакторський текст під місцевий пошуковий намір, і тримати
 * шість таких в одному файлі означає зробити його нечитабельним уже на
 * третій мові.
 *
 * Мова зʼявляється в цьому переліку тоді, коли її текст написаний.
 */

import type { PageDefinition } from "../../lib/page-types";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { uk } from "./uk";
import { ru } from "./ru";

export const seoAudit: PageDefinition = {
  key: "seo_audit",
  // «Матеріали»: пояснює частину однієї перевірки, а не окремий
  // продукт. Живе в підвалі й у перехресних посиланнях.
  group: "materials",
  schema: "web_page",
  navOrder: 2,
  locales: { en, de, es, fr, ru, uk },
};
