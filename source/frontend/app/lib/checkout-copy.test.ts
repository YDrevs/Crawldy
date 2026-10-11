/**
 * Відмова каси в кабінеті — про касу, а не про аудит.
 *
 * Поки 404 з каси проходив через загальний ключ, клієнт бачив «Цей аудит
 * недоступний у цьому браузері» замість «оплата зараз недоступна», а
 * кнопки «Купити» виглядали мертвими: та сама неправильна фраза після
 * кожного натискання. Заразом: місячний план у блоці «Докупити» — така
 * сама картка, як решта, без рамки бренду, якої немає на сторінці цін.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { translate } from "./i18n";

const APP = join(__dirname, "..");

/** Скільки разів рядок трапляється у джерелі. */
function count(source: string, needle: string): number {
  return source.split(needle).length - 1;
}
const plan = readFileSync(join(APP, "(product)", "app", "plan", "page.tsx"), "utf-8").replace(
  /\r\n/g,
  "\n",
);

describe("блок «Докупити»", () => {
  it("відмова каси має власний ключ на обох шляхах — покупка й підписка", () => {
    expect((plan.match(/404: "billing\.checkoutUnavailable"/g) ?? []).length).toBe(2);
    expect(plan).not.toContain('404: "problem.generic"');
  });

  it("ключ каже про оплату, а не про аудит, обома мовами кабінету", () => {
    for (const locale of ["en", "uk"] as const) {
      const text = translate(locale, "billing.checkoutUnavailable");
      expect(text).not.toBe("billing.checkoutUnavailable");
      expect(text.toLowerCase()).not.toContain(locale === "uk" ? "аудит" : "audit");
    }
    expect(translate("uk", "billing.checkoutUnavailable")).not.toBe(
      translate("en", "billing.checkoutUnavailable"),
    );
  });

  it("місячний план не виділений рамкою бренду", () => {
    expect(plan).not.toContain("border-2 border-brand");
  });
});

describe("каса відкривається накладкою, перехід — лише запасний шлях", () => {
  // Адресу каси Paddle будує з «default payment link» акаунта, тобто з
  // адреси нашої ж сторінки оплати. На локальному стенді це
  // `https://localhost:3000/...`, чого не існує: кнопка «Купити» в
  // кабінеті йшла туди першим ходом і вмирала на ERR_SSL_PROTOCOL_ERROR,
  // поки сусідня кнопка підписки працювала — та відкривала накладку.
  const plan = readFileSync(join(APP, "(product)", "app", "plan", "page.tsx"), "utf-8");
  const checkout = readFileSync(join(APP, "(product)", "checkout", "page.tsx"), "utf-8");
  const guest = readFileSync(join(APP, "components", "PaymentPanel.tsx"), "utf-8");

  it("усі три шляхи покупки починають з накладки", () => {
    for (const [label, source] of [
      ["кабінет", plan],
      ["сторінка оплати", checkout],
      ["гостьовий екран", guest],
    ] as const) {
      expect(source, label).toContain("openPaddleOverlay(");
    }
  });

  it("перехід на адресу провайдера стоїть під умовою «накладку не відкрито»", () => {
    // Дві каси кабінету: підписка й покупка пропозиції.
    expect(count(plan, "if (!overlaid) window.location.assign(opened.url);")).toBe(2);
    // На сторінці оплати перехід стоїть у блоці: після нього йде
    // `return`, бо далі сторінка вже чекала б на касу, якої немає.
    expect(count(checkout, "if (!overlaid) {")).toBe(1);
    expect(checkout).toContain("window.location.assign(opened.url);");
    expect(guest).toContain("if (!opened) {");
    // Старого безумовного переходу немає ніде.
    expect(plan).not.toContain("window.location.href = r.url");
  });
});

describe("адмінка → Платіжний провайдер", () => {
  const payment = readFileSync(join(APP, "(product)", "admin", "payment", "page.tsx"), "utf-8");
  const pricing = readFileSync(join(APP, "(product)", "admin", "page.tsx"), "utf-8");

  it("прайс провайдера ніде не вписують: ні на сторінці провайдера, ні на закладці цін", () => {
    // Сума задається на закладці «Ціни»; прайс у провайдера публікує
    // сервер при збереженні (рішення власника 2026-09-05). Поля для
    // `pri_…` — і окремі, і «прайс разової покупки» — зникли зовсім.
    expect(existsSync(join(APP, "(product)", "admin", "payment", "prices.tsx"))).toBe(false);
    expect(payment).not.toContain("ProviderPrices");
    expect(payment).not.toContain("paddle_full_audit_price_id");
    expect(payment).not.toContain('placeholder="pri_');
    expect(pricing).not.toContain('label="Посилання на прайс"');
    expect(pricing).not.toContain('label="Провайдер"');
    expect(pricing).not.toContain("Ціна ще не привʼязана");
  });

  it("сторінка провайдера показує стан каталогу, а не поля", () => {
    expect(payment).toContain("<CataloguePanel");
    expect(payment).toContain("rows={config.catalogue ?? []}");
    expect(payment).toContain("published={config.published ?? null}");
    expect(payment).toContain("<CatalogueCheck rows={probe.catalogue}");
  });
});

/**
 * Закрите вікно каси має відповідь на кожному з трьох екранів.
 *
 * Мовчання читається як «нічого не сталося» — саме так виглядав
 * кабінет, коли людина закривала касу: жодного слова, при тому що
 * поведінка кнопок від сесії залежала. Правило одне на всі три шляхи:
 * `checkout.closed` веде до питання серверу, а не в порожнечу.
 */
describe("закрита каса не лишається без відповіді", () => {
  const plan = readFileSync(
    join(__dirname, "..", "(product)", "app", "plan", "page.tsx"),
    "utf-8",
  );
  const checkout = readFileSync(
    join(__dirname, "..", "(product)", "checkout", "page.tsx"),
    "utf-8",
  );
  const guest = readFileSync(
    join(__dirname, "..", "(product)", "buy", "page.tsx"),
    "utf-8",
  );

  it("усі три екрани слухають закриття каси", () => {
    for (const [label, source] of [
      ["кабінет", plan],
      ["сторінка оплати", checkout],
      ["гостьовий екран", guest],
    ] as const) {
      expect(source, label).toContain("onClosed:");
    }
  });

  it("«кошти не списано» каже лише підтверджений стан", () => {
    // `charged === false` — це слово провайдера. Мовчання провайдера
    // веде в інший текст, і саме цим два стани й відрізняються.
    expect(checkout).toContain("charged === false");
    expect(checkout).toContain("order.notPaidLead");
    expect(checkout).toContain("checkout.unknownLead");
  });

  it("у кабінеті просто закрите вікно нічого не пише", () => {
    // Рішення власника 2026-09-07: на робочій сторінці повідомлення
    // «кошти не списано» переказує людині її ж дію. Мовчить лише цей
    // стан — випадок, коли провайдер не відповів, лишається озвученим,
    // бо гроші могли піти.
    expect(plan).toContain("charged === false");
    expect(plan).not.toContain("order.notPaidLead");
    expect(plan).toContain("checkout.unknownLead");
  });

  it("жоден екран не чекає вічно", () => {
    // Подія про закриття може не дійти взагалі; опитування мусить мати
    // межу, після якої екран каже правду замість спінера.
    expect(checkout).toContain("CLOSED_ATTEMPTS");
    expect(plan).toContain("CLOSED_ATTEMPTS");
    expect(guest).toContain("CLOSED_ATTEMPTS");
  });
});
