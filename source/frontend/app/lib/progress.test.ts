/**
 * Індикатор ходу аудиту: числа справжні або їх немає.
 *
 * Найпростіше рішення для екрана очікування — смужка, яка повзе до 90%
 * і чекає. Вона нічого не міряє, і в продукті, який відмовляється
 * вигадувати бал за непрочитаний сайт, вона була б тією самою неправдою
 * в іншому місці. Ці перевірки стережуть саме це: частка малюється лише
 * з чисел, що прийшли з бекенда.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { plural, translate } from "./i18n";

// Закінчення рядків нормалізуються: у репозиторію `core.autocrlf=true`,
// тож багаторядкове зіставлення без цього перевіряє спосіб checkout'у.
const page = readFileSync(
  join(__dirname, "..", "(product)", "result", "page.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

// Смужка ходу й оболонка переїхали в сусідній модуль: сторінка App Router
// не може експортувати компонент, а сторож сирої помилки мусить рендерити
// саме його. Твердження про хід читають той модуль.
const screens = readFileSync(
  join(__dirname, "..", "(product)", "result", "screens.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

// Екран результату — це два модулі; вимоги про нього в цілому стосуються обох.
const feature = `${page}\n${screens}`;

describe("смужка ходу не малюється без чисел", () => {
  it("ширина береться з прочитаних сторінок, а не з таймера", () => {
    // Ніякого руху за часом: у файлі немає ані setInterval, ані
    // штучного нарощування частки.
    expect(feature).not.toContain("setInterval");
    expect(screens).toContain("read / known");
  });

  it("стадія без чисел показує підпис і жодного відсотка", () => {
    // `measured` вимагає обох чисел; без нього смужки немає взагалі.
    expect(screens).toContain(
      'typeof read === "number" && typeof known === "number" && known > 0',
    );
    expect(screens).toContain("{measured ? (");
  });

  it("порожній хід не малює нічого", () => {
    expect(screens).toContain("if (!stage) return null;");
  });

  it("частка не перевищує одиниці", () => {
    // Знаменник росте, поки краул шукає адреси, і теоретично може
    // відстати від лічильника. Смужка за межу не виходить.
    expect(screens).toContain("Math.min(1, read / known)");
  });

  it("після краулу смужки немає взагалі", () => {
    // Повна смужка при живому спінері читається як «лишилось нуль», а
    // попереду ще перевірки й бал. Число сторінок після краулу —
    // доведений факт, і подається воно фактом.
    expect(screens).toContain('stage === "crawl"');
    expect(screens).toContain("{counting ? (");
    expect(screens).toContain("free.pagesDone");
  });
});

describe("стадії названі словами, які щось означають", () => {
  const stages = [
    "discovery",
    "crawl",
    "measuring",
    "render",
    "analysis",
    "scoring",
  ] as const;

  it("кожна стадія має рядок обома мовами", () => {
    for (const locale of ["en", "uk"] as const) {
      for (const stage of stages) {
        const text = translate(locale, `free.stage.${stage}`);
        expect(text).not.toContain("free.stage");
        expect(text.length).toBeGreaterThan(3);
      }
    }
  });

  it("підписи стадій різні між собою", () => {
    for (const locale of ["en", "uk"] as const) {
      const texts = stages.map((stage) => translate(locale, `free.stage.${stage}`));
      expect(new Set(texts).size).toBe(stages.length);
    }
  });

  it("рядок про сторінки несе обидва числа", () => {
    // Форма іменника — від знаменника: «3 з 5 сторінок», «1 з 1 сторінки».
    for (const locale of ["en", "uk"] as const) {
      const text = plural(locale, "free.pagesRead", 5, { read: 3, known: 5 });
      expect(text).toContain("3");
      expect(text).toContain("5");
      expect(text).not.toContain("{");
    }
  });

  it("факт про прочитане не має знаменника", () => {
    for (const locale of ["en", "uk"] as const) {
      const text = plural(locale, "free.pagesDone", 3, { read: 3 });
      expect(text).toContain("3");
      expect(text).not.toContain("{known}");
      expect(text).not.toContain("{");
    }
  });
});

describe("технічні екрани центрують знак однаково", () => {
  it("жоден стан не малює власну шапку повз спільну оболонку", () => {
    // Оболонка існує саме тому, що центрування інакше доводиться
    // памʼятати в кожному стані окремо — і на «Читаємо сайт» його вже
    // одного разу забули. Логотип у файлі лишився рівно один: в
    // оболонці й у шапці звіту.
    const headers = feature.match(/<LogoStacked/g) ?? [];
    expect(headers.length).toBe(2);
    expect(feature).toContain('<header className="mb-10 flex justify-center">');
    expect(feature).toContain(
      '<header className="mb-10 flex flex-col items-center gap-3">',
    );
  });
});
