/**
 * legal-acceptable-use — один документ, шість мов.
 *
 * Юридичні сторінки стоять окремою групою підвалу: вони не пояснюють
 * продукт і не ведуть у воронку, а дають знайти умови.
 */

import type { PageDefinition } from "../../lib/page-types";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { ru } from "./ru";
import { uk } from "./uk";

export const legalAcceptableUse: PageDefinition = {
  key: "legal_acceptable_use",
  group: "legal",
  schema: "web_page",
  navOrder: 4,
  locales: { en, de, fr, es, ru, uk },
};
