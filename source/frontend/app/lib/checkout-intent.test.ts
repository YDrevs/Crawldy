/**
 * Намір купити: адреса каси й розбір адреси назад.
 *
 * Правило власника (2026-09-06): зі сторінки цін кнопка веде просто в
 * касу. Кабінет на шляху до оплати не зʼявляється ні для того, хто вже
 * увійшов, ні для того, хто входить дорогою.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { afterPayment, checkoutHref, intentFrom } from "./checkout-intent";

describe("намір із адреси", () => {
  it("пропозиція й тариф розрізняються", () => {
    expect(intentFrom("?offer=pack")).toEqual({ kind: "offer", code: "pack" });
    expect(intentFrom("?plan=monthly")).toEqual({ kind: "plan", code: "monthly" });
    // Мова поруч наміру не змінює.
    expect(intentFrom("?offer=pack&lang=uk")).toEqual({ kind: "offer", code: "pack" });
  });

  it("порожній або відсутній намір — це не намір", () => {
    for (const search of ["", "?", "?lang=uk", "?offer=", "?offer=%20", "?plan="]) {
      expect(intentFrom(search), search).toBeNull();
    }
  });

  it("вхід від Paddle наміром не є: там своя транзакція", () => {
    expect(intentFrom("?_ptxn=txn_01abc")).toBeNull();
  });
});

describe("адреса каси", () => {
  it("англійська без параметра мови, решта — з ним", () => {
    expect(checkoutHref({ kind: "offer", code: "pack" }, "en")).toBe("/checkout?offer=pack");
    expect(checkoutHref({ kind: "plan", code: "monthly" }, "de")).toBe(
      "/checkout?plan=monthly&lang=de",
    );
  });

  it("код у адресі екранований", () => {
    expect(checkoutHref({ kind: "offer", code: "pack &х" }, "uk")).toBe(
      "/checkout?offer=pack%20%26%D1%85&lang=uk",
    );
  });

  it("кожна адреса читається назад тим самим розбором", () => {
    for (const locale of ["en", "uk", "de", "es", "fr", "ru"]) {
      for (const intent of [
        { kind: "offer", code: "pack" },
        { kind: "plan", code: "monthly" },
      ] as const) {
        const href = checkoutHref(intent, locale);
        expect(intentFrom(href.slice(href.indexOf("?"))), href).toEqual(intent);
      }
    }
  });
});

describe("сторінка оплати відкриває касу рівно раз", () => {
  const page = readFileSync(
    join(__dirname, "..", "(product)", "checkout", "page.tsx"),
    "utf-8",
  ).replace(/\r\n/g, "\n");

  it("сторож не дає ефекту виконатись удруге", () => {
    // Мова приходить у стан після першого рендеру (`en` → `uk`), і поки
    // вона стояла в залежностях, ефект виконувався двічі: дві транзакції
    // у провайдера й дві незавершені покупки на одну людину.
    expect(page).toContain("started.current");
    expect(page).not.toContain("}, [locale, router]);");
  });

  it("ця сторінка веде тільки в кабінет: разова сюди не приходить", () => {
    // Через `/checkout` купують те, що лягає на баланс, — пакет і
    // підписку. Разова перевірка анонімна й живе у власній воронці
    // `/buy`, без реєстрації (рішення власника 2026-09-06).
    expect(afterPayment({ kind: "offer", code: "pack" })).toBe("/app/plan");
    expect(afterPayment({ kind: "plan", code: "monthly" })).toBe("/app/plan");
    // Сторінка оплати бере адресу саме звідси, а не складає її сама.
    expect(page).toContain("afterPayment(intent)");
  });

  it("без сесії — вхід і назад у ту саму касу, без зупинки в кабінеті", () => {
    expect(page).toContain("status === 401");
    expect(page).toContain("`/login?lang=${asked}&next=${encodeURIComponent(back)}`");
    // Єдина дорога в кабінет — коли підписка вже є, тобто ЗАМІСТЬ оплати,
    // а не на шляху до неї.
    expect((page.match(/router\.replace\("\/app\/plan"\)/g) ?? []).length).toBe(1);
    expect(page).toContain("status === 409");
  });
});
