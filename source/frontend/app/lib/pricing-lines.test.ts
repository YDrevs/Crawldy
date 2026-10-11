/**
 * Рядки карток цін: склад видно завжди, числа — лише з конфігурації.
 *
 * Рішення власника 2026-09-05: відсутня роздрібна ціна не ховає, що
 * входить у пропозицію. Разова — завжди 1 + 1; пакет — одне число N і для
 * перевірок, і для Actual AI Presence, ціна за одну = загальна / N;
 * місячний план — безліміт і місячний період за означенням, окремо
 * налаштовується лише кількість Presence. Підписи без числа — затверджені
 * українські; мова без затвердженого підпису рядок пропускає, а не вигадує.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  SINGLE_ANALYSES,
  SINGLE_PRESENCE,
  monthlyLines,
  monthlyPriceText,
  packLines,
  packUnitNote,
  packUnitPrice,
  priceText,
  singleLines,
  type PricingStrings,
} from "./pricing-lines";

/** Український вміст сторінки — канонічні рядки власника. */
const UK: PricingStrings = {
  free: { heading: "Безкоштовне прев’ю", bullets: ["Загальний бал сайту"], cta: "Перевірити сайт" },
  single: {
    kind: "Разова перевірка",
    analyses: { one: "{n} повна перевірка сайту", few: "{n} повні перевірки сайтів", many: "{n} повних перевірок сайтів", other: "{n} повної перевірки сайтів" },
    scores: "Оцінки за всіма напрямами",
    issues: "Усі знайдені проблеми з доказами",
    pages: "Сторінки, яких стосується кожна проблема",
    order: "Пріоритети та порядок виправлення",
    download: "Повний звіт для завантаження",
    presence: { one: "Actual AI Presence: {n} перевірка", few: "Actual AI Presence: {n} перевірки", many: "Actual AI Presence: {n} перевірок", other: "Actual AI Presence: {n} перевірки" },
    cta: "Отримати звіт",
  },
  pack: {
    kind: "Пакет перевірок",
    analyses: { one: "{n} повна перевірка сайту", few: "{n} повні перевірки сайтів", many: "{n} повних перевірок сайтів", other: "{n} повної перевірки сайтів" },
    analysesLabel: "Повні перевірки сайтів",
    includesSingle: "Усе, що входить у разову перевірку",
    presence: { one: "Actual AI Presence: {n} перевірка", few: "Actual AI Presence: {n} перевірки", many: "Actual AI Presence: {n} перевірок", other: "Actual AI Presence: {n} перевірки" },
    presenceLabel: "Actual AI Presence",
    unitPrice: "{unit_price} за одну перевірку",
    unitPriceLabel: "Ціна за одну перевірку",
    noExpiry: "Пакет не має строку дії",
    cta: "Придбати пакет",
  },
  monthly: {
    badge: "Для регулярної роботи",
    kind: "Місячний план",
    unlimited: "Необмежена кількість повних перевірок",
    includesSingle: "Усе, що входить у разову перевірку",
    presencePerMonth: { one: "Actual AI Presence: {n} перевірка щомісяця", few: "Actual AI Presence: {n} перевірки щомісяця", many: "Actual AI Presence: {n} перевірок щомісяця", other: "Actual AI Presence: {n} перевірки щомісяця" },
    presenceLabel: "Actual AI Presence щомісяця",
    renews: "Ліміти поновлюються щомісяця",
    cta: "Підписатися",
  },
  perMonth: "/ місяць",
  priceOnRequest: "Ціна за запитом",
  loadFailed: "Не вдалося завантажити поточні пропозиції.",
};

/** Англійська — без затверджених підписів для рядків без числа (крім назви продукту). */
const EN: PricingStrings = {
  ...UK,
  single: { ...UK.single, analyses: { one: "{n} full website analysis", other: "{n} full website analyses" }, presence: { one: "Actual AI Presence: {n} check", other: "Actual AI Presence: {n} checks" } },
  pack: {
    kind: "Analysis pack",
    analyses: { one: "{n} full website analysis", other: "{n} full website analyses" },
    includesSingle: "The same full report for every analysis",
    presence: { one: "Actual AI Presence: {n} check", other: "Actual AI Presence: {n} checks" },
    presenceLabel: "Actual AI Presence",
    unitPrice: "{unit_price} per analysis",
    noExpiry: "Does not expire",
    cta: "Buy the pack",
  },
  monthly: {
    ...UK.monthly,
    unlimited: "Unlimited full website analyses",
    presencePerMonth: { one: "Actual AI Presence: {n} check per month", other: "Actual AI Presence: {n} checks per month" },
    presenceLabel: undefined,
    renews: "Allowances renew monthly",
  },
  perMonth: "/ month",
  priceOnRequest: "Price on request",
};

