/**
 * Один граф сутностей на всі мови.
 *
 * ## Той самий `@id` у кожній мові
 *
 * Crawldy — одна організація, а не шість. Якби кожна мовна версія
 * оголошувала власний ідентифікатор, машина побачила б шість різних
 * компаній із схожими назвами — тобто рівно протилежне тому, заради
 * чого розмітка існує. Тому `@id` прив'язаний до канонічного домену й
 * не залежить від мови; мовою міняється лише опис.
 *
 * ## Тільки те, що правда
 *
 * Ані `legalName`, ані адреси, ані телефону тут немає, бо їх ще немає в
 * природі. `sameAs` порожній, поки немає зовнішніх профілів: посилання
 * в нікуди обіцяє підтвердження особи, якого не існує.
 */

import { BRAND, LEGAL_ENTITY, ORIGIN, SAME_AS } from "./entity";
import type { Locale } from "./contracts";
import { ancestry, canonicalOf, pageOf, type PageKey } from "./pages";

const ORGANIZATION = `${ORIGIN}/#organization`;
const WEBSITE = `${ORIGIN}/#website`;
const APPLICATION = `${ORIGIN}/#app`;

/** Опис організації мовою читача. Факт один, речення різні. */
const ORGANIZATION_DESCRIPTION: Partial<Record<Locale, string>> = {
  en: "Crawldy audits how search engines and AI systems read a website, and what to fix first.",
  uk: "Crawldy перевіряє, як пошукові системи й AI-сервіси читають сайт, і що виправляти першим.",
};

function organization(locale: Locale) {
  return {
    "@type": "Organization",
    "@id": ORGANIZATION,
    name: BRAND,
    url: ORIGIN,
    description: ORGANIZATION_DESCRIPTION[locale] ?? ORGANIZATION_DESCRIPTION.en,
    // З'явиться разом із рішенням про юридичну особу — не раніше.
    ...(LEGAL_ENTITY ? { legalName: LEGAL_ENTITY } : {}),
    ...(SAME_AS.length > 0 ? { sameAs: SAME_AS } : {}),
  };
}

/**
 * Хлібні крихти з ланцюга батьків.
 *
 * Будуються з реєстру, а не з адреси: розібраний назад шлях дав би
 * назви сегментів, а не назви сторінок, і німецькою це були б слаги.
 */
function breadcrumbs(key: PageKey, locale: Locale) {
  const chain = ancestry(key);
  if (chain.length < 2) return null;
  return {
    "@type": "BreadcrumbList",
    "@id": `${canonicalOf(key, locale)}#breadcrumbs`,
    itemListElement: chain.map((node, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: node.locales[locale]?.navLabel,
      item: canonicalOf(node.key, locale),
    })),
  };
}

export function pageGraph(key: PageKey, locale: Locale): object {
  const page = pageOf(key, locale);
  const url = canonicalOf(key, locale);
  const graph: object[] = [organization(locale)];

  if (key === "home") {
    graph.push(
      {
        "@type": "WebSite",
        "@id": WEBSITE,
        url: ORIGIN,
        name: BRAND,
        inLanguage: locale,
        publisher: { "@id": ORGANIZATION },
      },
      {
        "@type": "SoftwareApplication",
        "@id": APPLICATION,
        name: BRAND,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        url: ORIGIN,
        publisher: { "@id": ORGANIZATION },
      },
    );
  } else if (page && url) {
    graph.push({
      "@type": "WebPage",
      "@id": url,
      url,
      name: page.h1,
      description: page.description,
      inLanguage: locale,
      isPartOf: { "@id": WEBSITE },
      publisher: { "@id": ORGANIZATION },
    });
  }

  const crumbs = breadcrumbs(key, locale);
  if (crumbs) graph.push(crumbs);

  return { "@context": "https://schema.org", "@graph": graph };
}
