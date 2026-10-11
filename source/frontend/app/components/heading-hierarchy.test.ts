/**
 * Ієрархія заголовків розділів: рівень окремо від розміру.
 *
 * ## Що було зламано
 *
 * `Heading` рахував і тег, і кегль з одного `level`. Тому розділ, який за
 * структурою мусив бути `h2`, писався `level={3}` рівно заради меншого
 * напису — і сторінка віддавала `h1 → h3` без жодного `h2` між ними. У
 * захопленні документного порядку це видно на 24 маршрутах із 80.
 *
 * Це та сама помилка, що й у назвах карток (`card-heading-level.test.ts`),
 * але з іншого кореня: там рівень був зашитий у компоненті, тут його
 * обирав виклик — і обирав неправильно, бо іншого способу зменшити напис
 * не було.
 *
 * ## Що змінено
 *
 * `level` лишився тим, чим був: справжнім рівнем тега. Поруч зʼявився
 * `size`, і 96 викликів стали `level={2} size="lg"` — тег другого рівня з
 * виглядом третього. Жодного рядка затвердженого тексту не змінено, жоден
 * клас не зрушив.
 *
 * ## Чого тест НЕ стверджує
 *
 * Він не забороняє `h3`. Вкладений заголовок законний там, де перед ним
 * справді є `h2`: блок «читайте також» (`Related`) стоїть після розділів і
 * лишається `h3`. Правило «жодного h3 на сторінці» зламало б кожну сторінку,
 * що має цей блок, тому тут стоїть інше: кожен `h3` мусить мати `h2` перед
 * собою.
 *
 * Він не фіксує ПЕРЕЛІК сторінок. Перелік — рішення редакції, сторінки
 * приходять і зникають, і тест, який його пінує, ламався б на кожній такій
 * зміні, нічого не стережучи. Пінуються чотири виправлені родини; для решти
 * діє правило.
 *
 * Головна не рендериться поза Next: `HeroAuditForm` питає роутер застосунку.
 * Її тіло сюди не потрапляє — і окремий тест доводить, що заголовків цього
 * класу в ній немає взагалі, тож пропуск нічого не ховає.
 */

import * as React from "react";
import { createElement } from "react";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { Heading, Related } from "./sections";
import { PAGES } from "../content/registry";

const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: unknown) => string;
};
(globalThis as unknown as { React: typeof React }).React = React;

/** Класи заголовка до поділу. Жоден символ із них не мав змінитися. */
const BASE_CLASS = "font-semibold tracking-tight text-primary";
const XL = `${BASE_CLASS} text-xl`;
const LG = `${BASE_CLASS} text-lg`;

/** Форма ремонту: тег другого рівня з виглядом, який раніше давав третій. */
const REPAIRED = 'level={2} size="lg"';
/** Єдине законне входження — вкладений заголовок у `Related`. */
const NESTED = "level={3}";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const CONTENT = join(HERE, "..", "content");
const SECTIONS = join(HERE, "sections.tsx");

function tsx(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...tsx(path));
    else if (entry.name.endsWith(".tsx")) out.push(path);
  }
  return out;
}

function count(text: string, needle: string): number {
  return text.split(needle).length - 1;
}

const CONTENT_FILES = tsx(CONTENT);

/**
 * Виправлені родини: скільки розділів і яка послідовність рівнів має вийти.
 *
 * Значення не зняті з цього ж прогону: вони пораховані з виміряної базової
 * лінії HEAD плюс оголошена правка — кожен `h3` цих родин стає `h2`. Тому
 * таблиця перевіряє кандидата, а не сама себе.
 *
 * Пінуються саме ці чотири, а не весь перелік сторінок: перелік — рішення
 * редакції, сторінки приходять і зникають, і тест, який його фіксує, ламався
 * б на кожній такій зміні, нічого не стережучи. Для решти сторінок нижче
 * стоїть правило, а не перелік.
 */
