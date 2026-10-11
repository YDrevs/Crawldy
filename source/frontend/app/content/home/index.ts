/**
 * Головна — одна сторінка, кілька мов.
 *
 * Кожна мова у власному файлі: локалізація тут не переклад, а окремий
 * редакторський текст під місцевий пошуковий намір.
 */

import type { PageDefinition } from "../../lib/page-types";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { ru } from "./ru";
import { uk } from "./uk";

export const home: PageDefinition = {
  key: "home",
  group: "product",
  schema: "web_page",
  locales: { en, de, uk, es, fr, ru },
};
