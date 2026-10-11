/**
 * Платіжний бік інтерфейсу: що він робить і чого не робить ніколи.
 *
 * Головне твердження всього файлу: **фронтенд не вміє видати право**.
 * Він уміє попросити касу, показати стан і перепитати сервер. Усе, що
 * стосується доступу, приходить із відповіді сервера — і жоден тест
 * нижче не знаходить іншого способу отримати `unlocked: true`.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  GUEST_HEADER,
  auditIsRunning,
  ensureGuestSession,
  isSettled,
  isShortView,
  openGuestSession,
  readGuestAudit,
  startGuestAudit,
  nextPollDelayMs,
  openCheckout,
  readCheckoutConfig,
  readGuestToken,
  readPaymentStatus,
  recallAudit,
  rememberAudit,
  writeGuestToken,
  type CheckoutIntent,
  type PaymentStatus,
  type StartedAudit,
} from "./guest-payment";
import {
  initializePaddle,
  openPaddleOverlay,
  successUrlFor,
  transactionRefFrom,
} from "./paddle";
import {
  INITIAL_FLOW,
  canRetry,
  needsReconciliation,
  reduceFlow,
  shouldKeepPolling,
  type FlowState,
} from "./payment-flow";
import { PUBLIC_SITE_LOCALES, translate } from "./i18n";

// Джерело панелі оплати: перевіряється, ЩО саме рендерить кожен стан.
const panel = readFileSync(
  join(__dirname, "..", "components", "PaymentPanel.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

const AUDIT = "9c2e1b40-0000-4000-8000-00000000a001";

const INTENT: CheckoutIntent = {
  purchase_intent: "3f1b7c9a-0000-4000-8000-000000000001",
  checkout_url: "https://sandbox-pay.paddle.io/hsc_01",
  audit_id: AUDIT,
  client_token: "test_ctkn_public",
  provider: "paddle",
  transaction_ref: "txn_01",
  environment: "sandbox",
};

function stubStorage(): void {
  const store = new Map<string, string>();
  vi.stubGlobal("window", {
    sessionStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    },
  });
}

function stubFetch(response: unknown, status = 200) {
  // Підпис явний: інакше `mock.calls` типізується порожнім кортежем, і
  // перевірити адресу запиту стає неможливо без приведення через
  // `unknown` — тобто без вимикання самої перевірки.
  const spy = vi.fn(async (_url: string, _init?: RequestInit) =>
    new Response(JSON.stringify(response), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

beforeEach(() => {
  stubStorage();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── каса замовляється в бекенда ────────────────────────────────────────────

describe("замовлення каси", () => {
  it("іде на наш бекенд і несе спроможність гостя", async () => {
    writeGuestToken("guest-token-1");
    const fetchSpy = stubFetch(INTENT);

    const intent = await openCheckout(AUDIT);

    expect(intent.transaction_ref).toBe("txn_01");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toContain(`/v1/public/audits/${AUDIT}/checkout`);
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)[GUEST_HEADER]).toBe(
      "guest-token-1",
    );
  });

  it("не надсилає ані ціни, ані аудиту в тілі", async () => {
    const fetchSpy = stubFetch(INTENT);
    await openCheckout(AUDIT);

    const [, init] = fetchSpy.mock.calls[0];
    // Тіла немає взагалі: покупку створює сервер, і все, що він має
    // знати, стоїть в адресі. Дані з браузера тут стали б тим, що
    // можна підробити.
    expect(init?.body).toBeUndefined();
  });

  it("відмову провайдера показує причиною, а не порожнім екраном", async () => {
    stubFetch({ detail: { reason: "checkout.unavailable" } }, 503);
    await expect(openCheckout(AUDIT)).rejects.toThrow("checkout.unavailable");
  });
});

// ── стан оплати питається в сервера ────────────────────────────────────────

describe("стан оплати", () => {
  it("береться з бекенда, а не з адреси повернення", async () => {
    const fetchSpy = stubFetch({
      audit_id: AUDIT,
      state: "processing",
      unlocked: false,
    });

    const status = await readPaymentStatus(AUDIT);

    expect(status.unlocked).toBe(false);
    const [url] = fetchSpy.mock.calls[0];
    expect(url).toContain(`/v1/public/audits/${AUDIT}/payment`);
  });

  it("«оплачено, але ще не відкрито» не вважається завершеним", () => {
    const paidButClosed: PaymentStatus = {
      audit_id: AUDIT,
      state: "paid",
      unlocked: false,
    };
    expect(isSettled(paidButClosed)).toBe(false);
    expect(isSettled({ ...paidButClosed, unlocked: true })).toBe(true);
  });

  it("невдала оплата й повернення коштів перепитувати не треба", () => {
    for (const state of ["failed", "refunded"] as const) {
      expect(isSettled({ audit_id: AUDIT, state, unlocked: false })).toBe(true);
    }
  });

  it("інтервал опитування росте й має стелю", () => {
    expect(nextPollDelayMs(0)).toBe(1000);
    expect(nextPollDelayMs(3)).toBe(8000);
    expect(nextPollDelayMs(99)).toBe(30_000);
  });
});

// ── накладна каса провайдера ───────────────────────────────────────────────

describe("каса Paddle", () => {
  it("відкривається за транзакцією й публічним токеном", async () => {
    const open = vi.fn();
    const setEnvironment = vi.fn();
    const initialize = vi.fn();
    vi.stubGlobal("window", {
      Paddle: {
        Environment: { set: setEnvironment },
        Initialize: initialize,
        Checkout: { open },
      },
    });

    const opened = await openPaddleOverlay({
      clientToken: INTENT.client_token,
      environment: "sandbox",
      transactionRef: INTENT.transaction_ref,
    });

    expect(opened).toBe(true);
    expect(setEnvironment).toHaveBeenCalledWith("sandbox");
    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({ token: "test_ctkn_public" }),
    );
    expect(open).toHaveBeenCalledWith({ transactionId: "txn_01" });
  });

  it("бойове оточення вмикається лише коли сервер його назвав", async () => {
    const setEnvironment = vi.fn();
    vi.stubGlobal("window", {
      Paddle: {
        Environment: { set: setEnvironment },
        Initialize: vi.fn(),
        Checkout: { open: vi.fn() },
      },
    });

    await openPaddleOverlay({
      clientToken: "t",
      environment: "live",
      transactionRef: "txn_1",
    });
    expect(setEnvironment).toHaveBeenCalledWith("production");
  });

  it("без токена не відкривається — і каже про це, а не мовчить", async () => {
    vi.stubGlobal("window", {});
    const opened = await openPaddleOverlay({
      clientToken: "",
      environment: "sandbox",
      transactionRef: "txn_01",
    });
    expect(opened).toBe(false);
  });

  it("закриття вікна оплати доходить до застосунку", async () => {
    let callback: ((event: { name?: string }) => void) | undefined;
    vi.stubGlobal("window", {
      Paddle: {
        Environment: { set: vi.fn() },
        Initialize: (options: {
          eventCallback?: (event: { name?: string }) => void;
        }) => {
          callback = options.eventCallback;
        },
        Checkout: { open: vi.fn() },
      },
    });
    const onClosed = vi.fn();

    await openPaddleOverlay({
      clientToken: "t",
      environment: "sandbox",
      transactionRef: "txn_01",
      onClosed,
    });
    callback?.({ name: "checkout.closed" });
    callback?.({ name: "checkout.loaded" });

    expect(onClosed).toHaveBeenCalledTimes(1);
  });
});

// ── стан екрана ────────────────────────────────────────────────────────────

describe("потік станів", () => {
  const opened = (): FlowState =>
    reduceFlow(
      reduceFlow(INITIAL_FLOW, { type: "checkout.requested" }),
      { type: "checkout.opened" },
    );

  it("відкрита каса — це очікування, а не оплата", () => {
    const state = opened();
    expect(state.phase).toBe("processing");
    expect(state.unlocked).toBe(false);
    expect(shouldKeepPolling(state)).toBe(true);
  });

  it("право приходить лише зі слова сервера", () => {
    const state = reduceFlow(opened(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "paid", unlocked: true },
    });
    expect(state.phase).toBe("paid");
    expect(state.unlocked).toBe(true);
    expect(shouldKeepPolling(state)).toBe(false);
  });

  it("оплачено без доступу лишається «обробляємо»", () => {
    const state = reduceFlow(opened(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "paid", unlocked: false },
    });
    expect(state.phase).toBe("processing");
    expect(state.unlocked).toBe(false);
    expect(shouldKeepPolling(state)).toBe(true);
  });

  it("відмова банку не блокує наступну спробу", () => {
    const state = reduceFlow(opened(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "failed", unlocked: false },
    });
    expect(state.phase).toBe("failed");
    expect(canRetry(state)).toBe(true);
  });

  it("закрите вікно оплати — питання до сервера, а не відповідь", () => {
    // Було: `canceled` одразу, з текстом «нічого не списано». Подія
    // закриття цього не доводить — гроші могли піти, а подія провайдера
    // ще в дорозі. Тепер вікно закрите — сервер звіряє транзакцію.
    const state = reduceFlow(opened(), { type: "checkout.closed" });
    expect(state.phase).toBe("reconciling");
    expect(state.unlocked).toBe(false);
    expect(canRetry(state)).toBe(false);
  });

  it("успішна оплата не читається як «ви закрили вікно»", () => {
    // Спіймано на живій пісочниці: людина заплатила, каса закрилася
    // сама, і екран сказав «Ви закрили вікно оплати, не завершивши
    // її». Каса шле `checkout.completed` ПЕРЕД `checkout.closed`, і
    // без памʼяті про перше друге читалось як відмова.
    const completed = reduceFlow(opened(), { type: "checkout.completed" });
    expect(completed.phase).toBe("processing");
    expect(completed.completed).toBe(true);

    const afterClose = reduceFlow(completed, { type: "checkout.closed" });
    expect(afterClose.phase).toBe("processing");
    expect(afterClose.phase).not.toBe("canceled");
  });

  it("завершена каса все одно не дає доступу — його дає лише сервер", () => {
    // Головне правило редюсера не має винятків: `completed` пояснює,
    // ЧОМУ закрилось вікно, і нічого не каже про гроші.
    const completed = reduceFlow(opened(), { type: "checkout.completed" });
    expect(completed.unlocked).toBe(false);
    expect(reduceFlow(completed, { type: "checkout.closed" }).unlocked).toBe(false);
  });

  it("памʼять про завершену касу переживає відповідь сервера", () => {
    // Сервер ще не бачив події провайдера й каже «processing». Якщо
    // після цього закрити вікно, стан не має впасти в «скасовано».
    const completed = reduceFlow(opened(), { type: "checkout.completed" });
    const asked = reduceFlow(completed, {
      type: "server.said",
      status: { audit_id: AUDIT, state: "processing", unlocked: false },
    });
    expect(asked.completed).toBe(true);
    expect(reduceFlow(asked, { type: "checkout.closed" }).phase).toBe("processing");
  });

  it("закриття вікна не скасовує вже підтверджену оплату", () => {
    const paid = reduceFlow(opened(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "paid", unlocked: true },
    });
    const afterClose = reduceFlow(paid, { type: "checkout.closed" });
    expect(afterClose.phase).toBe("paid");
    expect(afterClose.unlocked).toBe(true);
  });

  it("повернення коштів закриває доступ і лишає шлях назад", () => {
    const state = reduceFlow(opened(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "refunded", unlocked: false },
    });
    expect(state.phase).toBe("refunded");
    expect(state.unlocked).toBe(false);
  });

  it("жодна дія, крім слова сервера, не вмикає доступ", () => {
    const actions = [
      { type: "checkout.requested" },
      { type: "checkout.opened" },
      { type: "checkout.unavailable" },
      { type: "checkout.completed" },
      { type: "checkout.closed" },
    ] as const;
    for (const action of actions) {
      expect(reduceFlow(INITIAL_FLOW, action).unlocked).toBe(false);
    }
  });
});

// ── воронка гостя ──────────────────────────────────────────────────────────

describe("воронка гостя", () => {
  it("сесія відкривається один раз і зберігається одразу", async () => {
    const fetchSpy = stubFetch({ token: "t-1", expires_at: "2026-09-01T00:00:00Z" });

    const token = await openGuestSession();

    expect(token).toBe("t-1");
    // Відкритий токен віддається один раз. Не зберегти його тут —
    // означає загубити аудит, за який людина вже чекає.
    expect(readGuestToken()).toBe("t-1");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toContain("/v1/public/sessions");
    expect(init?.method).toBe("POST");
  });

  it("наявна спроможність не міняється на нову", async () => {
    writeGuestToken("already-here");
    const fetchSpy = stubFetch({ token: "should-not-be-used" });

    expect(await ensureGuestSession()).toBe("already-here");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("аудит замовляється однією адресою — і більше нічим", async () => {
    writeGuestToken("t-1");
    const fetchSpy = stubFetch({
      audit_id: AUDIT,
      status: "queued",
      unlocked: false,
    });

    const started = await startGuestAudit("https://example.com");

    expect(started.audit_id).toBe(AUDIT);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toContain("/v1/public/audits");
    expect(JSON.parse(String(init?.body))).toEqual({ url: "https://example.com" });
    expect((init?.headers as Record<string, string>)[GUEST_HEADER]).toBe("t-1");
  });

  it("поки аудит працює, короткого вигляду не існує", async () => {
    const fetchSpy = stubFetch({ audit_id: AUDIT, status: "running", unlocked: false });
    const view = await readGuestAudit(AUDIT, "uk");

    // Мова їде в запиті: підписи екрана беруться з каталогу фронта, а
    // тексти знахідок — із бекенда, і без `lang` вони розходились —
    // українська сторінка показувала англійські проблеми.
    expect(String(fetchSpy.mock.calls[0][0])).toContain("lang=uk");

    // Дві форми під однією адресою — контракт бекенда. Вигадати
    // порожню оболонку з нулями означало б показати бал, якого немає.
    expect(isShortView(view)).toBe(false);
    expect(auditIsRunning(view.status)).toBe(true);
  });

  it("готовий аудит приходить коротким виглядом і опитувати його годі", async () => {
    stubFetch({
      audit_id: AUDIT,
      status: "completed",
      unlocked: false,
      overall_band: "medium",
      overall_score: 62,
    });
    const view = await readGuestAudit(AUDIT, "uk");

    expect(isShortView(view)).toBe(true);
    expect(auditIsRunning(view.status)).toBe(false);
  });

  it("невдалий аудит теж завершений — чекати на нього нема чого", () => {
    expect(auditIsRunning("failed")).toBe(false);
    expect(auditIsRunning("partial")).toBe(false);
    expect(auditIsRunning("queued")).toBe(true);
  });

  it("пропущений аудит теж завершений — інакше екран опитував би його вічно", () => {
    // `skipped` віддає бекенд, коли запуск не починався: вичерпана квота.
    // Поки його тут не було, термінальний стан виглядав як «ще працює».
    expect(auditIsRunning("skipped")).toBe(false);
  });

  it("термінальна невдача приносить клас і безпечне речення", async () => {
    stubFetch({
      audit_id: AUDIT,
      status: "failed",
      unlocked: false,
      progress: {},
      failure_class: "site_unreachable",
      failure_reason:
        "Не вдалося відкрити сайт. Перевірте адресу й доступність сайту та спробуйте ще раз.",
    });
    const view = await readGuestAudit(AUDIT, "uk");

    expect(isShortView(view)).toBe(false);
    const started = view as StartedAudit;
    expect(auditIsRunning(started.status)).toBe(false);
    expect(started.failure_class).toBe("site_unreachable");
    expect(started.failure_reason).toContain("Не вдалося відкрити сайт");
  });

  it("усі пʼять класів невдачі проходять контракт без переліку на фронті", async () => {
    // Каталогу класів тут немає навмисно: речення складає бекенд мовою
    // запиту, а другий переклад тих самих пʼяти станів розійшовся б із
    // першим. Тест перевіряє саме те, що жоден клас не потребує знання
    // про себе на цьому боці.
    const classes = [
      "site_unreachable",
      "site_blocked",
      "provider_failed",
      "internal_error",
      "cancelled",
    ];
    for (const failure_class of classes) {
      stubFetch({
        audit_id: AUDIT,
        status: "failed",
        unlocked: false,
        failure_class,
        failure_reason: `речення для ${failure_class}`,
      });
      const view = (await readGuestAudit(AUDIT, "uk")) as StartedAudit;
      expect(view.failure_class).toBe(failure_class);
      expect(view.failure_reason).toBe(`речення для ${failure_class}`);
    }
  });

  it("аудит, що виконується, не несе полів про невдачу", async () => {
    stubFetch({ audit_id: AUDIT, status: "running", unlocked: false, progress: {} });
    const view = (await readGuestAudit(AUDIT, "uk")) as StartedAudit;

    expect(auditIsRunning(view.status)).toBe(true);
    expect(view.failure_class).toBeUndefined();
    expect(view.failure_reason).toBeUndefined();
  });

  it("відповідь без полів про невдачу лишається читаною", async () => {
    // Збережений стан, старший за контракт, і аудит, що впав до його
    // появи: поля просто немає, і це не збій.
    stubFetch({ audit_id: AUDIT, status: "failed", unlocked: false });
    const view = (await readGuestAudit(AUDIT, "uk")) as StartedAudit;

    expect(auditIsRunning(view.status)).toBe(false);
    expect(view.failure_reason).toBeUndefined();
  });
});

// ── сторінка default payment link ──────────────────────────────────────────

describe("сторінка оплати", () => {
  function stubPaddle() {
    const set = vi.fn();
    const initialize = vi.fn();
    const open = vi.fn();
    const store = new Map<string, string>();
    vi.stubGlobal("window", {
      Paddle: { Environment: { set }, Initialize: initialize, Checkout: { open } },
      sessionStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => void store.set(k, v),
      },
    });
    return { set, initialize, open };
  }

  it("ідентифікатор транзакції читається з `_ptxn`", () => {
    expect(transactionRefFrom("?_ptxn=txn_01abc")).toBe("txn_01abc");
    expect(transactionRefFrom("?audit=1")).toBe("");
    expect(transactionRefFrom("")).toBe("");
  });

  it("ініціалізація готує провайдера й НЕ відкриває касу сама", async () => {
    const { set, initialize, open } = stubPaddle();

    const paddle = await initializePaddle({
      clientToken: "test_ctkn_public",
      environment: "sandbox",
    });

    expect(paddle).not.toBeNull();
    expect(set).toHaveBeenCalledWith("sandbox");
    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({ token: "test_ctkn_public" }),
    );
    // Побачивши `_ptxn`, Paddle.js відкриває касу сам. Другий виклик
    // відкрив би її двічі.
    expect(open).not.toHaveBeenCalled();
  });

  it("без токена ініціалізації немає — і це видно, а не мовчазно", async () => {
    const { initialize } = stubPaddle();
    const paddle = await initializePaddle({ clientToken: "", environment: "sandbox" });

    expect(paddle).toBeNull();
    expect(initialize).not.toHaveBeenCalled();
  });

  it("адреса повернення передається провайдеру, коли ми знаємо аудит", async () => {
    const { initialize } = stubPaddle();

    await initializePaddle({
      clientToken: "t",
      environment: "sandbox",
      successUrl: "https://crawldy.ai/result?audit=a1&processing=1",
    });

    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        checkout: {
          settings: { successUrl: "https://crawldy.ai/result?audit=a1&processing=1" },
        },
      }),
    );
  });

  it("невідомий аудит не дає вигаданої адреси повернення", () => {
    expect(successUrlFor("https://crawldy.ai", "")).toBeUndefined();
    expect(successUrlFor("https://crawldy.ai", "a1")).toBe(
      "https://crawldy.ai/result?audit=a1&processing=1",
    );
  });

  it("повернення веде в стан очікування, а не у відкритий звіт", () => {
    // `processing=1` змушує сторінку результату питати сервер. Якби тут
    // стояло «готово», повернення з каси саме по собі відмикало б звіт.
    expect(successUrlFor("https://crawldy.ai", "a1")).toContain("processing=1");
    expect(successUrlFor("https://crawldy.ai", "a1")).not.toContain("unlocked");
  });

  it("налаштування каси беруться з бекенда, а не з збірки фронтенду", async () => {
    const fetchSpy = stubFetch({
      provider: "paddle",
      environment: "sandbox",
      client_token: "test_ctkn_public",
    });

    const config = await readCheckoutConfig();

    expect(config.client_token).toBe("test_ctkn_public");
    const [url] = fetchSpy.mock.calls[0];
    expect(url).toContain("/v1/public/checkout-config");
  });

  it("аудит запамʼятовується для повернення — і лише він", () => {
    rememberAudit("audit-1");
    expect(recallAudit()).toBe("audit-1");
  });
});

// ── закрите вікно каси: звірка, а не здогад ────────────────────────────────

describe("закрите без оплати вікно звіряється з провайдером", () => {
  const opened = (): FlowState =>
    reduceFlow(
      reduceFlow(INITIAL_FLOW, { type: "checkout.requested" }),
      { type: "checkout.opened" },
    );
  const closed = (): FlowState => reduceFlow(opened(), { type: "checkout.closed" });
  const said = (state: FlowState, charged: boolean | null): FlowState =>
    reduceFlow(state, {
      type: "server.said",
      status: { audit_id: AUDIT, state: "processing", unlocked: false, charged },
    });

  it("подія закриття сама по собі не означає «не списано»", () => {
    // Раніше `checkout.closed` без `completed` одразу ставав «скасовано»
    // з текстом «нічого не списано». Подія лише каже, що вікно закрите.
    const state = closed();
    expect(state.phase).toBe("reconciling");
    expect(state.unlocked).toBe(false);
    expect(canRetry(state)).toBe(false);
    expect(shouldKeepPolling(state)).toBe(true);
    expect(needsReconciliation(state)).toBe(true);
  });

  it("гілка 1: підтверджена оплата йде в доступ і ніколи не каже «не списано»", () => {
    const state = reduceFlow(closed(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "paid", unlocked: true, charged: true },
    });
    expect(state.phase).toBe("paid");
    expect(state.unlocked).toBe(true);
    expect(canRetry(state)).toBe(false);
  });

  it("гілка 2: провайдер підтвердив «не оплачено» — скасування й повторна спроба", () => {
    const state = said(closed(), false);
    expect(state.phase).toBe("canceled");
    expect(state.unlocked).toBe(false);
    expect(canRetry(state)).toBe(true);
    expect(shouldKeepPolling(state)).toBe(false);
  });

  it("гілка 3: стан не зʼясовано — тимчасовий екран без кнопки повтору", () => {
    const state = said(closed(), null);
    expect(state.phase).toBe("reconciling");
    expect(canRetry(state)).toBe(false);
    expect(shouldKeepPolling(state)).toBe(true);
    // Наступне питання до сервера знову несе прохання звірити.
    expect(needsReconciliation(state)).toBe(true);
  });

  it("гроші пішли, подія в дорозі: чекаємо підтвердження, доступу немає", () => {
    const state = said(closed(), true);
    expect(state.phase).toBe("processing");
    expect(state.unlocked).toBe(false);
    expect(canRetry(state)).toBe(false);
    expect(needsReconciliation(state)).toBe(false);
  });

  it("невдала оплата під час звірки лишається невдалою оплатою", () => {
    const state = reduceFlow(closed(), {
      type: "server.said",
      status: { audit_id: AUDIT, state: "failed", unlocked: false, charged: false },
    });
    expect(state.phase).toBe("failed");
    expect(canRetry(state)).toBe(true);
  });

  it("звірка не дає права ні за яких відповідей", () => {
    for (const charged of [true, false, null]) {
      expect(said(closed(), charged).unlocked).toBe(false);
    }
  });

  it("повторне закриття й повторна спроба не множать станів", () => {
    // Закрити → звірити → «не списано» → закрити ще раз: той самий
    // ланцюг. Покупок клієнт не створює взагалі — він лише просить касу
    // на той самий аудит.
    const first = said(closed(), false);
    const again = reduceFlow(
      reduceFlow(first, { type: "checkout.requested" }),
      { type: "checkout.opened" },
    );
    const closedAgain = reduceFlow(again, { type: "checkout.closed" });
    expect(closedAgain.phase).toBe("reconciling");
    expect(said(closedAgain, false).phase).toBe("canceled");
  });

  it("прохання звірити їде в адресі лише коли воно потрібне", async () => {
    const fetchSpy = stubFetch({
      audit_id: AUDIT,
      state: "processing",
      unlocked: false,
      charged: false,
    });
    await readPaymentStatus(AUDIT, { reconcile: true });
    expect(String(fetchSpy.mock.calls[0][0])).toContain(
      `/v1/public/audits/${AUDIT}/payment?reconcile=true`,
    );

    await readPaymentStatus(AUDIT);
    expect(String(fetchSpy.mock.calls[1][0])).not.toContain("reconcile");
  });

  it("повторна спроба просить касу на ТОЙ САМИЙ аудит і нічого не створює сама", async () => {
    writeGuestToken("guest-token-1");
    const fetchSpy = stubFetch(INTENT);
    await openCheckout(AUDIT);
    await openCheckout(AUDIT);
    for (const call of fetchSpy.mock.calls) {
      expect(String(call[0])).toContain(`/v1/public/audits/${AUDIT}/checkout`);
      expect(call[1]?.body).toBeUndefined();
    }
    // Другого аудиту й другої транзакції клієнт не замовляє: обидві
    // спроби — один і той самий запит на той самий ідентифікатор.
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});

// ── стани оплати шістьма мовами ───────────────────────────────────────────

describe("тексти станів оплати — точні формулювання власника", () => {
  const CANCELED: Record<string, [string, string, string]> = {
    en: ["Payment not completed", "Your check has been saved. You were not charged.", "Try again"],
    uk: ["Оплату не завершено", "Вашу перевірку збережено. Кошти не списано.", "Спробувати ще раз"],
    de: ["Zahlung nicht abgeschlossen", "Ihre Prüfung wurde gespeichert. Es wurde nichts berechnet.", "Erneut versuchen"],
    es: ["Pago no completado", "Tu análisis se ha guardado. No se ha realizado ningún cargo.", "Intentarlo de nuevo"],
    fr: ["Paiement non finalisé", "Votre analyse a été enregistrée. Aucun montant n’a été débité.", "Réessayer"],
    ru: ["Оплата не завершена", "Ваша проверка сохранена. Средства не списаны.", "Попробовать снова"],
  };
  const RECONCILING: Record<string, [string, string]> = {
    en: ["Checking payment status", "Your check has been saved. Please wait while we confirm the payment status."],
    uk: ["Перевіряємо статус оплати", "Вашу перевірку збережено. Зачекайте, поки ми підтвердимо статус оплати."],
    de: ["Zahlungsstatus wird geprüft", "Ihre Prüfung wurde gespeichert. Bitte warten Sie, während wir den Zahlungsstatus bestätigen."],
    es: ["Comprobando el estado del pago", "Tu análisis se ha guardado. Espera mientras confirmamos el estado del pago."],
    fr: ["Vérification du paiement", "Votre analyse a été enregistrée. Veuillez patienter pendant que nous confirmons le statut du paiement."],
    ru: ["Проверяем статус оплаты", "Ваша проверка сохранена. Подождите, пока мы подтвердим статус оплаты."],
  };

  it("скасування: заголовок, текст і кнопка в шести мовах", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const [title, lead, cta] = CANCELED[locale];
      expect(translate(locale, "free.payment.canceled.title"), locale).toBe(title);
      expect(translate(locale, "free.payment.canceled.lead"), locale).toBe(lead);
      expect(translate(locale, "free.payment.retry"), locale).toBe(cta);
    }
  });

  it("тимчасовий стан звірки в шести мовах — і без кнопки в компоненті", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const [title, lead] = RECONCILING[locale];
      expect(translate(locale, "free.payment.reconciling.title"), locale).toBe(title);
      expect(translate(locale, "free.payment.reconciling.lead"), locale).toBe(lead);
    }
    const reconciling = panel.slice(
      panel.indexOf("function Reconciling("),
      panel.indexOf("type RetryReason"),
    );
    expect(reconciling).toContain("free.payment.reconciling.title");
    expect(reconciling).not.toContain("<Button");
    expect(reconciling).not.toContain("free.payment.retry");
  });

  it("кожен стан рендериться рівно одним компонентом і одним словником", () => {
    expect(panel).toContain('if (flow.phase === "reconciling") return <Reconciling />;');
    expect(panel).toContain('if (flow.phase === "canceled") return <Retry reason="canceled"');
    expect(panel).toContain("readPaymentStatus(auditId, { reconcile })");
    // Сирий код провайдера чи застосунку на екран не потрапляє: панель
    // не рендерить `detail`, `reason` чи текст винятку.
    // `${reason}` у ключі каталогу — інше: то вибір рядка, а не його вміст.
    expect(panel).not.toMatch(/(?<!\$)\{(detail|reason|String\(problem\)|error\.message)\}/);
  });
});