const REPAIRED_FAMILIES: Record<string, { sections: number; sequence: string }> = {
  ai_visibility: { sections: 3, sequence: "1222222" },
  seo_audit: { sections: 3, sequence: "122222" },
  methodology: { sections: 5, sequence: "12222222" },
  technical_seo_audit: { sections: 5, sequence: "12222222" },
};

/**
 * Головна питає роутер застосунку і поза Next не рендериться. Пропуск
 * безпечний лише поки в ній немає заголовків цього класу — це доводиться
 * окремо, а не припускається.
 */
const NOT_RENDERABLE = "home";

const RENDERED: Record<string, string> = {};
const MARKUP: Record<string, string> = {};
for (const [key, def] of Object.entries(PAGES)) {
  if (!def || key === NOT_RENDERABLE) continue;
  for (const [locale, page] of Object.entries(def.locales)) {
    if (!page) continue;
    const markup = renderToStaticMarkup(createElement(page.Body as never));
    MARKUP[`${key}/${locale}`] = markup;
    RENDERED[`${key}/${locale}`] = [...markup.matchAll(/<h([1-6])[\s>]/g)]
      .map((m) => m[1])
      .join("");
  }
}

describe("рівень — це тег, розмір — це клас", () => {
  it("другий рівень без розміру: h2 із власним кеглем", () => {
    expect(
      renderToStaticMarkup(createElement(Heading, { title: "Т" } as never)),
    ).toContain(`<h2 class="${XL}">Т</h2>`);
  });

  it("третій рівень без розміру: h3 із власним кеглем", () => {
    expect(
      renderToStaticMarkup(
        createElement(Heading, { title: "Т", level: 3 } as never),
      ),
    ).toContain(`<h3 class="${LG}">Т</h3>`);
  });

  it("форма ремонту: h2 з виглядом, який давав третій рівень", () => {
    expect(
      renderToStaticMarkup(
        createElement(Heading, { title: "Т", level: 2, size: "lg" } as never),
      ),
    ).toContain(`<h2 class="${LG}">Т</h2>`);
  });

  it("розмір не тягне за собою рівня: h3 може бути великим", () => {
    expect(
      renderToStaticMarkup(
        createElement(Heading, { title: "Т", level: 3, size: "xl" } as never),
      ),
    ).toContain(`<h3 class="${XL}">Т</h3>`);
  });

  it("жодне значення size не малює тег іншого рівня", () => {
    for (const level of [2, 3] as const) {
      for (const size of [undefined, "xl", "lg"] as const) {
        const markup = renderToStaticMarkup(
          createElement(Heading, { title: "Т", level, size } as never),
        );
        expect(markup).toContain(`<h${level} `);
        expect(markup).not.toContain(`<h${level === 2 ? 3 : 2} `);
      }
    }
  });

  it("підводка й далі окремий абзац під заголовком", () => {
    expect(
      renderToStaticMarkup(
        createElement(Heading, { title: "Т", lead: "П", level: 2, size: "lg" } as never),
      ),
    ).toContain('<p class="mt-3 max-w-measure text-secondary">П</p>');
  });
});

describe("джерело: 97 входжень, 96 виправлених і одне законне", () => {
  const repaired = CONTENT_FILES.reduce(
    (n, f) => n + count(readFileSync(f, "utf8"), REPAIRED),
    0,
  );
  const nestedInContent = CONTENT_FILES.reduce(
    (n, f) => n + count(readFileSync(f, "utf8"), NESTED),
    0,
  );
  const sections = readFileSync(SECTIONS, "utf8");

  it("виправлених викликів рівно 96", () => {
    expect(repaired).toBe(96);
  });

  it("у сторінках вмісту не лишилося жодного level={3}", () => {
    expect(nestedInContent).toBe(0);
  });

  it("єдине level={3} живе в Related", () => {
    expect(count(sections, NESTED)).toBe(1);
    expect(sections).toContain("<Heading title={title} level={3} />");
  });

  it("разом 97 — рівно стільки, скільки було до правки", () => {
    expect(repaired + nestedInContent + count(sections, NESTED)).toBe(97);
  });

  it("виправлені виклики лежать у 24 файлах", () => {
    const files = CONTENT_FILES.filter((f) =>
      readFileSync(f, "utf8").includes(REPAIRED),
    );
    expect(files.length).toBe(24);
  });

  it("головна не містить заголовків цього класу, тож її пропуск нічого не ховає", () => {
    const home = CONTENT_FILES.filter((f) =>
      f.startsWith(join(CONTENT, NOT_RENDERABLE)),
    );
    expect(home.length).toBe(6);
    for (const file of home) {
      const text = readFileSync(file, "utf8");
      expect(count(text, NESTED)).toBe(0);
      expect(count(text, REPAIRED)).toBe(0);
    }
  });
});

