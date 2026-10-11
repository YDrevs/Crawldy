/**
 * Оплата повного аудиту гостем: від кнопки до чесного стану.
 *
 * ## Що фронтенд НЕ вирішує
 *
 * Нічого з того, що стосується права. Він не створює покупку, не
 * називає ціну, не вважає повернення з каси оплатою й не робить
 * висновків із параметрів адреси. Усі ці рядки прийшли б із чужого
 * сайту, а право дає лише перевірена подія провайдера, яку бачить
 * сервер.
 *
 * Тому тут є рівно дві дії: попросити бекенд відкрити касу й запитати
 * бекенд, що він знає про гроші. Обидві відповіді — серверні.
 *
 * ## Чому не `api.ts`
 *
 * Той файл ходить із cookie-сесією кабінету. Гість не має ані акаунта,
 * ані cookie: у нього спроможність у заголовку `X-Guest-Token`, і вона
 * діє на один браузер і сім днів. Змішати два способи автентифікації в
 * одному клієнті означало б надсилати кожен з них не туди.
 */

import { API_URL, ApiError, UNREACHABLE } from "./api";
import type { AuditResult } from "./contracts";
import type { FreeAuditResult } from "./free-result";

/** Заголовок спроможності гостя. Дзеркало `CAPABILITY_HEADER` бекенда. */
export const GUEST_HEADER = "X-Guest-Token";

/** Де живе токен гостя. `sessionStorage`, бо спроможність — на вкладку. */
const TOKEN_KEY = "crawldy.guest";

/**
 * Аудит, за який зараз платять.
 *
 * Потрібен рівно одному місцю — сторінці default payment link. Paddle
 * приводить на неї лише з `?_ptxn=`, тож номера аудиту в адресі немає
 * й бути не може, а після оплати людину треба повернути саме до її
 * результату. Правом це не є: сторінка результату однаково питає
 * сервер.
 */
const AUDIT_KEY = "crawldy.audit";

export function readGuestToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    // Приватний режим забороняє сховище. Це не збій оплати — просто
    // токен доведеться передати іншим шляхом.
    return "";
  }
}

export function writeGuestToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* див. вище */
  }
}

/**
 * Мова гостя переживає переходи, у яких адреса її не несе.
 *
 * Каса default payment link повертає людину без нашого `?lang=`:
 * Paddle додає до налаштованої адреси лише `_ptxn`. Без запамʼятаної
 * мови українець, що заплатив, повертався б на англійський екран.
 * Це подання, не право: сервер мову гостя не зберігає й не питає.
 */
const LANG_KEY = "crawldy.lang";

export function rememberLocale(locale: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(LANG_KEY, locale);
  } catch {
    /* приватний режим забороняє сховище — мова просто буде типовою */
  }
}

