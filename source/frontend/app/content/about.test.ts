/**
 * «Про нас» не показує вигаданого звіту — жодною мовою.
 *
 * Там стояв `example-shop.com` із балом 62, покриттям «24 з 31» і
 * критичною знахідкою. Усе це вигадане, і саме сторінка «Про нас» —
 * те місце, де читач вирішує, чи вірити нашим числам узагалі.
 *
 * Тест читає ВИХІДНИЙ КОД сторінок, а не рендер: віджет повертався
 * одним рядком імпорту, і саме рядок треба стерегти. Справжній зразок
 * зʼявиться після розміщення — ним стане звіт Crawldy про самого себе.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const DIR = join(__dirname, "about");
const LOCALES = ["en", "uk", "de", "es", "fr", "ru"] as const;

/** Код без коментарів: пояснення про видалене саме й містить видалене. */
function code(locale: string): string {
  return readFileSync(join(DIR, `${locale}.tsx`), "utf-8")
    .replace(/\r\n/g, "\n")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("сторінка «Про нас» не містить вигаданого звіту", () => {
  it("файлів рівно шість — жодну мову не забуто", () => {
    const files = readdirSync(DIR).filter((name) => name.endsWith(".tsx"));
    expect(files.length).toBe(LOCALES.length);
  });

  for (const locale of LOCALES) {
    it(`${locale}: вигаданого домену, бала й покриття немає`, () => {
      const source = code(locale);
      expect(source).not.toContain("example-shop.com");
      expect(source).not.toContain("ScorePreview");
      expect(source).not.toMatch(/\b62\b/);
      expect(source).not.toMatch(/24\s*(of|з|von|de|из)\s*31/);
      expect(source).not.toContain("aside=");
    });
  }

  it("жодна мова не тягне за собою макет результату", () => {
    for (const locale of LOCALES) {
      const source = code(locale);
      expect(source).not.toContain("MOCK_FREE_RESULT");
      expect(source).not.toContain("mockResult");
    }
  });

  it("підпису «приклад» біля вигаданого звіту теж немає", () => {
    // Сам по собі підпис не гріх — гріхом він був поруч із числами,
    // яких ми не міряли. Разом із віджетом пішов і він.
    const labels = ["Example", "Приклад", "Пример", "Beispiel", "Ejemplo", "Exemple"];
    for (const locale of LOCALES) {
      const source = code(locale);
      for (const label of labels) {
        expect(source, `${locale}/${label}`).not.toContain(`"${label}"`);
      }
    }
  });
});
