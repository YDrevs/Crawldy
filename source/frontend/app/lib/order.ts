/**
 * Разова покупка, що починається з оплати. Без акаунта.
 *
 * ## Чому окремий модуль
 *
 * `guest-payment.ts` описує воронку «спершу превʼю»: там аудит уже є, і
 * все адресується його номером. Тут навпаки — аудиту ще немає, а
 * покупка вже є, і саме вона тримає всю нитку. Змішувати два порядки в
 * одному модулі означало б плутати «оплата за цей аудит» з «аудит за цю
 * оплату».
 *
 * ## Чому пам'ять довговічна
 *
 * Спроможність гостя живе в `sessionStorage` — на вкладку, і це
 * правильно для превʼю: закрив вкладку, почав спочатку, нічого не
 * втратив. Для оплаченої покупки те саме означало б втрату грошей:
 * людина заплатила, закрила вкладку до того, як назвала сайт, і
 * повернутися вже нікуди. Тому замовлення (номер покупки + токен)
 * лягає в `localStorage` і переживає вкладку. Правом воно не є: сервер
 * однаково звіряє покупку з організацією токена, а токен живе сім днів.
 */

import { API_URL, ApiError, UNREACHABLE } from "./api";
import {
  GUEST_HEADER,
  ensureGuestSession,
  openGuestSession,
  readGuestToken,
  writeGuestToken,
} from "./guest-payment";

/** Замовлення, яке пережило вкладку. */
const ORDER_KEY = "crawldy.order";

export interface RememberedOrder {
  purchaseId: string;
  token: string;
}

export function rememberOrder(order: RememberedOrder): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ORDER_KEY, JSON.stringify(order));
  } catch {
    // Приватний режим забороняє сховище. Оплата від цього не ламається —
    // лише повернення після закритої вкладки.
  }
}

export function recallOrder(): RememberedOrder | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ORDER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<RememberedOrder>;
    if (!parsed.purchaseId || !parsed.token) return null;
    return { purchaseId: parsed.purchaseId, token: parsed.token };
  } catch {
    return null;
  }
}

export function forgetOrder(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ORDER_KEY);
  } catch {
    /* див. вище */
  }
}

/**
 * Повернути спроможність, якою відкривали цю касу.
 *
 * Токен вкладки міг зникнути разом із вкладкою; довговічний запис його
 * відновлює. Нового не створюємо: нова організація не має ані покупки,
 * ані кредитів, і людина побачила б «оплати не було» після оплати.
 */
export function restoreOrderSession(): RememberedOrder | null {
  const order = recallOrder();
  if (order === null) return null;
  if (!readGuestToken()) writeGuestToken(order.token);
  return order;
}

async function orderRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = readGuestToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { [GUEST_HEADER]: token } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, UNREACHABLE);
  }
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    let reason = "";
    try {
      const parsed = JSON.parse(body);
      reason =
        typeof parsed?.detail === "string"
          ? parsed.detail
          : String(parsed?.detail?.reason ?? "");
    } catch {
      reason = "";
    }
    throw new ApiError(response.status, reason);
  }
  return (await response.json()) as T;
}

export interface OpenedOrder {
  purchase_id: string;
  checkout_url: string;
  client_token: string;
  provider: string;
  transaction_ref: string;
  environment: string;
}

export interface OrderState {
  purchase_id: string;
  /** none | processing | paid | failed | refunded — стан за нашими записами. */
  state: string;
  charged: boolean | null;
  started_audit_id: string | null;
  presence_available: number;
}

/**
 * Відкрити касу на разову перевірку. Аудиту ще немає — і не треба.
 *
 * Спроможність створюється тут же, якщо її не було: покупка мусить
 * комусь належати ще до того, як людина щось назве.
 */
export async function openOrder(): Promise<OpenedOrder> {
  await ensureGuestSession();
  let opened: OpenedOrder;
  try {
    opened = await orderRequest<OpenedOrder>("/v1/public/orders", {
      method: "POST",
    });
  } catch (failure) {
    // Мертва спроможність: токен у сховищі є, а сервер його не знає —
    // сесія протухла (сім днів), базу перезалили, або запис лишився від
    // іншого стенда. Це не відмова оплати: перед нами звичайний новий
    // відвідувач, і саме ним його треба зробити. Без цього людина
    // застрягала назавжди — кожне натискання «спробувати ще раз» било
    // в те саме 404, і кнопка виглядала зламаною.
    if (!(failure instanceof ApiError) || failure.status !== 404) throw failure;
    forgetOrder();
    await openGuestSession();
    opened = await orderRequest<OpenedOrder>("/v1/public/orders", {
      method: "POST",
    });
  }
  rememberOrder({ purchaseId: opened.purchase_id, token: readGuestToken() });
  return opened;
}

/** Стан замовлення за нашими записами. `reconcile` питає провайдера. */
export function readOrder(purchaseId: string, reconcile = false): Promise<OrderState> {
  const query = reconcile ? "?reconcile=true" : "";
  return orderRequest<OrderState>(`/v1/public/orders/${purchaseId}${query}`);
}

/** Витратити оплачену покупку на названий сайт. */
export function startPaidAudit(
  purchaseId: string,
  url: string,
): Promise<{ audit_id: string; status: string; unlocked: boolean }> {
  return orderRequest(`/v1/public/orders/${purchaseId}/audit`, {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}
