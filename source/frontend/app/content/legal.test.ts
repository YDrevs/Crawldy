/**
 * Правова інформація: чотири документи, шість мов, робочі посилання.
 *
 * Тест дивиться на реєстр і на згенеровані сторінки, бо саме реєстр
 * тут — джерело маршрутів, карти сайту, `hreflang` і підвалу. Сторінка,
 * якої в ньому немає, не існує ні для однієї з цих поверхонь.
 *
 * Окремо стережеться те, чого пакет вимагає прямо: жодної маркетингової
 * обвʼязки на юридичній сторінці й жодного плейсхолдера. Значення, які
 * власник назвав, підставлені; речення, які несли ті, що він вирішив не
 * оголошувати, прибрані цілком — обірвана мітка «Точний перелік:» без
 * переліку гірша за відсутність речення.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PAGES } from "./registry";
import { localesOf, pathOf } from "../lib/pages";
import { PUBLIC_SITE_LOCALES } from "../lib/i18n";
import type { PageKey } from "../lib/page-types";

const KEYS: PageKey[] = [
  "legal_privacy",
  "legal_terms",
  "legal_refunds",
  "legal_acceptable_use",
];

const FOLDER: Record<string, string> = {
  legal_privacy: "legal-privacy",
  legal_terms: "legal-terms",
  legal_refunds: "legal-refunds",
  legal_acceptable_use: "legal-acceptable-use",
};

/** Підписи меню — дослівно з таблиці §3 затвердженого пакета. */
const NAV: Record<string, Record<string, string>> = {
  en: {
    legal_privacy: "Privacy and Cookies",
    legal_terms: "Terms of Service",
    legal_refunds: "Refunds and Cancellation",
    legal_acceptable_use: "Acceptable Use",
  },
  uk: {
    legal_privacy: "Конфіденційність і cookie",
    legal_terms: "Умови користування",
    legal_refunds: "Повернення коштів і скасування",
    legal_acceptable_use: "Допустиме використання",
  },
  de: {
    legal_privacy: "Datenschutz und Cookies",
    legal_terms: "Nutzungsbedingungen",
    legal_refunds: "Rückerstattungen und Kündigung",
    legal_acceptable_use: "Zulässige Nutzung",
  },
  es: {
    legal_privacy: "Privacidad y cookies",
    legal_terms: "Términos del servicio",
    legal_refunds: "Reembolsos y cancelación",
    legal_acceptable_use: "Uso aceptable",
  },
  fr: {
    legal_privacy: "Confidentialité et cookies",
    legal_terms: "Conditions d’utilisation",
    legal_refunds: "Remboursements et résiliation",
    legal_acceptable_use: "Utilisation acceptable",
  },
  ru: {
    legal_privacy: "Конфиденциальность и cookie",
    legal_terms: "Условия использования",
    legal_refunds: "Возвраты и отмена",
    legal_acceptable_use: "Допустимое использование",
  },
};

function source(key: PageKey, locale: string): string {
  return readFileSync(
    join(__dirname, FOLDER[key], `${locale}.tsx`),
    "utf-8",
  ).replace(/\r\n/g, "\n");
}

describe("чотири документи існують шістьма мовами", () => {
  it("кожен ключ зареєстровано в окремій групі підвалу", () => {
    for (const key of KEYS) {
      const page = PAGES[key];
      expect(page, key).toBeDefined();
      expect(page!.group, key).toBe("legal");
      // Без `navOrder` сторінка є, але в підвалі її немає.
      expect(page!.navOrder, key).toBeGreaterThan(0);
    }
  });

  it("кожен документ написаний усіма шістьма мовами", () => {
    for (const key of KEYS) {
      expect(localesOf(key).slice().sort(), key).toEqual(
        PUBLIC_SITE_LOCALES.slice().sort(),
      );
    }
  });

  it("адреса є в кожній мові й несе її префікс", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        const href = pathOf(key, locale);
        expect(href, `${key}/${locale}`).toBeTruthy();
        // Англійська — корінь без префікса, решта — зі своїм.
        if (locale === "en") {
          expect(href!.startsWith("/"), key).toBe(true);
          expect(href!.slice(1).split("/")[0], key).not.toBe("en");
        } else {
          expect(href!.startsWith(`/${locale}/`), `${key}/${locale}`).toBe(true);
        }
      }
    }
  });

  it("адреси всіх 24 сторінок різні", () => {
    const all = KEYS.flatMap((key) =>
      PUBLIC_SITE_LOCALES.map((locale) => pathOf(key, locale)),
    );
    expect(all).toHaveLength(24);
    expect(new Set(all).size).toBe(24);
  });
});

