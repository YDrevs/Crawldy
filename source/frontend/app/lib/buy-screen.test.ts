/**
 * Анонімна разова покупка: оплата → сайт → чотири звіти.
 *
 * Перевіряються обіцянки екрана, а не верстка. Головна з них — та, яку
 * власник назвав прямо: у цій воронці реєстрації немає ніде.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PUBLIC_SITE_LOCALES, translate } from "./i18n";

const PAGE = readFileSync(
  join(__dirname, "..", "(product)", "buy", "page.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

const ORDER = readFileSync(join(__dirname, "order.ts"), "utf-8").replace(/\r\n/g, "\n");

const CARDS = readFileSync(
  join(__dirname, "..", "components", "PricingCards.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

describe("разова покупка починається з оплати й без акаунта", () => {
  it("картка «Разова перевірка» веде в анонімну касу", () => {
    expect(CARDS).toContain("cta={{ href: buyHref, label: strings.single.cta }}");
    // Ані форми превʼю, ані дороги через кабінет для цієї картки.
    expect(CARDS).not.toContain('code: single.code }, locale)');
  });

  it("на екрані немає ані входу, ані реєстрації", () => {
    for (const forbidden of ["/login", "/signup", "register", "password"]) {
      expect(PAGE, forbidden).not.toContain(forbidden);
    }
  });

  it("каса відкривається до того, як існує аудит", () => {
    expect(PAGE).toContain("openOrder()");
    expect(ORDER).toContain('"/v1/public/orders"');
    // Сайт питають ПІСЛЯ оплати — окремим викликом, окремим станом.
    expect(PAGE).toContain("startPaidAudit(purchaseId, url)");
    expect(ORDER).toContain("/audit`");
  });

  it("каса відкривається рівно раз", () => {
    // Другий виклик — це друга транзакція у провайдера й друга
    // незавершена покупка на одну людину.
    expect(PAGE).toContain("started.current");
  });

  it("оплачена покупка переживає закриту вкладку", () => {
    // Спроможність гостя живе на вкладку; оплачена покупка так жити не
    // може — інакше закрита вкладка коштує людині грошей.
    expect(ORDER).toContain("window.localStorage");
    expect(PAGE).toContain("restoreOrderSession()");
  });

  it("повернення з каси нічого не відмикає — питаємо сервер", () => {
    expect(PAGE).toContain("readOrder(purchaseId");
    expect(PAGE).toContain("PAYMENT_ATTEMPTS");
    expect(PAGE).toContain('setPhase("notPaid")');
  });

  it("«кошти не списано» каже лише той стан, якому це підтвердили", () => {
    // Провайдер, що не відповів, — це не «ні». Один стан на обидва
    // випадки продавав би другу покупку тому, хто вже заплатив.
    expect(PAGE).toContain("state.charged === false");
    expect(PAGE).toContain('setPhase("unknown")');
    expect(PAGE).toContain("TITLES[phase]");
    expect(PAGE).toContain('notPaid: "order.notPaidTitle"');
    expect(PAGE).toContain('unknown: "order.unknownTitle"');
    for (const locale of PUBLIC_SITE_LOCALES) {
      const unknown = translate(locale, "order.unknownLead");
      expect(unknown, locale).not.toBe("order.unknownLead");
      expect(unknown, locale).not.toBe(translate(locale, "order.notPaidLead"));
    }
  });

  it("закрите вікно каси питає провайдера одразу, а не через дві хвилини", () => {
    expect(PAGE).toContain("onClosed");
    expect(PAGE).toContain("closed.current");
    expect(PAGE).toContain("CLOSED_ATTEMPTS");
  });

  it("«спробувати ще раз» відкриває касу, а не перезавантажує адресу", () => {
    expect(PAGE).toContain("onClick={() => void beginCheckout()}");
    expect(PAGE).not.toContain("window.location.assign(`/buy");
  });

  it("«забагато спроб» — відповідь про нас, а не про гроші", () => {
    // Обмежувач частоти рахує десять спроб на годину на адресу клієнта.
    // Поки 429 показувався як «оплата не пройшла», кнопка «спробувати
    // ще раз» вела в ту саму відмову — і виглядала зламаною.
    expect(PAGE).toContain("failure.status === 429");
    expect(PAGE).toContain('setPhase("throttled")');
    // Кнопки в цьому стані немає: вона привела б у ту саму стіну.
    expect(PAGE).toContain('phase === "throttled" ? null : (');
    for (const locale of PUBLIC_SITE_LOCALES) {
      const lead = translate(locale, "order.throttledLead");
      expect(lead, locale).not.toBe("order.throttledLead");
      // І тут ми не обіцяємо, що кошти не списано: ми цього не знаємо.
      expect(lead, locale).not.toBe(translate(locale, "order.notPaidLead"));
    }
  });

  it("мертвий токен у сховищі не робить кнопку вічно зламаною", () => {
    // Спроможність гостя живе сім днів. Поки протухлий токен ішов у
    // кожен запит, сервер відповідав 404, і «спробувати ще раз» било в
    // ту саму стіну — саме це власник і побачив.
    expect(ORDER).toContain("failure.status !== 404");
    expect(ORDER).toContain("openGuestSession()");
  });

  it("свіжий візит не застрягає на старій неоплаченій покупці", () => {
    // Саме це власник і побачив: зі сторінки цін одразу «оплата не
    // пройшла», бо в памʼяті лежало покинуте замовлення.
    expect(PAGE).toContain('state.state === "paid"');
    expect(PAGE).toContain("forgetOrder()");
  });

  it("знак веде на головну сайту мовою сторінки", () => {
    expect(PAGE).toContain("publicHomeHref(locale)");
    expect(PAGE).toContain('aria-label="Crawldy"');
    const checkout = readFileSync(
      join(__dirname, "..", "(product)", "checkout", "page.tsx"),
      "utf-8",
    );
    expect(checkout).toContain("publicHomeHref(locale)");
  });

  it("короткі екрани стоять посередині, а не притиснуті до верху", () => {
    expect(PAGE).toContain("min-h-screen w-full max-w-2xl flex-col justify-center");
    const result = readFileSync(
      join(__dirname, "..", "(product)", "result", "screens.tsx"),
      "utf-8",
    );
    expect(result).toContain("min-h-screen w-full max-w-2xl flex-col justify-center");
  });

  it("про присутність питають один раз — тими самими фактами", () => {
    expect(PAGE).toContain("presenceAsked.current");
    expect(PAGE).toContain("startGuestPresence(auditId");
    expect(PAGE).toContain("brand: form.brand.trim()");
    expect(PAGE).toContain("category: form.category.trim()");
  });

  it("наприкінці — чотири документи одного продукту", () => {
    expect(PAGE).toContain("docx-general");
    expect(PAGE).toContain("docx-technical");
    expect(PAGE).toContain('"general" as const');
    expect(PAGE).toContain('"technical" as const');
  });

  it("«обидві завершено» — лише коли їх справді дві", () => {
    expect(PAGE).toContain('t(presenceId ? "order.done" : "order.doneAudit")');
  });

  it("екран говорить усіма шістьма мовами сайту", () => {
    const keys = [
      "order.title",
      "order.opening",
      "order.waiting",
      "order.notPaidTitle",
      "order.notPaidLead",
      "order.retry",
      "order.lost",
      "order.formLead",
      "order.url",
      "order.language",
      "order.run",
      "order.runningAudit",
      "order.runningPresence",
      "order.done",
      "order.doneAudit",
      "order.downloads",
      "order.openReport",
      "order.auditFailed",
    ];
    const english = keys.map((key) => translate("en", key));
    for (const locale of PUBLIC_SITE_LOCALES) {
      for (const [index, key] of keys.entries()) {
        const text = translate(locale, key);
        expect(text, `${locale}/${key}`).not.toBe(key);
        if (locale === "en") continue;
        // Збіг з англійською — ознака мовчазного фолбеку.
        expect(text, `${locale}/${key} = англійська`).not.toBe(english[index]);
      }
    }
  });
});
