/**
 * Політика краулерів: навчальні заборонені, пошукові та за запитом людини —
 * відкриті.
 *
 * Рішення записане давно, а в `robots.ts` його не було: групу навчальних
 * закривав `anthropic-ai` — токен, якого в документації Anthropic уже немає,
 * — тоді як чинний навчальний краулер `ClaudeBot` проходив за wildcard.
 * Правило діяло на папері, сайт віддавався.
 *
 * Тест виконує справжній продюсер і порівнює ПОВНИЙ серіалізований вивід із
 * зафіксованим «до». Різниця має бути рівно одна: додана група `ClaudeBot`.
 * Через це тест ловить не лише зникнення правки, а й будь-яку тиху зміну
 * сусідньої групи — саме те, чого не видно в діфі на один рядок.
 */

import { describe, expect, it } from "vitest";

import robots from "./robots";

type Rule = {
  userAgent?: string;
  allow?: string | string[];
  disallow?: string | string[];
};

/**
 * Вивід до правки, зафіксований дослівно.
 *
 * Порядок тут значущий не для краулерів, а для доказу: нова група дописана
 * в кінець, тож усе, що стояло раніше, мусить лишитися на своєму місці й у
 * своєму вигляді.
 */
const PRIVATE = ["/app", "/admin", "/api", "/result", "/report"];
const BEFORE: Rule[] = [
  { userAgent: "*", allow: "/", disallow: PRIVATE },
  { userAgent: "OAI-SearchBot", allow: "/", disallow: PRIVATE },
  { userAgent: "PerplexityBot", allow: "/", disallow: PRIVATE },
  { userAgent: "Applebot-Extended", allow: "/", disallow: PRIVATE },
  { userAgent: "Google-Extended", disallow: "/" },
  { userAgent: "GPTBot", disallow: "/" },
  { userAgent: "CCBot", disallow: "/" },
  { userAgent: "anthropic-ai", disallow: "/" },
  { userAgent: "Bytespider", disallow: "/" },
];

const CLAUDE_BOT: Rule = { userAgent: "ClaudeBot", disallow: "/" };

const produced = robots();
const rules = produced.rules as Rule[];

describe("вивід відрізняється від попереднього рівно однією групою", () => {
  it("повний серіалізований вивід — це «до» плюс група ClaudeBot", () => {
    expect(JSON.stringify(rules)).toBe(JSON.stringify([...BEFORE, CLAUDE_BOT]));
  });

  it("жодна з попередніх груп не змінилася", () => {
    expect(rules.slice(0, BEFORE.length)).toEqual(BEFORE);
  });

  it("груп стало рівно на одну більше", () => {
    expect(rules.length).toBe(BEFORE.length + 1);
  });
});

describe("ClaudeBot заборонено повністю", () => {
  const rule = rules.find((r) => r.userAgent === "ClaudeBot");

  it("група існує", () => {
    expect(rule).toBeDefined();
  });

  it("заборона на весь сайт і жодного дозволу", () => {
    expect(rule?.disallow).toBe("/");
    expect(rule?.allow).toBeUndefined();
  });
});

describe("пошук і запит людини лишилися відкритими", () => {
  // Це не той самий бот і не та сама політика: `Claude-SearchBot` індексує
  // для відповіді з посиланням, `Claude-User` ходить на прохання людини.
  // Заборонити їх означало б втратити саме ту видимість, заради якої все це.
  for (const agent of ["Claude-SearchBot", "Claude-User"]) {
    it(`${agent} ніде не згадано, тож діє відкритий wildcard`, () => {
      expect(JSON.stringify(rules)).not.toContain(agent);
    });
  }

  it("wildcard і далі відкриває сайт, закриваючи приватні розділи", () => {
    const wildcard = rules.find((r) => r.userAgent === "*");
    expect(wildcard?.allow).toBe("/");
    expect(wildcard?.disallow).toEqual(PRIVATE);
  });
});

describe("решта документа не зрушила", () => {
  it("мапа сайту й канонічний хост на місці", () => {
    expect(produced.sitemap).toBe("https://crawldy.ai/sitemap.xml");
    expect(produced.host).toBe("https://crawldy.ai");
  });

  it("застарілий токен не прибрано — це окреме рішення власника", () => {
    expect(rules.some((r) => r.userAgent === "anthropic-ai")).toBe(true);
  });
});