describe("підписи меню — ті, що затверджені", () => {
  it("кожна мова несе свій рядок із таблиці пакета", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        const page = PAGES[key]!.locales[locale]!;
        expect(page.navLabel, `${key}/${locale}`).toBe(NAV[locale]![key]);
      }
    }
  });

  it("заголовок колонки написаний шістьма мовами", () => {
    const shell = readFileSync(
      join(__dirname, "..", "components", "PublicShell.tsx"),
      "utf-8",
    );
    const block = shell.slice(shell.indexOf("  legal: {"));
    const map = block.slice(0, block.indexOf("},"));
    for (const [locale, title] of [
      ["en", "Legal"],
      ["uk", "Правова інформація"],
      ["de", "Rechtliches"],
      ["es", "Información legal"],
      ["fr", "Informations légales"],
      ["ru", "Правовая информация"],
    ] as const) {
      expect(map, locale).toContain(title);
    }
  });
});

describe("сторінка веде далі, а не у воронку", () => {
  it("кожна сторінка посилається на три сусідні й на контакт", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        const text = source(key, locale);
        const others = KEYS.filter((other) => other !== key);
        for (const other of others) {
          const href = pathOf(other, locale) as string;
          expect(text, `${key}/${locale} → ${other}`).toContain(`"${href}"`);
        }
        const contact = pathOf("contact", locale) as string;
        expect(text, `${key}/${locale} → контакт`).toContain(`"${contact}"`);
      }
    }
  });

  it("маркетингової обвʼязки на юридичних сторінках немає", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        const text = source(key, locale);
        // §10.2: ані карток тарифів, ані повторюваної кнопки запуску.
        expect(text, `${key}/${locale}`).not.toContain("SiteCta");
        expect(text, `${key}/${locale}`).not.toContain("PricingCards");
        expect(text, `${key}/${locale}`).not.toContain("ctaOf(");
      }
    }
  });
});

