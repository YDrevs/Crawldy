/**
 * Точні заміни інвентаря E1 на сторінках сайту (затверджено 2026-09-05)
 * і маршрути, без яких de/es/fr/ru не побачили б своїх рядків.
 *
 * Сторінки: «Про нас» без неперевіреного «більшість інструментів…»;
 * іспанські «direcciones» → «dimensiones»; російське «обходит сайт
 * онлайн» без вставленого слова. Маршрути: спільний нижній CTA і форма
 * героя несуть мову сторінки на гостьовий екран, сторінка оплати
 * впізнає будь-яку з шести запамʼятованих мов.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ctaOf } from "./cta";

const CONTENT = __dirname;
const APP = join(__dirname, "..");

/** dir, locale, затверджений текст, попередній текст. */
const ROWS: [string, string, string, string][] = [
  ["website-audit", "es", "Las seis dimensiones del análisis", "Las seis direcciones del análisis"],
  ["website-audit", "es", "La puntuación se calcula solo con las dimensiones que se pudieron medir. Si faltan datos, Crawldy lo dice directamente en lugar de poner un cero.", "La puntuación se calcula solo con las direcciones que se pudieron medir. Si faltan datos, Crawldy lo dice directamente en lugar de poner un cero."],
  ["website-audit", "ru", "Crawldy проверяет сайт по шести направлениям и показывает, что стоит исправить в первую очередь. Для каждой проблемы в отчёте есть доказательства и страницы, которых она касается.", "Crawldy обходит сайт онлайн, измеряет шесть направлений и возвращает упорядоченный список: что исправить, почему это важно простыми словами и сколько это стоит в баллах. Под каждой находкой — доказательство, на котором она построена."],
  ["methodology", "es", "La puntuación general se forma solo con las dimensiones que tienen datos suficientes.", "La puntuación general se forma solo con las direcciones que tienen datos suficientes."],
  ["about", "en", "Crawldy turns the problems it finds into a clear plan. The report shows the scale of a problem, the evidence and the priority of the fix.", "Most tools return a long list of checks but do not explain what really affects the result and where to start. Crawldy turns the problems it finds into a clear plan: it shows the scale, the evidence and the priority of every fix."],
  ["about", "uk", "Crawldy перетворює знайдені проблеми на зрозумілий план дій. У звіті видно масштаб проблеми, докази та пріоритет виправлення.", "Більшість інструментів повертають довгий перелік перевірок, але не пояснюють, що справді впливає на результат і з чого починати. Crawldy перетворює знайдені проблеми на зрозумілий план дій: показує масштаб, докази та пріоритет кожного виправлення."],
  ["about", "de", "Crawldy macht aus den gefundenen Problemen einen verständlichen Plan. Im Bericht sind Umfang des Problems, Belege und Priorität der Korrektur zu sehen.", "Die meisten Werkzeuge liefern eine lange Liste von Prüfungen, erklären aber nicht, was das Ergebnis wirklich beeinflusst und womit man anfangen sollte. Crawldy macht aus den gefundenen Problemen einen verständlichen Plan: Umfang, Belege und Priorität jeder Korrektur."],
  ["about", "es", "Crawldy convierte los problemas encontrados en un plan claro. En el informe se ven la escala del problema, las pruebas y la prioridad de la corrección.", "La mayoría de las herramientas devuelven una lista larga de comprobaciones, pero no explican qué influye de verdad en el resultado ni por dónde empezar. Crawldy convierte los problemas encontrados en un plan claro: muestra la escala, las pruebas y la prioridad de cada corrección."],
  ["about", "fr", "Crawldy transforme les problèmes trouvés en un plan clair. Le rapport montre l'ampleur du problème, les preuves et la priorité de la correction.", "La plupart des outils renvoient une longue liste de vérifications sans expliquer ce qui influence vraiment le résultat ni par où commencer. Crawldy transforme les problèmes trouvés en un plan clair : il montre l'ampleur, les preuves et la priorité de chaque correction."],
  ["about", "ru", "Crawldy превращает найденные проблемы в понятный план действий. В отчёте видно масштаб проблемы, доказательства и приоритет исправления.", "Большинство инструментов возвращают длинный перечень проверок, но не объясняют, что действительно влияет на результат и с чего начинать. Crawldy превращает найденные проблемы в понятный план действий: показывает масштаб, доказательства и приоритет каждого исправления."],
];

function code(dir: string, locale: string): string {
  return readFileSync(join(CONTENT, dir, `${locale}.tsx`), "utf-8")
    .replace(/\r\n/g, "\n")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("точні заміни E1 на сторінках", () => {
  for (const [dir, locale, approved, old] of ROWS) {
    it(`${dir}/${locale}: затверджений текст є, попереднього немає`, () => {
      const text = code(dir, locale);
      expect(text).toContain(approved);
      expect(text).not.toContain(old);
    });
  }

  it("«Про нас» не порівнює з іншими інструментами жодною мовою", () => {
    for (const locale of ["en", "uk", "de", "es", "fr", "ru"]) {
      const lower = code("about", locale).toLowerCase();
      for (const phrase of [
        "most tools", "більшість інструментів", "die meisten werkzeuge",
        "la mayoría de las herramientas", "la plupart des outils", "большинство инструментов",
      ]) {
        expect(lower.includes(phrase), `${locale}: «${phrase}»`).toBe(false);
      }
    }
  });
});

describe("мова доходить до гостьового екрана й каси", () => {
  it("спільний CTA несе мову сторінки для кожної з шести мов", () => {
    expect(ctaOf("en").href).toBe("/result");
    for (const locale of ["uk", "de", "es", "fr", "ru"] as const) {
      expect(ctaOf(locale).href).toBe(`/result?lang=${locale}`);
    }
  });

  it("форма героя на головній передає мову в усіх пʼяти неанглійських версіях", () => {
    for (const locale of ["uk", "de", "es", "fr", "ru"]) {
      expect(code("home", locale), locale).toContain(`lang="${locale}"`);
    }
  });

  it("сторінка оплати впізнає будь-яку запамʼятовану мову сайту, а не лише «uk»", () => {
    const checkout = readFileSync(join(APP, "(product)", "checkout", "page.tsx"), "utf-8");
    expect(checkout).toContain("asSiteLocale(recallLocale())");
    expect(checkout).not.toContain('recallLocale() === "uk"');
  });

  it("хід аудиту рахує сторінки формами множини, а не одним закінченням", () => {
    const result = readFileSync(join(APP, "(product)", "result", "page.tsx"), "utf-8");
    // Хід переїхав у сусідній модуль; сам рядок і його форми ті самі.
    const screens = readFileSync(
      join(APP, "(product)", "result", "screens.tsx"), "utf-8");
    expect(screens).toContain('n("free.pagesRead", known, { read, known })');
    expect(screens).toContain('n("free.pagesDone", read, { read })');
    expect(result + screens).not.toContain('t("free.pagesRead")');
  });
});