describe("сторінки: після h1 не буває h3", () => {
  it("рендериться щонайменше одне тіло кожної виправленої родини", () => {
    for (const page of Object.keys(REPAIRED_FAMILIES)) {
      expect(
        Object.keys(RENDERED).filter((k) => k.startsWith(`${page}/`)).length,
      ).toBe(6);
    }
  });

  it("жодна сторінка не стрибає через рівень", () => {
    const jumps: string[] = [];
    for (const [key, seq] of Object.entries(RENDERED)) {
      const levels = [...seq].map(Number);
      for (let i = 1; i < levels.length; i += 1) {
        if (levels[i] - levels[i - 1] > 1) {
          jumps.push(`${key}: h${levels[i - 1]} → h${levels[i]}`);
        }
      }
    }
    expect(jumps).toEqual([]);
  });

  it("жодна сторінка не ставить h3 одразу після h1", () => {
    const bad = Object.entries(RENDERED)
      .filter(([, seq]) => seq.startsWith("13"))
      .map(([key]) => key);
    expect(bad).toEqual([]);
  });

  it("кожен h3 стоїть після h2, на кожній сторінці", () => {
    const orphans: string[] = [];
    for (const [key, seq] of Object.entries(RENDERED)) {
      const first3 = seq.indexOf("3");
      if (first3 === -1) continue;
      const first2 = seq.indexOf("2");
      if (first2 === -1 || first2 > first3) orphans.push(`${key}: ${seq}`);
    }
    expect(orphans).toEqual([]);
  });
});

describe("виправлені заголовки — справжні h2 з колишнім виглядом", () => {
  for (const [page, want] of Object.entries(REPAIRED_FAMILIES)) {
    for (const key of Object.keys(RENDERED).filter((k) => k.startsWith(`${page}/`))) {
      it(`${key}: послідовність рівнів ${want.sequence}`, () => {
        expect(RENDERED[key]).toBe(want.sequence);
      });

      it(`${key}: ${want.sections} заголовків у h2 з класом третього рівня`, () => {
        expect(count(MARKUP[key], `<h2 class="${LG}">`)).toBe(want.sections);
        expect(MARKUP[key]).not.toContain(`<h3 class="${LG}">`);
      });
    }
  }
});

describe("законний вкладений h3 лишився h3", () => {
  const markup = renderToStaticMarkup(
    createElement(Related, {
      title: "Читайте також",
      links: [{ href: "/a", label: "A", text: "т" }],
    } as never),
  );

  it("Related віддає h3, а не h2", () => {
    expect(markup).toContain(`<h3 class="${LG}">Читайте також</h3>`);
    expect(markup).not.toContain("<h2");
  });

  it("вигляд блоку не змінився", () => {
    expect(markup).toContain('<li class="bg-surface">');
  });

  it("у жодній виправленій родині h3 не лишилось", () => {
    for (const page of Object.keys(REPAIRED_FAMILIES)) {
      for (const key of Object.keys(RENDERED).filter((k) => k.startsWith(`${page}/`))) {
        expect(RENDERED[key]).not.toContain("3");
      }
    }
  });
});
