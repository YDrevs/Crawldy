/**
 * Службовий кабінет: межі, які мусять триматися без запуску браузера.
 *
 * Три речі перевіряються тут, бо кожну з них уже ламали або майже
 * зламали в цьому проєкті:
 *
 * 1. **Секрет не приходить у браузер.** Контракт поля секрету має
 *    `value: null`, і жодна сторінка не показує значення — лише стан.
 * 2. **Кабінет клієнта не знає про адмінку.** Пункт меню, посилання чи
 *    згадка платформної ролі в спільній оболонці — це витік службового
 *    розділу в чужий інтерфейс (рішення власника 2026-09-05).
 * 3. **Дві мови, повний паритет.** Ключ, доданий лише в один словник,
 *    показав би адміністраторові сирий ідентифікатор — саме так уже
 *    траплялося з клієнтським каталогом.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { ADMIN_LOCALES, adminKeys, adminText, initialAdminLocale } from "./admin-i18n";

const APP = join(__dirname, "..");

function source(...parts: string[]): string {
  return readFileSync(join(APP, ...parts), "utf-8").replace(/\r\n/g, "\n");
}

const PAGES = [
  ["(product)", "admin", "payment", "page.tsx"],
  ["(product)", "admin", "ai", "page.tsx"],
  ["(product)", "admin", "analytics", "page.tsx"],
  ["(product)", "admin", "testing", "page.tsx"],
];

describe("дві мови службового кабінету", () => {
  it("словники мають однакові ключі", () => {
    const [uk, en] = [adminKeys("uk"), adminKeys("en")];
    expect(new Set(uk)).toEqual(new Set(en));
    expect(uk.length).toBe(en.length);
  });

  it("кожен ключ має непорожній рядок в обох мовах", () => {
    for (const locale of ADMIN_LOCALES) {
      for (const key of adminKeys(locale)) {
        expect(adminText(locale, key).trim().length, `${locale}/${key}`).toBeGreaterThan(0);
      }
    }
  });

  it("невідомий ключ повертає сам ключ, а не порожнечу", () => {
    expect(adminText("uk", "no.such.key")).toBe("no.such.key");
  });

  it("кожна підстановка має місце, яке її заповнює", () => {
    // Підстановки в каталозі зараз немає жодної: рядок, що ховав числа
    // за `{…}`, прибрано з екрана. Якщо колись зʼявиться новий, він має
    // мати місце, яке його заповнює, — інакше клієнт побачить фігурні
    // дужки. Механізм підстановки лишається робочим і перевіряється тут
    // же: на рядку без параметрів він нічого не псує.
    // Рядок із підстановкою мусить мати місце, яке її заповнює: інакше
    // клієнт побачить фігурні дужки. Тому перевіряються ДВІ речі —
    // що жоден рядок БЕЗ параметрів їх не містить, і що кожен рядок ІЗ
    // параметрами заповнюється до кінця.
    const WITH_PARAMS: Record<string, Record<string, string | number>> = {
      "payments.credited": { quantity: 25, amount: "53.29 USD" },
      "payments.checkedAll": { paid: 1, total: 32 },
      "payments.sweepConfirm": { count: 12 },
      "payments.swept": { swept: 12 },
      "payments.sweepSummary": {
        total: 31, checked: 29, unpaid: 29, foreign: 2, paid: 0, unknown: 0,
      },
      "economics.basis": { obs: 60, prompts: 15, modes: 2, repeats: 2 },
      "economics.note": { source: "ka-dent.com.ua" },
    };
    for (const locale of ADMIN_LOCALES) {
      for (const key of adminKeys(locale)) {
        const params = WITH_PARAMS[key];
        expect(adminText(locale, key, params), `${locale}/${key}`).not.toMatch(
          /\{[a-z_]+\}/,
        );
      }
    }
    expect(adminText("uk", "nav.pricing", { unused: 1 })).toBe("Ціни");
  });

  it("початкова мова: український профіль — українська, решта — англійська", () => {
    const store: Record<string, string> = {};
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (k: string) => store[k] ?? null,
        setItem: (k: string, v: string) => {
          store[k] = v;
        },
      },
    });
    expect(initialAdminLocale("uk")).toBe("uk");
    expect(initialAdminLocale("de")).toBe("en");
    expect(initialAdminLocale(undefined)).toBe("en");
    store.crawldy_admin_locale = "uk";
    expect(initialAdminLocale("de")).toBe("uk");
    vi.unstubAllGlobals();
  });
});

describe("секрети не доходять до браузера", () => {
  it("жодна службова сторінка не читає значення секрету", () => {
    for (const page of PAGES) {
      const text = source(...page);
      // Єдиний шлях до секрету — `SecretField`, і він показує стан.
      expect(text, page.join("/")).not.toMatch(/\.secretValue|api_key.*\.value\b/);
    }
  });

  it("контракт поля описує секрет як «значення немає»", () => {
    const contracts = source("lib", "admin-api.ts");
    expect(contracts).toContain("Завжди `null` для секретів");
    expect(contracts).toContain("hint: string");
  });

  it("бекенд не кладе значення секрету у відповідь", () => {
    const runtime = readFileSync(
      join(APP, "..", "..", "backend", "app", "core", "runtime_config.py"),
      "utf-8",
    );
    expect(runtime).toContain('row["value"] = None');
    expect(runtime).toContain("def _tail");
  });
});

describe("кабінет клієнта нічого не знає про адмінку", () => {
  it("спільна оболонка не має ані посилання, ані ролі", () => {
    const shell = source("components", "AppShell.tsx");
    expect(shell).not.toContain("/admin");
    expect(shell).not.toContain("platform_role");
  });

  it("службова оболонка окрема й перевіряє роль", () => {
    const layout = source("(product)", "admin", "layout.tsx");
    expect(layout).toContain("isStaff");
    expect(layout).toContain("platform_role");
    expect(layout).not.toContain("AppShell");
  });
});

describe("навігація службового кабінету", () => {
  const shell = source("components", "AdminShell.tsx");

  it("шість розділів, і ціни лишились на своїй адресі", () => {
    const items = shell.match(/href: "\/admin[^"]*"/g) ?? [];
    expect(items.length).toBe(6);
    expect(items).toContain('href: "/admin"');
    for (const href of [
      '"/admin/payment"',
      '"/admin/ai"',
      '"/admin/payments"',
      '"/admin/analytics"',
      '"/admin/testing"',
    ]) {
      expect(shell).toContain(`href: ${href}`);
    }
  });

  it("активний розділ визначається точним збігом для кореня", () => {
    expect(shell).toContain('item.href === "/admin" ? path === "/admin"');
  });

  it("у меню акаунта є вихід, і він закриває сесію на сервері", () => {
    expect(shell).toContain('t("shell.signOut")');
    expect(shell).toContain('icon="logout"');
    const layout = source("(product)", "admin", "layout.tsx");
    expect(layout).toContain("void logout().then(");
    expect(layout).toContain("router.replace(`/login?lang=${site}`)");
  });
});

describe("тестування не вдає роботу конвеєра", () => {
  const page = source("(product)", "admin", "testing", "page.tsx");

  it("запуск іде на службовий маршрут, а не в макет", () => {
    expect(page).toContain("startTestAudit");
    expect(page).toContain("startTestPresence");
    expect(page).not.toContain("mock");
  });

  it("звіт береться з того самого маршруту, що й у клієнта", () => {
    const api = source("lib", "admin-api.ts");
    expect(api).toContain("/v1/admin/testing/audits/${id}/report");
    for (const format of ["json", "docx", "docx_owner"]) {
      expect(page).toContain(`"${format}"`);
    }
  });

  it("окремий провайдер можна запустити нарізно", () => {
    expect(page).toContain("provider: provider || null");
    expect(page).toContain("testing.allProviders");
  });
});
