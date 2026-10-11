/**
 * Клієнт API. Єдине місце, звідки інтерфейс говорить із бекендом.
 *
 * Автентифікація — cookie-сесія (`credentials: "include"`), не ключ API:
 * ключ у браузері читається будь-яким скриптом на сторінці, а cookie з
 * `httponly` — ні. Ключі лишаються для інтеграцій, не для UI.
 *
 * Кожна функція повертає тип із `contracts.ts`. Жодних `any`, жодних
 * запитів повз цей файл: інакше межа між фронтендом і бекендом
 * розмивається саме там, де її найважче потім знайти.
 */

import type {
  Account,
  AdminOffer,
  AdminPlan,
  AuditDetail,
  AuditResult,
  AuditSummary,
  Cadence,
  Finding,
  LlmModel,
  Locale,
  Me,
  Offer,
  OfferCheckout,
  PresenceRun,
  PresenceRunCreate,
  PresenceSuggestion,
  PresencePlan,
  PresenceRunDetail,
  PurchaseState,
  ReportFormat,
  Schedule,
  Site,
  SiteHistory,
  Verdict,
} from "./contracts";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Помилка з відповіді API: статус лишається, щоб UI міг розрізняти. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const UNREACHABLE =
  `Backend is not responding (${API_URL}). Check that the stack is running.`;

/**
 * Скільки чекати на відповідь.
 *
 * `fetch` без межі не завершується ніколи: сервер, який прийняв
 * зʼєднання й мовчить, лишає інтерфейс у стані завантаження назавжди —
 * і це гірше за помилку, бо помилку видно, а вічний спінер виглядає як
 * повільна мережа. Спіймано на власному кабінеті: непіднятий бекенд
 * давав порожню сторінку зі спінером замість переходу на вхід.
 *
 * Тридцять секунд, а не пʼять: аудит ставиться в чергу швидко, але
 * звіт із докладними знахідками збирається довше.
 */
export const TIMEOUT_MS = 30_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), TIMEOUT_MS);
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      signal: abort.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    // fetch кидає «Failed to fetch» на все — від вимкненого бекенда до
    // CORS. Користувачу з цього рядка неясно нічого.
    throw new ApiError(0, UNREACHABLE);
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    throw new ApiError(response.status, await describe(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function describe(response: Response): Promise<string> {
  const body = await response.text().catch(() => "");
  let detail: string | null = null;
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed?.detail === "string") detail = parsed.detail;
    else if (Array.isArray(parsed?.detail)) {
      detail =
        parsed.detail
          .map((e: { msg?: string }) => e.msg)
          .filter(Boolean)
          .join("; ") || null;
    }
  } catch {
    /* тіло не JSON */
  }
  if (response.status === 401) return detail ?? "Please sign in.";
  if (response.status === 403) return detail ?? "Not allowed.";
  if (response.status === 404) return detail ?? "Not found.";
  if (response.status === 409) return detail ?? "Conflict.";
  // 502 від нас — це завжди авторський текст про зовнішній сервіс
  // («ціну не опубліковано у провайдера…»), а не витік нутрощів: у
  // необробленої помилки сервера `detail` немає взагалі. Ковтати його
  // означало показувати «Server error (502)» там, де сервер уже сказав,
  // що саме зробити. Тому: є `detail` — показуємо його.
  if (response.status >= 500) return detail ?? `Server error (${response.status}).`;
  return detail ?? `${response.status}: ${body.slice(0, 200)}`;
}

// ── автентифікація ────────────────────────────────────────────────────────

export const register = (email: string, password: string) =>
  request<Me>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const login = (email: string, password: string) =>
  request<Me>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const logout = () => request<void>("/v1/auth/logout", { method: "POST" });

export const getMe = () => request<Me>("/v1/auth/me");

// ── відновлення пароля ────────────────────────────────────────────────────
//
// Відповідь на запит відновлення однакова для відомої й невідомої адреси
// — і це не недогляд API, а його зміст: інакше форма «забули пароль»
// стає безкоштовним перевіряльником, хто зареєстрований у сервісі.
// Інтерфейс тому й показує нейтральне підтвердження: іншого він не знає.

/** Попросити лист із посиланням. 202 незалежно від того, чи є акаунт. */
export const requestPasswordReset = (email: string, lang: string) =>
  request<{ accepted: boolean }>("/v1/auth/password/forgot", {
    method: "POST",
    body: JSON.stringify({ email, lang }),
  });

/**
 * Чи чинне посилання — БЕЗ його витрачання.
 *
 * Потрібне, щоб сказати «посилання застаріло» до того, як людина введе
 * новий пароль, а не після. 404 приходить однаково на прострочений,
 * використаний, скасований і вигаданий токен.
 */
export const checkPasswordResetToken = (token: string) =>
  request<void>(`/v1/auth/password/reset?token=${encodeURIComponent(token)}`);