export function recallLocale(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.sessionStorage.getItem(LANG_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberAudit(auditId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(AUDIT_KEY, auditId);
  } catch {
    /* приватний режим забороняє сховище — повернення просто буде типовим */
  }
}

export function recallAudit(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.sessionStorage.getItem(AUDIT_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Публічні налаштування каси: `GET /v1/public/checkout-config`. */
export interface CheckoutConfig {
  provider: string;
  environment: string;
  /** Клієнтський токен провайдера. Публічний за його ж задумом. */
  client_token: string;
}

export const readCheckoutConfig = () =>
  guestRequest<CheckoutConfig>("/v1/public/checkout-config");

/** Відповідь `POST /v1/public/audits/{id}/checkout`. */
export interface CheckoutIntent {
  purchase_intent: string;
  checkout_url: string;
  audit_id: string;
  /** Публічний токен провайдера для його ж скрипта. Не ключ API. */
  client_token: string;
  provider: string;
  transaction_ref: string;
  environment: string;
}

/**
 * Стани оплати, які сервер уміє назвати.
 *
 * `paid` окремо від `unlocked` навмисно: гроші прийшли, а провіження
 * могло ще не завершитись. Одне поле на два факти або обіцяло б звіт,
 * якого ще немає, або називало б оплату неоплаченою.
 *
 * `canceled` тут немає, і це не пропуск: закриття вікна оплати — подія
 * браузера, а не факт про гроші. Сервер її не бачить і вигадувати не
 * буде; цей стан живе в компоненті, який вікно й відкривав.
 */
export type PaymentState =
  | "none"
  | "processing"
  | "paid"
  | "failed"
  | "refunded";

export interface PaymentStatus {
  audit_id: string;
  state: PaymentState;
  unlocked: boolean;
  /**
   * Чи списано кошти за останню покупку.
   *
   * `false` — сервер знає, що ні: каси не відкривали або провайдер
   * підтвердив, що транзакція не оплачена. `true` — списано (доступ при
   * цьому може ще не прийти: його дає лише подія провайдера). `null` —
   * не зʼясовано: без `reconcile` сервер провайдера не питає, а з ним
   * провайдер міг не відповісти. Відсутність поля читається як `null`.
   */
  charged?: boolean | null;
}

async function guestRequest<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new ApiError(response.status, await describeGuestError(response));
  }
  return (await response.json()) as T;
}

async function describeGuestError(response: Response): Promise<string> {
  const body = await response.text().catch(() => "");
  let reason = "";
  try {
    const parsed = JSON.parse(body);
    reason =
      typeof parsed?.detail === "string"
        ? parsed.detail
        : String(parsed?.detail?.reason ?? "");
  } catch {
    /* тіло не JSON */
  }
  if (response.status === 503) return reason || "checkout.unavailable";
  if (response.status === 409) return reason || "already.unlocked";
  if (response.status === 404) return reason || "not.found";
  return reason || `${response.status}`;
}

/**
 * Попросити бекенд відкрити касу.
 *
 * Покупка створюється там і до каси; звідси не передається нічого,
 * крім номера аудиту, — і цього досить, бо все інше сервер знає сам.
 */
export const openCheckout = (auditId: string) =>
  guestRequest<CheckoutIntent>(`/v1/public/audits/${auditId}/checkout`, {
    method: "POST",
  });

/**
 * Що сервер знає про гроші за цей аудит. Єдине джерело правди.
 *
 * `reconcile` просить сервер звірити транзакцію з провайдером. Це
 * потрібно рівно в одному випадку — вікно каси закрилось без слова
 * «оплачено»: подія від провайдера в такому разі не приходить ніколи,
 * і без звірки сервер не має як відрізнити «передумав» від «заплатив,
 * а подія ще в дорозі». Решту часу відповідь береться з наших записів.
 */
export const readPaymentStatus = (
  auditId: string,
  options: { reconcile?: boolean } = {},
) =>
  guestRequest<PaymentStatus>(
    `/v1/public/audits/${auditId}/payment${options.reconcile ? "?reconcile=true" : ""}`,
  );

/** Стани, у яких питати ще раз немає сенсу: вони не зміняться самі. */
export const SETTLED_STATES: readonly PaymentState[] = [
  "paid",
  "failed",
  "refunded",
];

export function isSettled(status: PaymentStatus): boolean {
  // `paid` без `unlocked` не є кінцевим: гроші прийшли, доступ ще ні,
  // і саме цей стан варто перепитати.
  if (status.state === "paid") return status.unlocked;
  return SETTLED_STATES.includes(status.state);
}

/**
 * Скільки чекати перед наступним питанням.
 *
 * Зростає, а не стоїть на місці: підтвердження приходить за секунди,
 * але якщо його немає за хвилину, воно навряд чи прийде за наступну —
 * а рівний інтервал у секунду перетворив би відкриту вкладку на
 * повільний обстріл власного API.
 */
export function nextPollDelayMs(attempt: number): number {
  const seconds = Math.min(2 ** Math.max(attempt, 0), 30);
  return seconds * 1000;
}

// ── аудит гостя ────────────────────────────────────────────────────────────

/**
 * Сесія гостя: організація без учасників плюс спроможність на сім днів.
 *
 * Відкритий токен віддається один раз — тут. Ніде більше його прочитати
 * не можна, тож загублений токен означає загублений аудит, і саме тому
 * він лягає у сховище одразу, до першого ж наступного запиту.
 */
export async function openGuestSession(): Promise<string> {
  const opened = await guestRequest<{ token: string; expires_at: string }>(
    "/v1/public/sessions",
    { method: "POST" },
  );
  writeGuestToken(opened.token);
  return opened.token;
}

/** Спроможність, яка вже є, або нова. */
export async function ensureGuestSession(): Promise<string> {
  return readGuestToken() || (await openGuestSession());
}

/**
 * Де саме зараз аудит.
 *
 * Усі поля необовʼязкові, і це не м'якість типу, а сам стан справ:
 * до першої хвилі краулу писати нічого, а при кількох цілях бекенд не
 * пише взагалі — одне число описувало б то одну ціль, то іншу. Екран
 * мусить уміти обидва випадки, тому «немає чисел» тут представлене,
 * а не підмінене нулями.
 */
export interface AuditProgress {
  stage?: string;
  pages_read?: number;
  pages_known?: number;
}

export interface StartedAudit {
  audit_id: string;
  status: string;
  unlocked: boolean;
  progress?: AuditProgress;
  /**
   * Чому не вийшло — нормалізованим класом і безпечним реченням.
   *
   * Обидва поля необовʼязкові й приходять ЛИШЕ для термінальної невдачі:
   * у виконуваного аудиту невдачі ще не сталося, і порожнє поле поруч із
   * «виконується» читалося б як натяк.
   *
   * Речення складає бекенд мовою запиту. Каталогу класів тут немає
   * навмисно: другий переклад тих самих пʼяти станів розійшовся б із
   * першим, а екран уже передає `lang` і вміє показати те, що прийшло.
   * `failure_class` лишається для розрізнення, а не для показу.
   */
  failure_class?: string;
  failure_reason?: string;
}

export const startGuestAudit = (url: string) =>
  guestRequest<StartedAudit>("/v1/public/audits", {
    method: "POST",
    body: JSON.stringify({ url }),
  });

/**
 * Стан аудиту або короткий вигляд, коли він готовий.
 *
 * Дві форми під однією адресою — це контракт бекенда, а не спрощення:
 * поки аудит виконується, короткого вигляду не існує, і вигадувати
 * порожню оболонку з нулями означало б показати бал, якого немає.
 */
export const readGuestAudit = (auditId: string, lang: string) =>
  guestRequest<StartedAudit | FreeAuditResult>(
    `/v1/public/audits/${auditId}?lang=${encodeURIComponent(lang)}`,
  );

/** Повний звіт. Викликається лише після того, як сервер сказав `unlocked`.
 *
 * Мова передається так само, як у короткому вигляді: підписи екрана
 * приходять із каталогу фронта, а тексти знахідок — із бекенда, і без
 * `lang` вони розходились. Українська сторінка показувала англійські
 * проблеми під українськими підписами. */
export const readGuestFull = (auditId: string, lang: string) =>
  guestRequest<AuditResult>(
    `/v1/public/audits/${auditId}/full?lang=${encodeURIComponent(lang)}`,
  );

/** Чи це вже короткий вигляд, а не просто статус. */
export function isShortView(
  value: StartedAudit | FreeAuditResult,
): value is FreeAuditResult {
  return "overall_band" in value;
}

/** Стани аудиту, у яких чекати вже нема чого.
 *
 * `skipped` тут доданий: бекенд віддає саме його, коли запуск не
 * починався (вичерпана квота), і без цього рядка екран опитував такий
 * аудит нескінченно — термінальний стан виглядав як «ще працює».
 *
 * `cancelled` лишився, хоч `AuditStatus` такого значення не має й
 * бекенд його не віддає: прибрати мертвий рядок — окрема зміна, а не
 * частина цієї. Він нікому не шкодить, але й нічого не ловить.
 */
const AUDIT_DONE = new Set(["completed", "partial", "failed", "skipped", "cancelled"]);

export const auditIsRunning = (status: string) => !AUDIT_DONE.has(status);

/**
 * Постійне посилання на куплений звіт.
 *
 * Видається після розблокування й переживає гостьову сесію: право
 * привʼязане до покупки, а не до сьоми днів у sessionStorage.
 */
export const issueReportLink = (auditId: string, lang: string) =>
  guestRequest<{ token: string; url: string }>(
    `/v1/public/audits/${auditId}/report-link`,
    { method: "POST", body: JSON.stringify({ lang }) },
  );

// ── присутність після оплати ─────────────────────────────────────────
//
// Разова покупка дає одиницю присутності; факти для прогону виводяться
// з того самого аудиту й показуються з можливістю змінити.

export interface GuestPresenceSuggestion {
  audit_id: string;
  url: string;
  brand: string;
  brand_aliases: string[];
  category: string;
  location: string | null;
  language: string;
  /** Звідки взято кожен непорожній факт: schema | title | domain | site. */
  sources: Record<string, string>;
}

export interface GuestPresenceRun {
  id: string;
  url: string;
  brand: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  finished_at: string | null;
  observations_total: number;
  observations_ok: number;
  cost_usd: number;
  error: string | null;
  entitlement_source: string | null;
  deliverable: boolean | null;
}

export interface GuestPresence {
  suggestion: GuestPresenceSuggestion;
  can_start: boolean;
  credits_available: number;
  providers: string[];
  runs: GuestPresenceRun[];
}

export const readGuestPresence = (auditId: string) =>
  guestRequest<GuestPresence>(`/v1/public/audits/${auditId}/presence`);

export const startGuestPresence = (
  auditId: string,
  payload: {
    brand: string;
    brand_aliases: string[];
    category: string;
    location: string | null;
    language: string;
    idempotency_key: string;
  },
) =>
  guestRequest<GuestPresenceRun>(`/v1/public/audits/${auditId}/presence`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const readGuestPresenceRun = (runId: string) =>
  guestRequest<GuestPresenceRun>(`/v1/public/presence/${runId}`);

/**
 * Word-експорт присутності для гостя: той самий документ, що в кабінеті.
 *
 * Через blob, а не через `<a href>`: право гостя — це заголовок зі
 * спроможністю, і посилання його не несе. Імʼя файлу береться з
 * відповіді — вид документа називає сервер.
 */
export async function downloadGuestPresenceReport(
  runId: string,
  lang: string,
  kind: "general" | "technical",
) {
  const token = readGuestToken();
  const response = await fetch(
    `${API_URL}/v1/public/presence/${runId}/export.docx?lang=${lang}&kind=${kind}`,
    {
      cache: "no-store",
      headers: token ? { [GUEST_HEADER]: token } : {},
    },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await describeGuestError(response));
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  const match = response.headers
    .get("content-disposition")
    ?.match(/filename="([^"]+)"/);
  link.download = match?.[1] ?? `ai-presence-${runId.slice(0, 8)}-${kind}.docx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}