describe("змінні пакета підставлені, а не лишені напівфабрикатом", () => {
  // Дата чинності й домени названі власником 7 вересня 2026; перелік
  // cookie й представника в ЄС він вирішив не оголошувати, і речення,
  // які їх несли, прибрані цілком. Плейсхолдера на сторінці не лишилось
  // жодного: `[[…]]` на юридичній сторінці читається як недороблена
  // сторінка, а не як застереження.
  const DATE: Record<string, string> = {
    uk: "01 січня 2026 року",
    en: "1 January 2026",
    de: "1. Januar 2026",
    es: "1 de enero de 2026",
    fr: "1er janvier 2026",
    ru: "01 января 2026 года",
  };

  it("жодного плейсхолдера не лишилось", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        expect(source(key, locale), `${key}/${locale}`).not.toMatch(/\[\[[A-Z_]+\]\]/);
      }
    }
  });

  it("дата чинності стоїть на кожній сторінці своєю нормою", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        expect(source(key, locale), `${key}/${locale}`).toContain(DATE[locale]!);
      }
    }
  });

  it("розділу «Міжнародна передача» немає в жодній мові", () => {
    // Рішення власника 7 вересня 2026: розділ видаляється цілком —
    // із заголовком, абзацом і реченням про представника в ЄС, яке в
    // ньому стояло. Половина розділу була б гіршою за його відсутність.
    const GONE: Record<string, string[]> = {
      uk: ["Міжнародна передача", "представника Crawldy у ЄС"],
      en: ["International transfers", "EU representative"],
      de: ["Internationale Übermittlungen", "EU-Vertreter"],
      es: ["Transferencias internacionales", "Representante de Crawldy en la UE"],
      fr: ["Transferts internationaux", "Représentant de Crawldy"],
      ru: ["Международная передача", "Представитель Crawldy в ЕС"],
    };
    for (const locale of PUBLIC_SITE_LOCALES) {
      const text = source("legal_privacy", locale);
      for (const gone of GONE[locale]!) {
        expect(text, `${locale}: «${gone}»`).not.toContain(gone);
      }
    }
  });

  it("про cookie сказано рівно одне речення — про технічно необхідні", () => {
    const COOKIES: Record<string, string> = {
      uk: "Crawldy може використовувати технічно необхідні cookie для роботи сайту, авторизації та збереження налаштувань користувача.",
      en: "Crawldy may use technically necessary cookies for the operation of the site, authentication, and storing user preferences.",
      de: "Crawldy kann technisch notwendige Cookies für den Betrieb der Website, die Anmeldung und das Speichern von Nutzereinstellungen verwenden.",
      es: "Crawldy puede usar cookies técnicamente necesarias para el funcionamiento del sitio, la autenticación y el almacenamiento de las preferencias del usuario.",
      fr: "Crawldy peut utiliser des cookies techniquement nécessaires au fonctionnement du site, à l’authentification et à l’enregistrement des préférences de l’utilisateur.",
      ru: "Crawldy может использовать технически необходимые cookie для работы сайта, авторизации и сохранения пользовательских настроек.",
    };
    for (const locale of PUBLIC_SITE_LOCALES) {
      const text = source("legal_privacy", locale);
      expect(text, locale).toContain(COOKIES[locale]!);
      // Абзац про Turnstile і Paddle лишився: він про інше.
      expect(text, `${locale}: Turnstile`).toContain("Turnstile");
    }
  });

  it("політика називає обидва домени", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const text = source("legal_privacy", locale);
      expect(text, locale).toContain("crawldy.ai");
      expect(text, locale).toContain("crawldy.com");
    }
  });

  it("сторінка не обіцяє елемента керування, якого немає", () => {
    // Пункт «Налаштування cookie» зʼявиться лише після consent manager
    // (§3 пакета), тож текст, який на нього посилався, переписано
    // власником 7 вересня 2026 на одне речення про технічно необхідні
    // cookie. Разом із ним пішов і `[[COOKIE_TABLE]]`: він стояв там же.
    const SETTINGS = ["Налаштування cookie", "Cookie Settings",
                      "Cookie-Einstellungen", "Configuración de cookies",
                      "Paramètres des cookies", "Настройки cookie"];
    const INVENTORY = ["Точний перелік", "Exact inventory", "Vollständige Liste",
                       "Inventario exacto", "Inventaire exact", "Точный перечень"];
    for (const locale of PUBLIC_SITE_LOCALES) {
      const text = source("legal_privacy", locale);
      for (const stub of [...SETTINGS, ...INVENTORY]) {
        expect(text, `${locale}: «${stub}»`).not.toContain(stub);
      }
      // Подвійного пробілу на місці прибраного речення теж немає:
      // дивимось усередину самих рядків тексту, а не на відступи коду.
      for (const value of text.match(/text: "(?:[^"\\]|\\.)*"/g) ?? []) {
        expect(value, `${locale}: подвійний пробіл`).not.toContain("  ");
      }
    }
  });
});

describe("структура однакова в усіх мовах, база — українська", () => {
  // Пакет подавав DE/ES/FR/RU скорочено: розділи були злиті. Власник
  // перевіряє українську версію, тож решта мов мусить мати ті самі
  // розділи в тому самому порядку — інакше перевірена ним сторінка не
  // описує того, що читає німець.
  const headings = (key: PageKey, locale: string): string[] =>
    Array.from(source(key, locale).matchAll(/kind: "heading", text: "([^"]*)"/g))
      .map((match) => match[1]!);

  it("кількість і порядок розділів збігаються з базою", () => {
    for (const key of KEYS) {
      const base = headings(key, "uk").length;
      expect(base, `${key}: база порожня`).toBeGreaterThan(0);
      for (const locale of PUBLIC_SITE_LOCALES) {
        expect(headings(key, locale).length, `${key}/${locale}`).toBe(base);
      }
    }
  });

  it("кожен розділ має власний непорожній заголовок", () => {
    for (const key of KEYS) {
      for (const locale of PUBLIC_SITE_LOCALES) {
        const list = headings(key, locale);
        for (const title of list) {
          expect(title.trim(), `${key}/${locale}`).not.toBe("");
        }
        // Два однакові заголовки на сторінці — слід невдалого розрізу.
        expect(new Set(list).size, `${key}/${locale}: дублі`).toBe(list.length);
      }
    }
  });
});
