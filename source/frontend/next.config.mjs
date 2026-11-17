import path from "node:path";
import { fileURLToPath } from "node:url";

import { securityHeaders } from "./security-headers.mjs";

/**
 * Корінь трасування задано явно.
 *
 * Next виводить його з розташування lockfile, а в домашній теці
 * користувача лежить сторонній `package-lock.json` — і корінь ставав
 * `<HOME>`. Наслідок не косметичний: у трасування збірки
 * потрапляє чуже дерево, а `standalone` збирає не те.
 */
const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * Другий домен не має створювати другий сайт.
 *
 * `crawldy.com` куплений разом із `crawldy.ai` і вказує на той самий
 * застосунок. Якби він віддавав вміст кодом 200, вийшла б повна копія
 * сайту на іншому домені — дублікат, який ми самі й називаємо знахідкою
 * в чужих аудитах.
 *
 * Абсолютний canonical на `.ai` цю ситуацію пояснює, але не усуває:
 * пошук усе одно мусить обійти обидві копії, щоб дізнатися про звʼязок,
 * а частина систем canonical між доменами трактує як пораду. Постійне
 * перенаправлення не лишає місця для тлумачення й передає всю вагу
 * посилань на канонічний домен.
 *
 * Умова за заголовком `host`, а не за середовищем: локальна розробка й
 * попередні збірки йдуть з інших доменів і під правило не підпадають.
 */
const CANONICAL_HOST = "crawldy.ai";
const MIRROR_HOSTS = ["crawldy.com", "www.crawldy.com", "www.crawldy.ai"];

/**
 * Заголовки безпеки — у `security-headers.mjs` (там і пояснення, чому
 * повна CSP поки звітна, а HSTS вмикається лише змінною).
 */
const SECURITY_HEADERS = securityHeaders({
  hsts: process.env.HSTS_ENABLED === "true",
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
});

/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  outputFileTracingRoot: here,
  // Версія фреймворку в кожній відповіді нічого не дає читачеві й
  // економить роботу тому, хто підбирає експлойт під версію.
  poweredByHeader: false,
  async headers() {
    // `/:path*` — усі маршрути застосунку, включно з `/`, обробниками
    // маршрутів (`/robots.txt`, `/sitemap.xml`) і сторінкою 404.
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async redirects() {
    return MIRROR_HOSTS.map((host) => ({
      source: "/:path*",
      has: [{ type: "host", value: host }],
      destination: `https://${CANONICAL_HOST}/:path*`,
      // 308, а не 302: адреса змінилася назавжди, і пошук має перенести
      // вагу, а не тримати обидві копії в індексі.
      permanent: true,
    }));
  },
};
