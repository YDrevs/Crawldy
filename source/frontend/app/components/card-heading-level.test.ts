/**
 * Рівень заголовка картки (`heading-order`).
 *
 * `CardGrid` стоїть одразу під `h1` сторінки, а назви карток були `h3` —
 * структура стрибала через рівень. У зібраних прогонах Lighthouse це
 * спрацювало на 9 з 38, а захоплення документного порядку показало
 * `h1,3,3,3,2,…` на 24 з 80 маршрутів.
 *
 * Змінено рівно одне: ім'я тега. Клас лишився символ у символ, тому розмір,
 * вага й колір беруться з тих самих утиліт, а Tailwind preflight однаково
 * скидає типографіку `h2` і `h3`. Тест стереже обидві половини: тег став
 * `h2`, і при цьому клас та текст не зрушили.
 *
 * Чого тест НЕ робить: не забороняє `h3` узагалі. Глибші заголовки в інших
 * місцях законні, і правило «жодного h3 на сторінці» було б хибним.
 */

import * as React from "react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { CardGrid } from "./sections";
import type { Card } from "./sections";

const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: unknown) => string;
};
(globalThis as unknown as { React: typeof React }).React = React;

/** Клас назви картки до правки — жоден символ не мав змінитися. */
const TITLE_CLASS = "font-medium text-primary";

const CARDS: Card[] = [
  { title: "Швидкість і UX", text: "LCP, INP, CLS та відповідь сервера." },
  {
    title: "Придатність до цитування",
    text: "Структура відповіді, авторство, контакти.",
    note: "Придатність, а не факт цитування.",
  },
];

const markup = renderToStaticMarkup(
  createElement(CardGrid, { cards: CARDS } as never),
);

describe("назва картки — заголовок другого рівня", () => {
  for (const card of CARDS) {
    it(`«${card.title}» стоїть у h2 з незмінним класом`, () => {
      expect(markup).toContain(
        `<h2 class="${TITLE_CLASS}">${card.title}</h2>`,
      );
    });

    it(`«${card.title}» більше не h3`, () => {
      expect(markup).not.toContain(`<h3 class="${TITLE_CLASS}">${card.title}`);
    });
  }

  it("заголовків рівно стільки, скільки карток", () => {
    expect((markup.match(/<h2 /g) ?? []).length).toBe(CARDS.length);
  });

  it("у сітці карток не лишилося жодного h3", () => {
    // Вузько: йдеться про розмітку САМОЇ сітки. Інші компоненти сторінки
    // вільні мати свої h3 там, де рівень справді третій.
    expect(markup).not.toContain("<h3");
  });
});

describe("видимий шар картки не зрушив", () => {
  it("текст і застереження лишилися на місці", () => {
    for (const card of CARDS) {
      expect(markup).toContain(card.text);
      if (card.note) expect(markup).toContain(card.note);
    }
  });

  it("обгортка сітки та її класи не змінилися", () => {
    expect(markup).toContain('<li class="bg-surface">');
    expect(markup).toContain("grid gap-px overflow-hidden rounded-lg");
  });

  it("порядок карток збережено", () => {
    expect(markup.indexOf(CARDS[0].title)).toBeLessThan(
      markup.indexOf(CARDS[1].title),
    );
  });
});
