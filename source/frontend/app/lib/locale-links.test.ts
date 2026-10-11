/**
 * Мова живе в префіксі шляху й не губиться на переходах.
 *
 * Захищає від підтвердженого бага: /uk → сторінка входу → логотип →
 * головна ставала англійською, бо логотип вів у зашитий «/». Дорога
 * назад тепер будується з мови САЙТУ (усі шість), навіть коли сама
 * форма входу існує лише en і uk.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  PUBLIC_SITE_LOCALES,
  asSiteLocale,
  missingAuthKeys,
  publicHomeHref,
} from "./i18n";
import { pathOf } from "./pages";

const LOGIN_PAGE = join(__dirname, "..", "(product)", "login", "page.tsx");

describe("мова сайту розпізнається — всі шість", () => {
  it("кожна з шести мов валідна", () => {
    for (const locale of ["en", "de", "es", "fr", "ru", "uk"] as const) {
      expect(asSiteLocale(locale)).toBe(locale);
    }
    expect(PUBLIC_SITE_LOCALES).toHaveLength(6);
  });

  it("невідоме значення не вгадується", () => {
    for (const junk of [null, "", "pl", "xx", "UK", "uk-UA", "//evil"]) {
      expect(asSiteLocale(junk as string | null)).toBeNull();
    }
  });
});

describe("дорога назад веде на головну тією самою мовою", () => {
  it("адреса головної збігається з реєстром сторінок для всіх шести мов", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      expect(publicHomeHref(locale), locale).toBe(pathOf("home", locale));
    }
  });

  it("повне коло: головна → вхід (?lang=) → логотип → та сама головна", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      // Посилання «Увійти» на публічній сторінці несе мову сайту…
      const loginHref = `/login?lang=${locale}`;
      const carried = new URLSearchParams(loginHref.split("?")[1]).get("lang");
      // …сторінка входу читає її як мову САЙТУ (не клампить до en/uk)…
      const site = asSiteLocale(carried);
      expect(site, locale).toBe(locale);
      // …і логотип повертає рівно туди, звідки прийшли.
      expect(publicHomeHref(site!), locale).toBe(pathOf("home", locale));
    }
  });

  it("вхід ↔ реєстрація — перемикання стану, а не навігація: мова на місці", () => {
    const login = readFileSync(LOGIN_PAGE, "utf-8");
    // Перемикання «вхід/створити акаунт» міняє режим, не адресу: жодного
    // переходу, який міг би загубити ?lang= чи ?next=.
    expect(login.includes("setMode(")).toBe(true);
    expect(login.includes('href="/login')).toBe(false);
  });
});

describe("форма входу існує всіма шістьма мовами (екрани 04–05)", () => {
  it("кожна мова несе ВЛАСНІ рядки форми — фолбек тут заборонений", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      expect(missingAuthKeys(locale), locale).toEqual([]);
    }
  });

  it("сторінка входу: шість мов, без заголовків, зі своєю валідацією", () => {
    const login = readFileSync(LOGIN_PAGE, "utf-8");
    // Мова форми = мова сайту, всі шість — без клампа до en/uk.
    expect(login.includes("PUBLIC_SITE_LOCALES")).toBe(true);
    expect(login.includes("formLocaleOf")).toBe(false);
    // Заголовок і підзаголовок зняті, не замінені іншими (рішення
    // власника, екрани 04–05).
    for (const gone of [
      "auth.title",
      "auth.subtitle",
      "auth.createTitle",
      "auth.createSubtitle",
    ]) {
      expect(login.includes(gone), gone).toBe(false);
    }
    // Валідація контрольована застосунком: браузерні підказки приходять
    // мовою браузера, а не мовою сторінки.
    expect(login.includes("noValidate")).toBe(true);
    for (const key of [
      "auth.emailRequired",
      "auth.emailInvalid",
      "auth.passwordRequired",
    ]) {
      expect(login.includes(key), key).toBe(true);
    }
    // У профіль зберігається лише мова, яку кабінет уміє показати.
    expect(login.includes("COMPLETE_LOCALES")).toBe(true);
    // Захист від відкритого редиректу вцілів — він переїхав у
    // `lib/landing.ts` разом із правилом «куди вести після входу»
    // (сторінка Next не може експортувати власних помічників).
    expect(login.includes("landingFor")).toBe(true);
    const landing = readFileSync(join(__dirname, "landing.ts"), "utf-8");
    expect(landing.includes('raw.startsWith("//")')).toBe(true);
  });
});

describe("мова сайту переживає кабінет", () => {
  // Підтверджений дефект: людина з /de входила в кабінет і поверталася на
  // англійську головну. Мова губилась не на виході, а на ВХОДІ: у кабінету
  // немає мовного префікса в адресі, а профіль знає лише мови, якими
  // кабінет існує (en, uk). Тепер останню публічну сторінку памʼятає
  // браузер, і всі дороги назад будуються з неї.
  const APP = join(__dirname, "..");
  const shell = readFileSync(join(APP, "components", "AppShell.tsx"), "utf-8");
  const header = readFileSync(join(APP, "components", "PublicHeader.tsx"), "utf-8");
  const appLayout = readFileSync(join(APP, "(product)", "app", "layout.tsx"), "utf-8");
  const adminLayout = readFileSync(join(APP, "(product)", "admin", "layout.tsx"), "utf-8");
  const login = readFileSync(LOGIN_PAGE, "utf-8");

  it("публічна сторінка лишає мову там, де кабінет її знайде", () => {
    expect(header).toContain("rememberSiteLocale(locale)");
  });

  it("дорога назад бере мову профілю, а порожній профіль — памʼять браузера", () => {
    // Порядок: профіль → памʼять → англійська. Зворотний порядок віз
    // власника з українським кабінетом на англійську головну лише тому,
    // що колись у цьому браузері відкривали англійську сторінку.
    const lib = readFileSync(join(APP, "lib", "site-locale.ts"), "utf-8");
    expect(lib).toContain("chosen ?? readSiteLocale() ?? \"en\"");
    expect(shell).toContain("publicHomeHref(site)");
    expect(shell).not.toContain("publicHomeHref(locale)");
    expect(adminLayout).toContain("publicHomeHref(site)");
  });

  it("шар кабінету дає СИРУ мову профілю, а не підставлену англійську", () => {
    // `useLocale()` уже підставив `en` там, де профіль порожній, і по
    // ньому не відрізнити англійця від німця. Німець із /de при цьому
    // має порожній профіль — його мову знає лише памʼять браузера.
    expect(shell).toContain("useSiteLocale(profileLocale)");
    expect(shell).not.toContain("useSiteLocale(locale)");
    expect(appLayout).toContain("profileLocale={me.user?.locale}");
    expect(adminLayout).toContain("useSiteLocale(me?.user?.locale)");
  });

  it("обидві дороги на форму входу несуть мову: і вихід, і сторож", () => {
    // Сторож спрацьовує ПІСЛЯ виходу (сесії вже немає) і перекривав
    // адресу виходу — тож мова потрібна обом, інакше перемагає та, що
    // без неї.
    for (const [name, source] of [
      ["кабінет клієнта", appLayout],
      ["адмінка", adminLayout],
    ] as const) {
      expect(source, name).toContain("/login?lang=${site}");
      expect(source, name).not.toContain('router.replace("/login")');
      expect(source, name).not.toContain('router.replace("/login?next=%2Fadmin")');
      expect(source, name).not.toContain("/login?lang=${locale}");
    }
    expect(adminLayout).toContain("/login?next=%2Fadmin&lang=${site}");
  });

  it("форма входу без ?lang= бере запамʼятовану мову, а з ?lang= — адресу", () => {
    expect(login).toContain("readSiteLocale()");
    expect(login).toContain('asSiteLocale(params.get("lang"))');
    // Адреса головніша за памʼять: памʼять читається лише коли параметра
    // немає, інакше посилання з листа мовчки відкривалося б іншою мовою.
    expect(login).toContain("if (requested === null)");
  });
});
