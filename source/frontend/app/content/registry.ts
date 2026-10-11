/**
 * Усі публічні сторінки в одній таблиці.
 *
 * Додати сторінку = написати її вміст і дописати сюди рядок. Ніде
 * більше: маршрут, карта сайту, `hreflang`, меню, підвал і перелінковка
 * читають звідси.
 *
 * Порожньо для мови означає «сторінки цією мовою немає» — не «поки не
 * переклали». Різниця видима зовні: такої адреси не існує, вона не
 * зʼявляється в перемикачі мов і не оголошується в `hreflang`.
 */

import { aiVisibility } from "./ai-visibility";
import { about } from "./about";
import { contact } from "./contact";
import { geoAudit } from "./geo-audit";
import { legalAcceptableUse } from "./legal-acceptable-use";
import { legalPrivacy } from "./legal-privacy";
import { legalRefunds } from "./legal-refunds";
import { legalTerms } from "./legal-terms";
import { methodology } from "./methodology";
import { pricing } from "./pricing";
import { technicalSeoAudit } from "./technical-seo-audit";
import { home } from "./home";
import { seoAudit } from "./seo-audit";
import { websiteAudit } from "./website-audit";
import type { PageDefinition, PageKey } from "../lib/page-types";

/**
 * `Partial` навмисно: `PageKey` перелічує сторінки, які **заплановані**,
 * а таблиця містить ті, що **написані**. Приведення типом до повного
 * `Record` зробило б із запланованої сторінки таку, що ніби існує, — і
 * перше ж посилання на неї впало б у рантаймі замість збірки.
 */
export const PAGES: Partial<Record<PageKey, PageDefinition>> = {
  home,
  ai_visibility: aiVisibility,
  website_audit: websiteAudit,
  seo_audit: seoAudit,
  methodology: methodology,
  about: about,
  contact: contact,
  geo_audit: geoAudit,
  technical_seo_audit: technicalSeoAudit,
  pricing: pricing,
  legal_privacy: legalPrivacy,
  legal_terms: legalTerms,
  legal_refunds: legalRefunds,
  legal_acceptable_use: legalAcceptableUse,
};
