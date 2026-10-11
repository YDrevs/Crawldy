/**
 * website_audit — одна сторінка, кілька мов.
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

export const websiteAudit: PageDefinition = {
  key: "website_audit",
  group: "product",
  schema: "web_page",
  // Перший у шапці: «Аналіз сайту» — це сам продукт, і він стоїть
  // попереду сторінок про його виміри.
  navOrder: 1,
  inHeader: true,
  locales: { en, de, es, fr, ru, uk },
};