const PACK_10 = {
  code: "pack", display_amount_minor: 900, exponent: 2, currency: "USD",
  audit_credits: 10, presence_credits: 10,
};

describe("Разова: склад фіксований 1 + 1, динамічні лише ціна й валюта", () => {
  it("сім рядків без жодної пропозиції в каталозі", () => {
    const lines = singleLines("uk", UK);
    expect(lines).toEqual([
      "1 повна перевірка сайту",
      "Оцінки за всіма напрямами",
      "Усі знайдені проблеми з доказами",
      "Сторінки, яких стосується кожна проблема",
      "Пріоритети та порядок виправлення",
      "Повний звіт для завантаження",
      "Actual AI Presence: 1 перевірка",
    ]);
    expect(SINGLE_ANALYSES).toBe(1);
    expect(SINGLE_PRESENCE).toBe(1);
  });

  it("англійська форма однини — та сама фіксована одиниця", () => {
    const lines = singleLines("en", EN);
    expect(lines[0]).toBe("1 full website analysis");
    expect(lines[6]).toBe("Actual AI Presence: 1 check");
  });

  it("без ціни головна ціна — «ціна за запитом», склад не змінюється", () => {
    expect(priceText(null, UK.priceOnRequest)).toBe("Ціна за запитом");
    expect(priceText({ display_amount_minor: null, exponent: 2, currency: "USD" }, UK.priceOnRequest)).toBe("Ціна за запитом");
    expect(priceText({ display_amount_minor: 1500, exponent: 2, currency: "USD" }, UK.priceOnRequest)).toBe("15.00 USD");
  });
});

describe("Пакет: дві незалежні кількості", () => {
  it("з N і ціною: кількість, Presence, ціна за одну — підписом під ціною", () => {
    expect(packLines("uk", UK, PACK_10)).toEqual([
      "10 повних перевірок сайтів",
      "Усе, що входить у разову перевірку",
      "Actual AI Presence: 10 перевірок",
      "Пакет не має строку дії",
    ]);
    expect(packUnitPrice(PACK_10)).toBe("0.90 USD");
    // Вона пояснює число поруч, а не входить у перелік складу.
    expect(packUnitNote(UK, PACK_10)).toBe("0.90 USD за одну перевірку");
  });

  it("форми множини за мовою: 3 — few, 21 — one, англійська однина", () => {
    const three = { ...PACK_10, audit_credits: 3, presence_credits: 3 };
    expect(packLines("uk", UK, three)[0]).toBe("3 повні перевірки сайтів");
    expect(packLines("uk", UK, three)[2]).toBe("Actual AI Presence: 3 перевірки");
    expect(packLines("uk", UK, { ...PACK_10, audit_credits: 21 })[0]).toBe("21 повна перевірка сайту");
    const one = { ...PACK_10, audit_credits: 1, presence_credits: 1 };
    expect(packLines("en", EN, one)[0]).toBe("1 full website analysis");
    expect(packLines("en", EN, one)[2]).toBe("Actual AI Presence: 1 check");
  });

  it("кількість присутності своя: 10 перевірок і 3 присутності", () => {
    // Рівно те, заради чого власник розвів ці числа 6 вересня 2026:
    // пакет може містити менше присутностей, ніж перевірок.
    const lines = packLines("uk", UK, { ...PACK_10, presence_credits: 3 });

    expect(lines[0]).toBe("10 повних перевірок сайтів");
    expect(lines[2]).toBe("Actual AI Presence: 3 перевірки");
  });

  it("нуль присутності лишає підпис без числа, а не «0 перевірок»", () => {
    // Пакет без присутності легальний; «Actual AI Presence: 0» читалося б
    // як зіпсоване число, а не як «її тут немає».
    const lines = packLines("uk", UK, { ...PACK_10, presence_credits: 0 });

    expect(lines[2]).toBe("Actual AI Presence");
  });

  it("пакет на одну перевірку не показує ціни за одну — вона дорівнює загальній", () => {
    // Та сама умова, що працювала до 5 вересня: рядок має сенс від N ≥ 2.
    expect(packUnitPrice({ ...PACK_10, audit_credits: 1 })).toBeNull();
    expect(packUnitPrice({ ...PACK_10, audit_credits: 2 })).toBe("4.50 USD");
  });

  it("без N і ціни: значення лишаються підписами без числа", () => {
    const lines = packLines("uk", UK, null);
    expect(lines).toEqual([
      "Повні перевірки сайтів",
      "Усе, що входить у разову перевірку",
      "Actual AI Presence",
      "Пакет не має строку дії",
    ]);
    for (const line of lines) expect(line).not.toMatch(/\d/);
    // Підпис ціни за одну перевірку лишається під ціною.
    expect(packUnitNote(UK, null)).toBe("Ціна за одну перевірку");
  });

  it("є N, немає ціни: кількість числом, ціна за одну — підписом", () => {
    const pack = { ...PACK_10, display_amount_minor: null };
    const lines = packLines("uk", UK, pack);
    expect(lines[0]).toBe("10 повних перевірок сайтів");
    expect(lines[2]).toBe("Actual AI Presence: 10 перевірок");
    expect(packUnitNote(UK, pack)).toBe("Ціна за одну перевірку");
  });

  it("кількість присутності читається з каталогу, а не виводиться з N", () => {
    // До 6 вересня 2026 тут стояла протилежна вимога: поля не існувало, і
    // рядок брав N. Власник розвів числа — перевірка стереже нове правило.
    expect(packLines("uk", UK, { ...PACK_10, presence_credits: 99 })[2]).toBe(
      "Actual AI Presence: 99 перевірок",
    );
    const source = readFileSync(join(__dirname, "pricing-lines.ts"), "utf-8");
    expect(source).toContain("presence_credits");
  });

  it("мова без затвердженого підпису пропускає рядок, а не вигадує його", () => {
    const lines = packLines("en", EN, null);
    expect(lines).toEqual(["The same full report for every analysis", "Actual AI Presence", "Does not expire"]);
    // Англійська не має затвердженого підпису — рядок не вигадується.
    expect(packUnitNote(EN, null)).toBeNull();
  });
});

