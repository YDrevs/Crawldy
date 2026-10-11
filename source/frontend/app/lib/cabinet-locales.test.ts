/**
 * Кабінет клієнта шістьма мовами — і адмінка, що лишається двома.
 *
 * До 8 вересня 2026 кабінет існував лише en/uk: у німецькому,
 * іспанському й французькому словниках було по 137 ключів проти 382
 * англійських. `COMPLETE_LOCALES` був чесним запобіжником — увімкнена
 * «de» дала б наполовину англійський екран.
 *
 * Тому тут стережеться не константа, а ПРИЧИНА: жодна мова кабінету не
 * сміє мовчки падати в англійську. Константу легко змінити назад чи
 * вперед; напівперекладена мова так само легко проходить очима.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  COMPLETE_LOCALES,
  FALLBACK_LOCALE,
  LOCALE_LABEL,
  PUBLIC_SITE_LOCALES,
  publicHomeHref,
  translate,
} from "./i18n";
import { ADMIN_LOCALES } from "./admin-i18n";
import type { Locale } from "./contracts";

/**
 * Ключі кожного словника — з джерела, а не з рантайму.
 *
 * `translate()` мовчки підставляє англійську, тож через нього діру не
 * видно. Тут читається сам файл: ключ або є у словнику мови, або ні.
 */
function localeDicts(): Partial<Record<Locale, Set<string>>> {
  const src = readFileSync(join(process.cwd(), "app", "lib", "i18n.ts"), "utf8");
  const names: Locale[] = ["en", "uk", "de", "es", "fr", "ru"];
  const marks = names
    .map((n) => ({ n, i: src.indexOf(`const ${n}: Dict = {`) }))
    .filter((m) => m.i >= 0)
    .sort((a, b) => a.i - b.i);
  const out: Partial<Record<Locale, Set<string>>> = {};
  marks.forEach((m, k) => {
    const end = k + 1 < marks.length ? marks[k + 1]!.i : src.indexOf("const DICTS");
    const block = src.slice(m.i, end);
    const keys = new Set<string>();
    for (const found of block.matchAll(/^ {2}"([^"]+)":/gm)) keys.add(found[1]!);
    out[m.n] = keys;
  });
  return out;
}

/** Розділи кабінету, які людина бачить у навігації та на екранах. */
const CABINET_KEYS = [
  "nav.dashboard",
  "nav.sites",
  "nav.audits",
  "nav.presence",
  "nav.plan",
  "nav.account",
  "nav.signOut",
  "action.newAnalysis",
  "newAudit.start",
  "presence.title",
  "presence.start",
  "billing.buy",
  "billing.portal",
];

describe("кабінет: шість мов", () => {
  it("перелік повних мов кабінету збігається з мовами сайту", () => {
    expect([...COMPLETE_LOCALES].sort()).toEqual([...PUBLIC_SITE_LOCALES].sort());
    expect(COMPLETE_LOCALES).toHaveLength(6);
  });

  it("жодна мова кабінету не падає в англійський фолбек", () => {
    // Міряється НАЯВНІСТЬ ключа у словнику мови, а не відмінність
    // значення від англійського: «Dashboard» німецькою — правильний
    // німецький термін, а не підставлена англійська. Збіг значень тут
    // нічого не доводить, відсутність ключа — доводить.
    const dicts = localeDicts();
    for (const locale of COMPLETE_LOCALES) {
      const keys = dicts[locale];
      expect(keys, `немає словника для ${locale}`).toBeTruthy();
      for (const key of CABINET_KEYS) {
        expect(keys!.has(key), `${locale}: немає ключа ${key}`).toBe(true);
      }
    }
  });

  it("кожна мова кабінету має ВСІ ключі англійського словника", () => {
    const dicts = localeDicts();
    const en = dicts[FALLBACK_LOCALE]!;
    for (const locale of COMPLETE_LOCALES) {
      if (locale === FALLBACK_LOCALE) continue;
      const missing = [...en].filter((k) => !dicts[locale]!.has(k));
      expect(
        missing.length,
        `${locale}: бракує ${missing.length} ключів, напр. ${missing.slice(0, 5).join(", ")}`,
      ).toBe(0);
    }
  });

  it("кожна мова кабінету має власний підпис у перемикачі", () => {
    for (const locale of COMPLETE_LOCALES) {
      expect(LOCALE_LABEL[locale], `немає підпису для ${locale}`).toBeTruthy();
    }
    const labels = COMPLETE_LOCALES.map((l) => LOCALE_LABEL[l]);
    expect(new Set(labels).size, "підписи мов повторюються").toBe(labels.length);
  });
});

describe("мова між сайтом і кабінетом", () => {
  it("вхід із будь-якої мови сайту зберігає її в профіль", () => {
    // `login/page.tsx` зберігає мову лише якщо вона в COMPLETE_LOCALES.
    // Поки список був із двох, німець отримував англійський кабінет.
    for (const locale of PUBLIC_SITE_LOCALES) {
      expect(
        (COMPLETE_LOCALES as string[]).includes(locale),
        `${locale}: вхід не збереже мову в профіль`,
      ).toBe(true);
    }
  });

  it("дорога назад на сайт веде у ту саму мову", () => {
    expect(publicHomeHref("en")).toBe("/");
    for (const locale of PUBLIC_SITE_LOCALES) {
      if (locale === "en") continue;
      expect(publicHomeHref(locale)).toBe(`/${locale}`);
    }
  });

  it("кабінет кладе мову профілю в памʼять сайту", () => {
    // Памʼять писав ЛИШЕ публічний header, тож той, хто перемкнув мову
    // всередині кабінету, її не лишав. На виході `clear()` обнуляє
    // профіль, сторож перезапускається з порожньою памʼяттю — і німець
    // потрапляв на АНГЛІЙСЬКУ форму входу при правильному коді виходу.
    const layout = readFileSync(
      join(process.cwd(), "app", "(product)", "app", "layout.tsx"),
      "utf8",
    );
    expect(layout).toContain("rememberSiteLocale");
    expect(layout).toMatch(/rememberSiteLocale\(chosen\)/);
    // Обидва переходи на форму входу мусять нести мову.
    const redirects = layout.match(/\/login\?lang=\$\{site\}/g) ?? [];
    expect(redirects.length, "перехід на /login без мови").toBeGreaterThanOrEqual(2);
  });

  it("мова кабінету не є частиною адреси", () => {
    // Перемикання мови всередині кабінету не змінює маршрут, тож розділ,
    // сесія й дані лишаються на місці. Якби мова стояла в адресі,
    // перемикач був би переходом.
    for (const locale of COMPLETE_LOCALES) {
      expect(publicHomeHref(locale)).not.toContain("/app");
    }
  });
});

describe("адмінка лишається двомовною", () => {
  it("має рівно дві мови", () => {
    expect(ADMIN_LOCALES).toHaveLength(2);
    expect([...ADMIN_LOCALES].sort()).toEqual(["en", "uk"]);
  });

  it("жодної з чотирьох нових мов в адмінці немає", () => {
    for (const locale of ["de", "es", "fr", "ru"] as Locale[]) {
      expect(
        (ADMIN_LOCALES as string[]).includes(locale),
        `${locale} просочилась в адмінку`,
      ).toBe(false);
    }
  });
});
