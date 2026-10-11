/**
 * Назва таблиці правил оцінювання (S-11, axe `table-fake-caption`).
 *
 * Перший рядок таблиці — `<th colSpan={2}>`, оформлений як заголовок групи.
 * Для ока це підзаголовок, для зчитувача екрана — просто клітинка: сама
 * таблиця лишалась без назви, і axe називає це «перша дитина таблиці має
 * бути caption, а не клітинка» (3 прогони з 3 на `/methodology`).
 *
 * Правка додає СПРАВЖНІЙ `<caption>` першим елементом таблиці й ховає його
 * класом `sr-only`. Видиме не змінюється: підзаголовки, рядки, класи й
 * порядок лишаються ті самі.
 *
 * Тест рендерить справжній компонент — `renderToStaticMarkup` віддає
 * розмітку без DOM, тож середовище `node` з конфігурації не змінюється
 * (той самий підхід, що в `app/lib/result-screen.test.ts`).
 *
 * Чого тест НЕ дозволяє собі пройти дарма: кожне твердження нижче падає,
 * якщо caption прибрати, винести за межі таблиці, зробити видимим, поставити
 * не першим або підвʼязати мову до чужого рядка.
 */

import * as React from "react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { ScoringRules } from "./ScoringRules";
import facts from "../content/methodology/scoring-facts.json";
import type { Locale } from "../lib/contracts";

// `@types/react-dom` не є залежністю проєкту, тож звичайний імпорт валив би
// `tsc --noEmit`. Оголошена форма єдиної потрібної функції; `require`
// типізований через `@types/node`, який у проєкті є.
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: unknown) => string;
};

// `.tsx` тут компілюються класичним перетворенням, без імпорту React.
(globalThis as unknown as { React: typeof React }).React = React;

/** Затверджені людиною назви. Жодна не виводиться й не перекладається. */
const CAPTIONS: Record<string, string> = {
  uk: "Правила оцінювання",
  en: "Scoring rules",
  de: "Bewertungsregeln",
  es: "Reglas de puntuación",
  fr: "Règles de notation",
  ru: "Правила оценки",
};
const LOCALES = Object.keys(CAPTIONS);

function render(locale: string): string {
  return renderToStaticMarkup(
    createElement(ScoringRules, {
      locale: locale as Locale,
      strings: {
        caption: CAPTIONS[locale],
        weightsTitle: "W",
        severityTitle: "S",
        limitsTitle: "L",
        modules: {
          seo: "seo", performance: "perf", ai_ready: "ai",
          tech: "tech", llm_visibility: "llm", accessibility: "a11y",
        },
        severities: {
          critical: "c", high: "h", medium: "m", low: "l", info: "i",
        },
        minCoverageLabel: "minLabel",
        minCoverageValue: "{n} words",
        repetitionLabel: "repLabel",
        repetitionValue: "x{n}",
        shareLabel: "shareLabel",
        shareValue: "{p}",
      },
    } as never),
  );
}

const table = (html: string): string =>
  html.slice(html.indexOf("<table"), html.indexOf("</table>") + "</table>".length);

describe("таблиця правил має назву для зчитувача екрана", () => {
  const html = render("uk");

  it("caption у таблиці рівно один", () => {
    expect((html.match(/<caption/g) ?? []).length).toBe(1);
  });

  it("це справжній <caption>, а не aria-label чи прихований div", () => {
    expect(table(html)).toContain("<caption");
    // Підміна атрибутом не рахується: назву таблиці зчитувачі беруть з caption.
    expect(html).not.toContain("aria-label");
  });

  it("caption — ПЕРШИЙ елемент таблиці", () => {
    const inner = table(html).replace(/^<table[^>]*>/, "");
    expect(inner.trimStart().startsWith("<caption")).toBe(true);
    // І він справді всередині таблиці, а не поруч із нею.
    expect(html.indexOf("<caption")).toBeGreaterThan(html.indexOf("<table"));
    expect(html.indexOf("<caption")).toBeLessThan(html.indexOf("</table>"));
  });

  it("caption прихований саме класом sr-only", () => {
    const tag = /<caption class="([^"]*)"/.exec(html)?.[1];
    expect(tag).toBe("sr-only");
  });

  it("caption не порожній", () => {
    expect(/<caption[^>]*>([^<]+)<\/caption>/.exec(html)?.[1]).toBe(CAPTIONS.uk);
  });
});

describe("кожна мова подає власну назву", () => {
  for (const locale of LOCALES) {
    it(`${locale}: рівно затверджений рядок`, () => {
      const html = render(locale);
      expect(/<caption[^>]*>([^<]+)<\/caption>/.exec(html)?.[1]).toBe(
        CAPTIONS[locale],
      );
    });

    it(`${locale}: не падає в іншу мову`, () => {
      const html = render(locale);
      for (const [other, text] of Object.entries(CAPTIONS)) {
        if (other === locale) continue;
        expect(html, `${locale} показує ${other}`).not.toContain(
          `>${text}</caption>`,
        );
      }
    });
  }

  it("усі шість назв різні між собою", () => {
    expect(new Set(Object.values(CAPTIONS)).size).toBe(LOCALES.length);
  });
});

describe("видиме не зрушило", () => {
  const html = render("uk");

  it("перший рядок і далі — той самий th з colSpan і scope", () => {
    // Порядок і РЕГІСТР атрибутів — справа рендерера, а не контракту:
    // `renderToStaticMarkup` віддає `colSpan`, браузерний серіалізатор —
    // `colspan`. Перевіряється наявність обох на тому самому <th>.
    const th = (/<th[^>]*>/.exec(html)?.[0] ?? "").toLowerCase();
    expect(th).toContain('colspan="2"');
    expect(th).toContain('scope="colgroup"');
    expect((html.match(/<th[ >]/g) ?? []).length).toBe(3);
  });

  it("усі підзаголовки на місці", () => {
    for (const title of ["W", "S", "L"]) {
      expect(html).toContain(`>${title}</th>`);
    }
  });

  it("рядки даних лишились усі", () => {
    // шість напрямів + пʼять серйозностей + три обмеження
    expect((html.match(/<tr/g) ?? []).length).toBe(3 + 6 + 5 + 3);
  });

  it("обгортка й класи таблиці не змінились", () => {
    expect(html).toContain('<table class="w-full border-collapse">');
    expect(html).toContain("overflow-x-auto rounded-lg border border-border");
  });

  it("числа й далі беруться з єдиного джерела фактів", () => {
    expect(facts.severity_multipliers.critical).toBe(5);
    expect(html).toContain("×5");
  });
});