describe("Місячний план: безліміт і період — за означенням, Presence — з конфігурації", () => {
  it("без тарифу: безліміт, склад, Presence-підпис, поновлення", () => {
    expect(monthlyLines("uk", UK, null)).toEqual([
      "Необмежена кількість повних перевірок",
      "Усе, що входить у разову перевірку",
      "Actual AI Presence щомісяця",
      "Ліміти поновлюються щомісяця",
    ]);
    expect(monthlyPriceText(null, UK, UK.priceOnRequest)).toBe("Ціна за запитом");
  });

  it("з кількістю Presence: число у формі множини мови", () => {
    const plan = { presence_checks_per_month: 5, prices: [{ amount_minor: 500, exponent: 2, currency: "USD" }] };
    expect(monthlyLines("uk", UK, plan)[2]).toBe("Actual AI Presence: 5 перевірок щомісяця");
    expect(monthlyLines("uk", UK, { ...plan, presence_checks_per_month: 1 })[2]).toBe("Actual AI Presence: 1 перевірка щомісяця");
    expect(monthlyLines("en", EN, { ...plan, presence_checks_per_month: 2 })[2]).toBe("Actual AI Presence: 2 checks per month");
    expect(monthlyPriceText(plan, UK, UK.priceOnRequest)).toBe("5.00 USD / місяць");
  });

  it("без ціни рядки безліміту, Presence і поновлення лишаються", () => {
    const plan = { presence_checks_per_month: 3, prices: [{ amount_minor: null, exponent: 2, currency: "USD" }] };
    expect(monthlyLines("uk", UK, plan)).toHaveLength(4);
    expect(monthlyPriceText(plan, UK, UK.priceOnRequest)).toBe("Ціна за запитом");
  });

  it("стану безліміту й періоду оплати як полів не існує", () => {
    const sources = ["pricing-lines.ts", join("..", "components", "PricingCards.tsx")].map((name) =>
      readFileSync(join(__dirname, name), "utf-8"),
    );
    for (const source of sources) {
      // Поля API, яких рендер не читає. Рядок `analysesPerMonth` лишається
      // застарілим НЕОБОВʼЯЗКОВИМ ключем у типі, поки пʼять інших мов його
      // несуть; логіка місячних рядків його не використовує (перевірено вище).
      for (const field of ["analyses_unlimited", "analyses_per_month", "interval", "billing_period"]) {
        expect(source, field).not.toContain(field);
      }
    }
    // Англійська без затвердженого підпису Presence пропускає рядок, решта стоїть.
    expect(monthlyLines("en", EN, null)).toEqual([
      "Unlimited full website analyses",
      "Усе, що входить у разову перевірку",
      "Allowances renew monthly",
    ]);
  });
});
