/**
 * Безпека розмітки контактної форми не залежить від скрипта.
 *
 * Наш власний детектор побачив на сторінці «Контакти» рівно
 * `method: "get"`, `action_scope: "empty"` — тобто ми продавали
 * спостереження, якого не виконували самі. Форма без `method` — це GET,
 * і браузер, у якого скрипт не спрацював, поклав би імʼя, пошту й текст
 * звернення в адресний рядок: в історію, у `Referer` наступного переходу
 * й у звичайні журнали проксі.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { CONTACT_FALLBACK } from "../content/contact/fallback";
import { TURNSTILE_LANGUAGE } from "./ContactForm";

const source = readFileSync(join(__dirname, "ContactForm.tsx"), "utf-8").replace(
  /\r\n/g,
  "\n",
);
const route = readFileSync(
  join(__dirname, "..", "api", "contact", "route.ts"),
  "utf-8",
).replace(/\r\n/g, "\n");

describe("розмітка форми безпечна без JavaScript", () => {
  it("метод оголошений явно і це POST", () => {
    expect(source).toContain('method="post"');
    expect(source).not.toContain('method="get"');
  });

  it("дія веде на свій origin, а не на чужий хост і не в порожнечу", () => {
    expect(source).toContain('action="/api/contact"');
    // Абсолютна адреса зробила б дію крос-доменною, а `API_URL` у
    // проді — інший хост.
    expect(source).not.toContain("action={`${API_URL}");
    expect(source).not.toContain('action=""');
  });

  it("жодне поле з даними людини не може потрапити в адресу", () => {
    // При POST браузер кладе поля в тіло. Достатньо довести, що метод
    // саме POST і що дія не несе полів у собі.
    for (const field of ["name", "email", "message", "site_url"]) {
      expect(source).toContain(`name="${field}"`);
      expect(source).not.toContain(`action="/api/contact?${field}`);
    }
  });

  it("звичайний шлях лишається на fetch: подія скасовується", () => {
    expect(source).toContain("event.preventDefault();");
    expect(source).toContain("onSubmit={submit}");
  });

  it("секретів у клієнті немає", () => {
    for (const secret of [
      "secret_key",
      "TURNSTILE_SECRET",
      "SMTP_PASSWORD",
      "contact_recipient",
    ]) {
      expect(source).not.toContain(secret);
      expect(route).not.toContain(secret);
    }
  });

  it("одержувач листа в браузер не потрапляє", () => {
    expect(source).not.toContain("@crawldy");
    expect(source).not.toMatch(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i);
  });
});

describe("челендж говорить мовою сторінки", () => {
  it("усі шість мов мають свій код", () => {
    // Спіймано власником на знімках: українська сторінка показувала
    // «Verification failed» і «Troubleshoot» англійською. Без явної мови
    // Cloudflare бере мову браузера, а не сторінки.
    const expected: Record<string, string> = {
      en: "en",
      uk: "uk",
      de: "de",
      es: "es",
      fr: "fr",
      ru: "ru",
    };
    for (const [locale, code] of Object.entries(expected)) {
      expect(TURNSTILE_LANGUAGE[locale], locale).toBe(code);
    }
  });

  it("мова передається у виклик рендеру, а не лишається в мапі", () => {
    expect(source).toContain("language: TURNSTILE_LANGUAGE[locale]");
  });

  it("на вузькому контейнері віджет компактний", () => {
    // Автоматична перевірка ширин спіймала переповнення на 42px при
    // 320px: звичайний віджет має 300px, а форма — менше. Розмір
    // обирається за контейнером до рендеру.
    expect(source).toContain('size: node.clientWidth < TURNSTILE_NORMAL_WIDTH ? "compact" : "normal"');
  });

  it("невідома мова падає в auto, а не в англійську", () => {
    expect(source).toContain('?? "auto"');
    expect(TURNSTILE_LANGUAGE["pt"]).toBeUndefined();
  });
});

describe("дії форми не стискаються на вузькому екрані", () => {
  it("до 480px дії стоять одна під одною, з 640px — у рядок", () => {
    expect(source).toContain("flex flex-col items-stretch gap-2 sm:flex-row");
  });

  it("підпис кнопки надсилання не переноситься", () => {
    expect(source).toContain("whitespace-nowrap");
    expect(source).toContain("w-full");
  });

  it("другорядна дія лишає комфортну зону дотику", () => {
    expect(source).toContain("min-h-11 w-full");
  });
});

describe("успіх лишається в ширині форми", () => {
  it("повідомлення не розтягується на весь контейнер", () => {
    const success = source.slice(source.indexOf('phase === "sent"'));
    expect(success.slice(0, 600)).toContain("max-w-xl");
  });

  it("другої кнопки й адреси пошти в ньому немає", () => {
    const success = source.slice(
      source.indexOf('phase === "sent"'),
      source.indexOf('const field ='),
    );
    expect(success).not.toContain("<button");
    expect(success).not.toContain("href=");
  });
});

describe("початковий стан і розкриття збережені", () => {
  it("форма присутня в розмітці й схована класом, а не лише атрибутом", () => {
    // `display: flex` із класу перебиває стиль браузера для `[hidden]`,
    // і форма лишалась на екрані разом із кнопкою.
    expect(source).toContain('opened ? "flex" : "hidden"');
    expect(source).toContain("hidden={!opened}");
  });

  it("кнопка оголошує стан і ціль", () => {
    expect(source).toContain("aria-expanded={false}");
    expect(source).toContain('aria-controls="contact-form"');
    expect(source).toContain('id="contact-form"');
  });

  it("фокус їде в перше поле, Escape повертає його на кнопку", () => {
    expect(source).toContain("firstField.current?.focus();");
    expect(source).toContain('if (event.key === "Escape") close();');
    expect(source).toContain("openButton.current?.focus();");
  });
});

describe("запасний маршрут не обходить жодної перевірки", () => {
  it("він пересилає на бекенд, а не приймає рішення сам", () => {
    expect(route).toContain("`${API_URL}/v1/contact`");
    expect(route).toContain('method: "POST"');
  });

  it("успіх лише за відповіддю бекенда", () => {
    expect(route).toContain("accepted = response.ok;");
    // Немає жодного місця, де успіх ставиться без відповіді сервера.
    expect(route).not.toContain("accepted = true");
  });

  it("приманка їде на сервер, а не відкидається дорогою", () => {
    expect(route).toContain('read("company")');
  });

  it("токен челенджу порожній чесно, а не підроблений", () => {
    expect(route).toContain('token: ""');
  });

  it("повернення лише на свій шлях — відкритого редіректу немає", () => {
    expect(route).toContain('if (!raw.startsWith("/") || raw.startsWith("//")) return "/";');
  });

  it("адреса клієнта передається для лічильника частоти", () => {
    expect(route).toContain("x-forwarded-for");
  });
});

describe("сторінка відповіді говорить шістьма мовами", () => {
  const locales = ["en", "uk", "de", "es", "fr", "ru"] as const;

  it("кожна мова має всі рядки", () => {
    for (const locale of locales) {
      const strings = CONTACT_FALLBACK[locale];
      expect(strings, locale).toBeDefined();
      for (const key of ["title", "sent", "blocked", "failed", "back"] as const) {
        expect(strings[key].length, `${locale}.${key}`).toBeGreaterThan(3);
      }
    }
  });

  it("відмова не вдає успіх у жодній мові", () => {
    // «Нічого не збережено» — це твердження про стан бази, і воно
    // правдиве: бекенд відмовив до запису.
    for (const locale of locales) {
      const { blocked, failed, sent } = CONTACT_FALLBACK[locale];
      expect(blocked).not.toBe(sent);
      expect(failed).not.toBe(sent);
    }
  });

  it("тексти різних мов не збігаються", () => {
    const sent = locales.map((locale) => CONTACT_FALLBACK[locale].sent);
    expect(new Set(sent).size).toBe(locales.length);
  });
});
