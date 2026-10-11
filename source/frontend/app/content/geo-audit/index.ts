/**
 * geo_audit — одна сторінка, кілька мов.
 *
 * Мова зʼявляється в переліку тоді, коли її текст написаний. Порожньо
 * означає «сторінки цією мовою немає», а не «поки не переклали»: такої
 * адреси не існує, вона не в перемикачі й не в hreflang.
 */

import type { PageDefinition } from "../../lib/page-types";
import { en } from "./en";
import { fr } from "./fr";

export const geoAudit: PageDefinition = {
  key: "geo_audit",
  // Погоджена архітектура футера (2026-09-03) не містить цього пункту:
  // без navOrder сторінка живе поза переліками — до неї ведуть
  // перехресні посилання з тексту (fr) і карта сайту.
  group: "materials",
  schema: "web_page",
  locales: { en, fr },
};
