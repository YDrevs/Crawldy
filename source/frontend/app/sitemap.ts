import type { MetadataRoute } from "next";

import { ORIGIN } from "./lib/entity";
import { allRoutes, alternatesOf } from "./lib/pages";

/**
 * Карта сайту з реєстру, а не з переліку файлів.
 *
 * Досі її не існувало взагалі, тоді як `robots.txt` її оголошував —
 * тобто ми самі мали знахідку, яку продаємо клієнтам.
 *
 * Кожен запис несе мовні відповідники. Це той самий кластер, що в
 * `hreflang`, з того самого джерела: два незалежні переліки розійшлися б
 * на першій же сторінці, якої немає однією з мов.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return allRoutes().map(({ key, path }) => ({
    url: `${ORIGIN}${path}`,
    lastModified: new Date(),
    alternates: { languages: alternatesOf(key) },
  }));
}
