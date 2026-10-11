/**
 * Куди веде вхід: адміністратор — одразу в адмінку.
 *
 * Рішення власника 2026-09-05: окремий кабінет клієнта адміністраторові
 * не потрібен, тож вхід під платформною роллю відкриває службову
 * сторінку. Явний намір із `?next=` при цьому сильніший за роль —
 * інакше перервана входом покупка втратила б, куди поверталась.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { isStaff, landingFor, safeNext } from "./landing";

describe("роль визначає лише те, що малювати", () => {
  it("порожня роль — не команда", () => {
    expect(isStaff(null)).toBe(false);
    expect(isStaff(undefined)).toBe(false);
    expect(isStaff("")).toBe(false);
    expect(isStaff("STAFF")).toBe(true);
    expect(isStaff("ADMIN")).toBe(true);
  });
});

describe("ціль входу", () => {
  it("без наміру: адміністратор — в адмінку, клієнт — у кабінет", () => {
    expect(landingFor("STAFF", null)).toBe("/admin");
    expect(landingFor("ADMIN", null)).toBe("/admin");
    expect(landingFor(null, null)).toBe("/app");
    expect(landingFor(undefined, null)).toBe("/app");
  });

  it("явний намір сильніший за роль: покупка після входу продовжується", () => {
    expect(landingFor("STAFF", "/checkout?offer=pack")).toBe("/checkout?offer=pack");
    expect(landingFor(null, "/checkout?plan=monthly")).toBe("/checkout?plan=monthly");
    expect(landingFor("STAFF", "/admin")).toBe("/admin");
  });

  it("намір у службову сторінку не веде туди того, кому туди не можна", () => {
    // Підтверджений випадок: вихід із адмінки лишає `next=/admin`, і на
    // тій самій формі створюють НОВИЙ акаунт. Він потрапляв на службову
    // сторінку й бачив відмову замість кабінету.
    expect(landingFor(null, "/admin")).toBe("/app");
    expect(landingFor(undefined, "/admin?tab=prices")).toBe("/app");
    expect(landingFor("", "/admin/payment")).toBe("/app");
    // Команді той самий намір лишається.
    expect(landingFor("STAFF", "/admin/payment")).toBe("/admin/payment");
    // Клієнтські цілі не зачеплені.
    expect(landingFor(null, "/checkout?offer=pack")).toBe("/checkout?offer=pack");
  });

  it("чужа адреса не стає ціллю: форма входу не редиректор", () => {
    for (const hostile of ["https://evil.example", "//evil.example", "javascript:alert(1)"]) {
      expect(safeNext(hostile), hostile).toBe("/app");
      expect(landingFor("STAFF", hostile), hostile).toBe("/app");
    }
  });
});

describe("сторінка входу користується саме цим правилом", () => {
  const page = readFileSync(
    join(__dirname, "..", "(product)", "login", "page.tsx"),
    "utf-8",
  ).replace(/\r\n/g, "\n");

  it("обидва шляхи — і форма, і вже наявна сесія — ведуть через landingFor", () => {
    expect((page.match(/landingFor\(me\.user\?\.platform_role, requestedNext\)/g) ?? []).length).toBe(2);
    // Старого безумовного переходу в кабінет більше немає.
    expect(page).not.toContain("router.replace(next)");
  });
});
