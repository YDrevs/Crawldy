/**
 * Накладна каса Paddle — мінімум, потрібний, щоб її відкрити.
 *
 * ## Межа секретів
 *
 * Сюди потрапляє рівно одне значення провайдера — client token, який
 * Paddle і призначив для браузера. Ключ API і секрет вебхука сюди не
 * приходять ніколи: перший уміє створювати транзакції, другий —
 * підробляти події, і обидва живуть лише на сервері.
 *
 * Токен не зашитий у збірку й не читається з `NEXT_PUBLIC_*`: його
 * віддає бекенд у відповіді на відкриття каси. Так фронтенд не має
 * власної конфігурації провайдера, і переплутати оточення тут просто
 * нема чим — `environment` приходить тією ж відповіддю.
 *
 * ## Чому накладна каса, а не перехід за адресою
 *
 * Обидва шляхи офіційні. Накладна лишає людину на нашій сторінці, тож
 * закриття вікна оплати ми бачимо як подію браузера — і можемо чесно
 * сказати «оплату скасовано» замість вічного «обробляємо». Перехід за
 * адресою лишається запасним варіантом: без токена накладну не
 * відкрити, і мовчазна відмова була б гіршою за перехід.
 */

const SCRIPT_URL = "https://cdn.paddle.com/paddle/v2/paddle.js";
const SCRIPT_ID = "paddle-js";

interface PaddleCheckoutEvent {
  name?: string;
}

interface PaddleInitOptions {
  token: string;
  eventCallback?: (event: PaddleCheckoutEvent) => void;
  checkout?: { settings?: { successUrl?: string } };
}

interface PaddleGlobal {
  Environment: { set: (environment: string) => void };
  Initialize: (options: PaddleInitOptions) => void;
  Checkout: {
    open: (options: { transactionId: string }) => void;
    close?: () => void;
  };
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

/** Завантажити скрипт провайдера один раз на сторінку. */
export function loadPaddle(): Promise<PaddleGlobal> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Paddle.js живе лише в браузері"));
  }
  if (window.Paddle) return Promise.resolve(window.Paddle);

  return new Promise((resolve, reject) => {
    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    const onLoad = () => {
      if (window.Paddle) resolve(window.Paddle);
      else reject(new Error("Paddle.js завантажився без Paddle"));
    };
    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener(
      "error",
      () => reject(new Error("Paddle.js не завантажився")),
      { once: true },
    );
    if (!existing) {
      script.id = SCRIPT_ID;
      script.src = SCRIPT_URL;
      script.async = true;
      document.head.appendChild(script);
    }
  });
}

export interface PaddleSetup {
  clientToken: string;
  environment: string;
  /**
   * Куди Paddle відправить браузер після успішної оплати.
   *
   * Це єдине місце, де поняття «адреса повернення» взагалі існує:
   * серверного поля для нього в Paddle немає. Спроба покласти його в
   * `checkout.url` транзакції вже коштувала нам мовчазно зламаного
   * посилання каси — там це адреса САМОЇ сторінки оплати.
   *
   * Сторінка, на яку ми повертаємо, доказом оплати не є: вона питає
   * сервер і чекає на перевірену подію.
   */
  successUrl?: string;
  /** Людина закрила вікно оплати, не заплативши. Не помилка. */
  onClosed?: () => void;
  /** Каса відзвітувала про успішну оплату — до того, як закритись. */
  onCompleted?: () => void;
  onEvent?: (event: PaddleCheckoutEvent) => void;
}

export interface OverlayRequest extends PaddleSetup {
  transactionRef: string;
}

/**
 * Завантажити скрипт провайдера й підготувати його до роботи.
 *
 * Повертає `null`, коли токена немає: без нього Paddle.js не має чим
 * автентифікуватися, і мовчазна спроба ініціалізації дала б сторінку,
 * яка виглядає робочою й не робить нічого.
 *
 * Після цього виклику Paddle.js сам відкриває касу, якщо в адресі є
 * `_ptxn` — саме на цьому тримається сторінка default payment link.
 */
export async function initializePaddle(
  setup: PaddleSetup,
): Promise<PaddleGlobal | null> {
  if (!setup.clientToken) return null;

  const paddle = await loadPaddle();
  // Оточення ставить сервер своєю відповіддю. Значення за
  // замовчуванням у Paddle.js — бойове, тож мовчання тут означало б
  // спробу оплатити пісочничну транзакцію справжніми грошима.
  paddle.Environment.set(setup.environment === "live" ? "production" : "sandbox");

  const options: PaddleInitOptions = {
    token: setup.clientToken,
    eventCallback: (event) => {
      // `checkout.completed` приходить ПЕРЕД `checkout.closed`, коли
      // оплата пройшла: каса звітує про успіх і тоді закривається сама.
      // Слухати лише закриття означало плутати «заплатив» із «передумав».
      if (event?.name === "checkout.completed") setup.onCompleted?.();
      if (event?.name === "checkout.closed") setup.onClosed?.();
      setup.onEvent?.(event);
    },
  };
  if (setup.successUrl) {
    options.checkout = { settings: { successUrl: setup.successUrl } };
  }
  paddle.Initialize(options);
  return paddle;
}

/**
 * Відкрити накладну касу.
 *
 * Повертає `false`, коли відкрити нічим, — тоді викликач переходить за
 * адресою каси. Кидає лише те, що є справжнім збоєм.
 */
export async function openPaddleOverlay(request: OverlayRequest): Promise<boolean> {
  if (!request.transactionRef) return false;
  const paddle = await initializePaddle(request);
  if (paddle === null) return false;
  paddle.Checkout.open({ transactionId: request.transactionRef });
  return true;
}

/** Ідентифікатор транзакції з адреси default payment link, якщо він там є. */
export const PADDLE_TRANSACTION_PARAM = "_ptxn";

export function transactionRefFrom(search: string): string {
  return new URLSearchParams(search).get(PADDLE_TRANSACTION_PARAM) ?? "";
}

/**
 * Куди Paddle поверне браузер після успішної оплати.
 *
 * `undefined`, коли аудит невідомий: повертати на сторінку, яка не
 * знає, що показувати, гірше за типове завершення Paddle.
 *
 * `processing=1`, а не «готово»: сторінка результату почне питати
 * сервер одразу й покаже звіт лише тоді, коли право справді зʼявиться.
 * Повернення з каси доказом оплати не є.
 */
export function successUrlFor(origin: string, auditId: string): string | undefined {
  if (!auditId) return undefined;
  return `${origin}/result?audit=${encodeURIComponent(auditId)}&processing=1`;
}
