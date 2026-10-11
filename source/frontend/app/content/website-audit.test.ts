/**
 * «Що перевіряємо»: короткий заголовок без рекламної другої частини.
 *
 * Раніше H1 був «Перевірка сайту для пошуку та ШІ: один звіт про те, що
 * справді не так» — заголовок із двокрапкою й приклеєним твердженням.
 * Власник затвердив коротку форму, і видалена частина не мала переїхати
 * в підводку.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const DIR = join(__dirname, "website-audit");
const LOCALES = ["en", "uk", "de", "es", "fr", "ru"] as const;

const H1: Record<string, string> = {
  en: "Website analysis for Search and AI",
  uk: "Перевірка сайту для пошуку та ШІ",
  de: "Website-Analyse für Suche und KI",
  es: "Análisis del sitio web para buscadores e IA",
  fr: "Analyse de site pour la recherche et l’IA",
  ru: "Проверка сайта для поиска и ИИ",
};

function code(locale: string): string {
  return readFileSync(join(DIR, `${locale}.tsx`), "utf-8")
    .replace(/\r\n/g, "\n")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("заголовок «Що перевіряємо» короткий і точний", () => {
  for (const locale of LOCALES) {
    it(`${locale}: H1 у герої та в метаданих збігається з погодженим`, () => {
      const source = code(locale);
      expect(source).toContain(`title=${JSON.stringify(H1[locale])}`);
      expect(source).toContain(`h1: ${JSON.stringify(H1[locale])}`);
    });

    it(`${locale}: видалена частина не переїхала в підводку`, () => {
      const source = code(locale).toLowerCase();
      for (const clause of [
        "really wrong", "actually wrong", "справді не так", "wirklich nicht stimmt",
        "de verdad falla", "vraiment pas", "на самом деле не так",
      ]) {
        expect(source, clause).not.toContain(clause);
      }
      // Заголовок без двокрапки: H1 із приклеєним твердженням — саме та
      // форма, якої більше немає.
      expect(H1[locale]).not.toContain(":");
    });
  }
});