/** Встановити пароль за посиланням із листа. Сесії не видається. */
export const resetPassword = (token: string, password: string) =>
  request<void>("/v1/auth/password/reset", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });

/**
 * Зміна відомого пароля. Поточний обовʼязковий навіть у кабінеті:
 * інакше вкрадена сесія перетворюється на вкрадений акаунт. Після
 * успіху всі сесії відкликані — включно з поточною.
 */
export const changePassword = (currentPassword: string, newPassword: string) =>
  request<void>("/v1/auth/password/change", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

// ── службовий каталог: ціни й кількості ─────────────────────────────────
//
// Ті самі маршрути, що й у решти команди Crawldy. Права перевіряє сервер:
// без платформної ролі приходить 403, скільки б інтерфейс не малював.

export const listAdminOffers = () =>
  request<AdminOffer[]>("/v1/admin/commerce/offers");

export const saveAdminOffer = (offer: AdminOffer) =>
  request<AdminOffer>(`/v1/admin/commerce/offers/${offer.code}`, {
    method: "PUT",
    body: JSON.stringify(offer),
  });

export const listAdminPlans = () =>
  request<AdminPlan[]>("/v1/admin/commerce/plans");

export const saveAdminPlan = (plan: AdminPlan) =>
  request<AdminPlan>(`/v1/admin/commerce/plans/${plan.code}`, {
    method: "PUT",
    body: JSON.stringify(plan),
  });

/** Мова інтерфейсу — у профіль: обрана на ноутбуці, діє й на телефоні. */
export const saveMyLocale = (locale: Locale) =>
  request<Me>("/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ locale }),
  });

// ── акаунт ────────────────────────────────────────────────────────────────

/** Мова — щоб назва тарифу прийшла мовою кабінету, а не дефолтом. */
export const getAccount = (lang?: Locale) =>
  request<Account>(`/v1/account${lang ? `?lang=${lang}` : ""}`);

// ── сайти ─────────────────────────────────────────────────────────────────

export const listSites = () => request<Site[]>("/v1/sites");

export const createSite = (url: string, displayName?: string) =>
  request<Site>("/v1/sites", {
    method: "POST",
    body: JSON.stringify({ url, display_name: displayName ?? "" }),
  });

export const getSite = (id: string) => request<Site>(`/v1/sites/${id}`);

export const archiveSite = (id: string) =>
  request<void>(`/v1/sites/${id}`, { method: "DELETE" });

export const getSiteHistory = (id: string) =>
  request<SiteHistory>(`/v1/sites/${id}/history`);

// ── розклади ──────────────────────────────────────────────────────────────

export const listSchedules = (siteId?: string) =>
  request<Schedule[]>(`/v1/schedules${siteId ? `?site_id=${siteId}` : ""}`);

