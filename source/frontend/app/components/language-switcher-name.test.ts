/**
 * Доступна назва перемикача мови (WCAG 2.5.3, «Label in Name»).
 *
 * Кнопка показує код мови — «EN» — а звалася для зчитувача «Language».
 * Голосове керування шукає контрол за тим, що людина ЧИТАЄ на екрані, тож
 * команда «EN» не знаходила кнопку з назвою «Language». axe називає це
 * `label-content-name-mismatch`; у зібраних прогонах воно спрацювало на 35
 * з 38 (усі публічні шаблони, крім `/result`, де перемикача немає).
 *
 * Правка суто атрибутна. Саме тому тест стереже ДВІ речі одночасно:
 * що доступна назва тепер містить видимий код, і що видимий шар не
 * зрушив — жодного класу, жодного символу тексту. Перевірка «код великими
 * буквами не трапляється ніде, крім `aria-label`» ловить будь-яку спробу
 * «полагодити» це домальовуванням тексту в кнопку.
 *
 * Рендер справжній: `renderToStaticMarkup` віддає розмітку без DOM, тож
 * середовище `node` з конфігурації не міняється (той самий підхід, що в
 * `app/lib/result-screen.test.ts`).
 */

import * as React from "react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { LanguageSwitcher } from "./LanguageSwitcher";
import type { Locale } from "../lib/contracts";

// `@types/react-dom` не є залежністю проєкту, тож звичайний імпорт валив би
// `tsc --noEmit`. Оголошена форма єдиної потрібної функції; `require`
// типізований через `@types/node`, який у проєкті є.
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: unknown) => string;
};

// `.tsx` тут компілюються класичним перетворенням, без імпорту React.
(globalThis as unknown as { React: typeof React }).React = React;

/**
 * Шість мов запуску — перелічені, а не імпортовані з `i18n`.
 *
 * Тест мусить давати той самий результат і на прийнятій базі, і поверх
 * незакомічених змін власника, а `PUBLIC_SITE_LOCALES` живе у файлі, який
 * власник зараз редагує. Вимога названа шістьма кодами — вони тут і стоять.
 */
const LAUNCH_LOCALES = ["uk", "en", "de", "es", "fr", "ru"] as const;

/** Підпис кнопки приходить у компонент уже перекладеним. */
const LABEL: Record<(typeof LAUNCH_LOCALES)[number], string> = {
  uk: "Мова",
  en: "Language",
  de: "Sprache",
  es: "Idioma",
  fr: "Langue",
  ru: "Язык",
};

/** Клас кнопки до правки — жоден символ не мав змінитися. */
const TRIGGER_CLASS =
  "inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm " +
  "text-secondary transition-colors duration-fast " +
  "hover:bg-surface-sunken hover:text-primary";

function render(current: Locale, label: string, compact: boolean): string {
  return renderToStaticMarkup(
    createElement(LanguageSwitcher, {
      current,
      locales: [...LAUNCH_LOCALES] as Locale[],
      hrefFor: (locale: Locale) => `/${locale}`,
      label,
      compact,
    } as never),
  );
}

/** Розмітка самої кнопки-тригера, без списку мов під нею. */
function trigger(markup: string): string {
  const start = markup.indexOf("<button");
  const end = markup.indexOf("</button>", start);
  expect(start, "кнопка-тригер має бути в розмітці").toBeGreaterThanOrEqual(0);
  return markup.slice(start, end + "</button>".length);
}

function attr(html: string, name: string): string | null {
  return new RegExp(`${name}="([^"]*)"`).exec(html)?.[1] ?? null;
}

/** Те, що людина справді бачить: розмітка без тегів і без атрибутів. */
function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, "").trim();
}

describe("розгорнутий режим: доступна назва містить видимий код", () => {
  for (const locale of LAUNCH_LOCALES) {
    const label = LABEL[locale];
    const button = trigger(render(locale as Locale, label, false));
    const name = attr(button, "aria-label") ?? "";

    it(`${locale}: назва — «${label}» плюс видимий код`, () => {
      expect(name).toBe(`${label}: ${locale.toUpperCase()}`);
    });

    it(`${locale}: видимий код входить у доступну назву`, () => {
      expect(name).toContain(locale.toUpperCase());
    });

    it(`${locale}: видимий текст лишився кодом мови й нічим більше`, () => {
      expect(visibleText(button)).toBe(locale);
    });

    it(`${locale}: код великими не витік у видимий шар`, () => {
      // Єдине місце, де код стоїть великими буквами, — доступна назва.
      // Регістр на екрані робить CSS (`uppercase`), а не текстовий вузол.
      const withoutName = button.replace(/ aria-label="[^"]*"/, "");
      expect(withoutName).not.toContain(locale.toUpperCase());
    });

    it(`${locale}: класи кнопки не змінилися`, () => {
      expect(attr(button, "className") ?? attr(button, "class")).toBe(
        TRIGGER_CLASS,
      );
    });
  }
});

describe("стислий режим: назва лишається самим підписом", () => {
  for (const locale of LAUNCH_LOCALES) {
    const label = LABEL[locale];
    const button = trigger(render(locale as Locale, label, true));

    it(`${locale}: жодного коду в назві — його не видно й на екрані`, () => {
      expect(attr(button, "aria-label")).toBe(label);
    });

    it(`${locale}: видимого тексту в кнопці немає`, () => {
      expect(visibleText(button)).toBe("");
    });
  }
});

describe("структура кнопки не зрушила", () => {
  const button = trigger(render("uk" as Locale, LABEL.uk, false));

  it("це та сама кнопка з тим самим типом і станом розкриття", () => {
    expect(attr(button, "type")).toBe("button");
    expect(attr(button, "aria-expanded")).toBe("false");
  });

  it("обидві іконки лишилися на місці й лишилися прихованими", () => {
    expect((button.match(/<svg/g) ?? []).length).toBe(2);
    expect((button.match(/aria-hidden="true"/g) ?? []).length).toBe(2);
  });
});
