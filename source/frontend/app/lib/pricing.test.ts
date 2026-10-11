/**
 * Видимість Monthly: рішення конфігурації, а не константи в коді.
 *
 * Захищає виправлення 2026-09-03: попередній прапорець
 * MONTHLY_CHECKOUT_READY мовчки ховав налаштований тариф — його немає.
 * Публічний тариф із живою ціною рендериться; безпрайсовий — ні;
 * непублічний бекенд взагалі не віддає (гейт на сервері).
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { monthlyToShow, perAuditAmount, pluralize, purchasable } from "./pricing";

const PRICED = {
  code: "monthly",
  sort_order: 1,
  highlighted: true,
  analyses_per_month: null,
  analyses_unlimited: true,
  presence_checks_per_month: 5,
  prices: [{ amount_minor: 500 }],
};

describe("Monthly рендериться з конфігурації", () => {
  it("публічний тариф із живою ціною показується", () => {
    expect(monthlyToShow([PRICED])).toBe(PRICED);
  });

  it("жодного жорсткого прапорця в коді, який міг би його сховати", () => {
    const source = readFileSync(join(__dirname, "pricing.ts"), "utf-8");
    expect(source.includes("MONTHLY_CHECKOUT_READY")).toBe(false);
    expect(/=\s*false/.test(source)).toBe(false);
  });

  it("безліміт і включені перевірки Presence — дані картки, не текст", () => {
    const shown = monthlyToShow([PRICED]);
    expect(shown?.analyses_unlimited).toBe(true);
    expect(shown?.presence_checks_per_month).toBe(5);
  });
});

describe("блок стоїть завжди, з конфігурації приходить число", () => {
  it("тариф без живої ціни ЛИШАЄТЬСЯ карткою — зникає лише число", () => {
    // Рішення власника 2026-09-03, що скасовує попереднє правило:
    // «Сітка не має щезати». Формати оплати — структура продукту, і
    // від наявності рядка в базі вона не залежить; сторінка із
    // заголовком «Три варіанти оплати» не сміє показувати один блок.
    const unpriced = { ...PRICED, prices: [{ amount_minor: null }] };
    expect(monthlyToShow([unpriced])).toBe(unpriced);
    // `purchasable` лишається — тепер він розводить «є число» і «числа
    // поки немає», а не «показувати чи ховати».
    expect(purchasable(unpriced)).toBe(false);
  });

  it("жодного налаштованого тарифу — картку малює сама сторінка", () => {
    // Компонент у цьому разі бере назву й опис із вмісту сторінки:
    // порожній каталог не є підставою прибрати формат оплати.
    expect(monthlyToShow([])).toBeNull();
  });

  it("підсвічений перемагає, інакше перший за порядком", () => {
    const plain = { ...PRICED, code: "a", highlighted: false, sort_order: 5 };
    const first = { ...PRICED, code: "b", highlighted: false, sort_order: 2 };
    expect(monthlyToShow([plain, PRICED])).toBe(PRICED);
    expect(monthlyToShow([plain, first])).toBe(first);
    expect(monthlyToShow([])).toBeNull();
  });
});

describe("ціна однієї перевірки в пакеті обчислюється, а не пишеться", () => {
  it("ділення з точністю валюти", () => {
    // 9.00 USD за 10 перевірок → 0.90 за перевірку.
    expect(perAuditAmount(900, 10, 2)).toBe("0.90");
    // 25.00 за 3 → 8.33: округлення до копійки, без хвоста.
    expect(perAuditAmount(2500, 3, 2)).toBe("8.33");
    // Валюта без копійок (exponent 0) лишається цілою.
    expect(perAuditAmount(1000, 3, 0)).toBe("333");
  });

  it("ділення й округлення — одним кроком, копійки не губляться", () => {
    // 10.00 за 6: наївне «округлити мінорні, потім поділити» дало б 1.66,
    // правильна відповідь — 1.67.
    expect(perAuditAmount(1000, 6, 2)).toBe("1.67");
  });
});

describe("множина обирається за правилами мови, закінчення постачає сторінка", () => {
  const uk = {
    one: "{n} повна перевірка сайту",
    few: "{n} повні перевірки сайтів",
    many: "{n} повних перевірок сайтів",
    other: "{n} повної перевірки сайтів",
  };
  const en = { one: "{n} full website analysis", other: "{n} full website analyses" };
  const fr = { one: "{n} analyse complète du site", other: "{n} analyses complètes de sites" };

  it("українська: 1 → one, 2–4 → few, 5+ і 11–14 → many", () => {
    expect(pluralize("uk", 1, uk)).toBe("1 повна перевірка сайту");
    expect(pluralize("uk", 3, uk)).toBe("3 повні перевірки сайтів");
    expect(pluralize("uk", 10, uk)).toBe("10 повних перевірок сайтів");
    expect(pluralize("uk", 11, uk)).toBe("11 повних перевірок сайтів");
    expect(pluralize("uk", 21, uk)).toBe("21 повна перевірка сайту");
  });

  it("англійська: одна форма для одиниці, інша для решти", () => {
    expect(pluralize("en", 1, en)).toBe("1 full website analysis");
    expect(pluralize("en", 10, en)).toBe("10 full website analyses");
  });

  it("французька: «один» охоплює й нуль", () => {
    expect(pluralize("fr", 0, fr)).toBe("0 analyse complète du site");
    expect(pluralize("fr", 1, fr)).toBe("1 analyse complète du site");
    expect(pluralize("fr", 2, fr)).toBe("2 analyses complètes de sites");
  });

  it("форми, якої немає, підміняє `other` — рядок не порожній", () => {
    expect(pluralize("uk", 3, { one: "{n} x", other: "{n} y" })).toBe("3 y");
  });
});