export const createSchedule = (input: {
  site_id: string;
  cadence: Cadence;
  timezone?: string;
  hour_local?: number;
}) =>
  request<Schedule>("/v1/schedules", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const setScheduleEnabled = (id: string, enabled: boolean) =>
  request<Schedule>(`/v1/schedules/${id}/${enabled ? "enable" : "disable"}`, {
    method: "POST",
  });

export const deleteSchedule = (id: string) =>
  request<void>(`/v1/schedules/${id}`, { method: "DELETE" });

// ── аудити ────────────────────────────────────────────────────────────────

export const listAudits = () => request<AuditSummary[]>("/v1/audits");

export const getAudit = (id: string, lang?: Locale) =>
  request<AuditDetail>(`/v1/audits/${id}${lang ? `?lang=${lang}` : ""}`);

export const createAudit = (input: {
  urls: string[];
  max_pages?: number;
  llm_model?: string | null;
}) =>
  request<AuditSummary>("/v1/audits", {
    method: "POST",
    body: JSON.stringify({
      urls: input.urls,
      options: {
        max_pages: input.max_pages ?? 25,
        max_depth: 2,
        llm_model: input.llm_model ?? null,
      },
    }),
  });

export const getLlmModels = () => request<LlmModel[]>("/v1/audits/llm-models");

/**
 * Результат аудиту в продуктовому вигляді — те, що малює екран звіту.
 * Окремий контракт від `?format=json`: той — файл, цей — інтерфейс.
 */
export const getAuditResult = (id: string, lang?: Locale) =>
  request<AuditResult>(`/v1/audits/${id}/result${lang ? `?lang=${lang}` : ""}`);

/**
 * Постійне платне посилання: той самий екранний вигляд, що в кабінеті.
 * Токен і є автентифікація — сесія не потрібна.
 */
export const readSharedReport = (token: string) =>
  request<AuditResult>(`/r/${token}?format=web`);

export const setVerdict = (issueId: string, verdict: Verdict, note = "") =>
  request<{ verdict: Verdict; note: string }>(
    `/v1/audits/issues/${issueId}/verdict`,
    { method: "PUT", body: JSON.stringify({ verdict, note }) },
  );

/**
 * Звіт іде через blob, а не через <a href>: запит потребує cookie сесії,
 * і браузер має віддати файл із правильним іменем із Content-Disposition.
 */
export async function downloadReport(
  auditId: string,
  format: ReportFormat,
  lang: Locale,
) {
  const response = await fetch(
    `${API_URL}/v1/audits/${auditId}/report?format=${format}&lang=${lang}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await describe(response));
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  const match = response.headers
    .get("content-disposition")
    ?.match(/filename="([^"]+)"/);
  link.download = match?.[1] ?? `crawldy-${auditId.slice(0, 8)}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

export type { Finding };

/** Actual AI Presence: явний запуск і читання спостережень. */
export function listPresenceRuns(): Promise<PresenceRun[]> {
  return request<PresenceRun[]>("/v1/presence/runs");
}

export function createPresenceRun(payload: PresenceRunCreate): Promise<PresenceRun> {
  return request<PresenceRun>("/v1/presence/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getPresenceRun(id: string): Promise<PresenceRunDetail> {
  return request<PresenceRunDetail>(`/v1/presence/runs/${id}`);
}

/** Факти для форми прогону — з останнього прочитаного аудиту сайту. 404 — аудиту немає. */
export function suggestPresence(url: string): Promise<PresenceSuggestion> {
  return request<PresenceSuggestion>(
    `/v1/presence/suggest?url=${encodeURIComponent(url)}`,
  );
}

export function getPresencePlan(): Promise<PresencePlan> {
  return request<PresencePlan>("/v1/presence/plan");
}

/** Вид документа: загальний власнику, технічний спеціалісту. */
export type ReportKind = "general" | "technical";

/** Word-експорт прогону: через blob, бо потрібна cookie-сесія. */
export async function downloadPresenceReport(
  id: string,
  lang: string,
  kind: ReportKind = "general",
) {
  const response = await fetch(
    `${API_URL}/v1/presence/runs/${id}/export.docx?lang=${lang}&kind=${kind}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await describe(response));
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  // Імʼя з відповіді, а не зібране тут: назва файлу називає вид, і
  // друге місце її складання розійшлося б із першим.
  const match = response.headers
    .get("content-disposition")
    ?.match(/filename="([^"]+)"/);
  link.download = match?.[1] ?? `ai-presence-${id.slice(0, 8)}-${kind}.docx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

/** Комерція: пропозиції, каса, портал платежів. Мова — щоб назви
 * пропозицій прийшли мовою кабінету, а не дефолтним написом. */
export function listOffers(locale?: string): Promise<Offer[]> {
  return request<Offer[]>(
    locale ? `/v1/offers?lang=${locale}` : "/v1/offers",
  );
}

export function openOfferCheckout(
  offerCode: string,
  promoCode?: string,
): Promise<OfferCheckout> {
  return request<OfferCheckout>("/v1/offers/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ offer_code: offerCode, promo_code: promoCode || undefined }),
  });
}

/** Свіжа сесія кабінету платежів провайдера. POST: кожен виклик
 *  створює нову тимчасову сесію; посилання ніде не зберігається. */
/**
 * Чи чекає кабінет на підтвердження оплати провайдером.
 *
 * Права це не видає й видати не може: сервер лише звіряє останню
 * незавершену покупку з провайдером. Потрібне рівно для одного стану, у
 * якому кабінет мовчав, — «щойно заплатив, а тут порожньо».
 */
export function readPaymentState(): Promise<{ awaiting_event: boolean }> {
  return request<{ awaiting_event: boolean }>("/v1/account/payment-state");
}

/**
 * Стан однієї покупки кабінету. `reconcile` питає провайдера — вмикати
 * його варто лише після закритої каси: поки вікно відкрите, події ще
 * можуть дійти самі.
 */
export function readPurchaseState(
  purchaseId: string,
  reconcile = false,
): Promise<PurchaseState> {
  const query = reconcile ? "?reconcile=true" : "";
  return request<PurchaseState>(
    `/v1/account/purchases/${encodeURIComponent(purchaseId)}${query}`,
  );
}

export function openBillingPortalSession(): Promise<{ url: string }> {
  return request<{ url: string }>("/v1/account/portal-session", {
    method: "POST",
  });
}

/** Каса підписки на публічний тариф. Права не видає — лише двері до
 *  оплати: підписку створить перевірена подія провайдера. */
export interface PlanCheckout {
  plan_code: string;
  provider_ref: string;
  url: string;
}

export function openPlanCheckout(planCode: string): Promise<PlanCheckout> {
  return request<PlanCheckout>(
    `/v1/plans/${encodeURIComponent(planCode)}/checkout`,
    { method: "POST" },
  );
}
