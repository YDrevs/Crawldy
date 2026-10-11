/**
 * Умова доступу до формату — на картці, шістьма мовами.
 *
 * Пакет і Місячний план вимагають акаунта, разова — ні. Раніше це було
 * сказано лише в договорі: покупець бачив ціну й кнопку, а про потребу
 * реєстрації дізнавався вже в касі. Тепер це підпис під переліком, і
 * тест стереже, щоб він був у КОЖНІЙ мові: пропущена локаль тут — не
 * косметика, а покупець, якого ведуть у касу без попередження.
 *
 * Керування через кабінет — навпаки, складова платних форматів, тож
 * стоїть пунктом переліку з галочкою, а не підписом.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PUBLIC_SITE_LOCALES } from "../lib/i18n";

const DIR = join(process.cwd(), "app", "content", "pricing");

function source(locale: string): string {
  return readFileSync(join(DIR, `${locale}.tsx`), "utf8");
}

/** Вміст блока `name: { ... }` до його `cta:` — межа однієї картки. */
function block(src: string, name: string): string {
  const start = src.indexOf(`${name}: {`);
  expect(start, `немає блока ${name}`).toBeGreaterThan(-1);
  const cta = src.indexOf("cta:", start);
  return src.slice(start, cta);
}

describe("ціни: умова доступу та керування — у всіх шести мовах", () => {
  it("пакет і місячний мають пункт про керування через кабінет", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const src = source(locale);
      for (const card of ["pack", "monthly"]) {
        expect(
          /manage:\s*"[^"]{15,}"/.test(block(src, card)),
          `${locale}/${card}: немає рядка manage`,
        ).toBe(true);
      }
    }
  });

  it("платні формати попереджають про акаунт, разова — про його відсутність", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const src = source(locale);
      for (const card of ["single", "pack", "monthly"]) {
        expect(
          /note:\s*"[^"]{5,}"/.test(block(src, card)),
          `${locale}/${card}: немає підпису note`,
        ).toBe(true);
      }
      // Підписи платних і безкоштовного формату не можуть збігатися:
      // вони кажуть протилежне.
      const single = block(src, "single").match(/note:\s*"([^"]+)"/)?.[1];
      const pack = block(src, "pack").match(/note:\s*"([^"]+)"/)?.[1];
      expect(single, `${locale}: підпис разової дорівнює підпису пакета`).not.toBe(
        pack,
      );
    }
  });

  it("підпис стоїть під переліком і брендованим кольором, без галочки", () => {
    const card = readFileSync(
      join(process.cwd(), "app", "components", "PricingCards.tsx"),
      "utf8",
    );
    // Одразу після закриття переліку — інакше він читався б як ціна.
    expect(card).toMatch(/<\/ul>\s*\{note \?/);
    // Клас перевіряється ЯК ТОКЕН, а не як підрядок: `text-accent-text`
    // містить `text-accent`, і підрядкова перевірка приймала б обидва.
    // Токени беруться з самого елемента підпису, тож `text-accent-text`
    // на будь-якому іншому елементі файлу перевірку не задовольнить.
    const note = card.match(
      /\{note \? \(\s*<p className="([^"]*)">\{note\}<\/p>\s*\) : null\}/,
    );
    expect(note, "елемент підпису не знайдено").not.toBeNull();
    const tokens = (note?.[1] ?? "").split(/\s+/).filter(Boolean);
    expect(tokens).toContain("text-accent-text");
    expect(tokens).not.toContain("text-accent");
  });
});
