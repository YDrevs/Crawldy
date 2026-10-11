/**
 * Службовий API: конфігурація, аналітика, тестування.
 *
 * Окремий модуль від `lib/api.ts` навмисно: клієнтський кабінет не має
 * жодної причини знати ці адреси, а межа в коді робить випадковий виклик
 * помітним у рев'ю. Транспорт спільний — той самий `request` із cookie
 * сесії, тими самими таймаутом і розбором помилок.
 *
 * Секретів у типах немає за побудовою: поле `value` секрету завжди
 * `null`, стан описують `configured`, `source` і `hint` (останні символи).
 */

import { ApiError, API_URL } from "./api";

export { ApiError };

// ── контракти ─────────────────────────────────────────────────────────

export type SettingSource = "admin" | "env" | "default" | "none";

export interface SettingField {
  key: string;
  domain: "payment" | "ai";
  provider: string;
  secret: boolean;
  masked: boolean;
  kind: "str" | "float" | "int" | "choice";
  choices: string[];
  configured: boolean;
  source: SettingSource;
  storage_available: boolean;
  undecryptable: boolean;
  default: string | null;
  /** Завжди `null` для секретів і замаскованих значень. */
  value: string | null;
  /** Останні символи налаштованого секрету — щоб упізнати, не показуючи. */
  hint: string;
}

/**
 * Запис каталогу очима сторінки провайдера: продукт, сума з кабінету і
 * чи має його чинний провайдер. Поля звірки (`provider_has`, `matches`,
 * `provider_amount_minor`) зʼявляються лише в живій перевірці; `outcome`
 * і `detail` — лише у звіті про перепублікацію після збереження.
 */
export interface CatalogueRow {
  kind: "offer" | "plan";
  code: string;
  name: string;
  amount_minor: number | null;
  currency: string;
  provider?: string;
  price_ref?: string;
  published?: boolean;
  interval?: string;
  outcome?: string;
  detail?: string;
  provider_has?: boolean;
  matches?: boolean;
  provider_amount_minor?: number;
  provider_currency?: string;
}

export interface PaymentConfig {
  active_provider: string;
  environment: string;
  /** Що продається і чи опубліковано в чинного провайдера — без мережі. */
  catalogue?: CatalogueRow[];
  /** Після PUT: що перепубліковано; `null` — публікація не була потрібна. */
  published?: CatalogueRow[] | null;
  status: "configured" | "not_configured" | "inconsistent" | "fake";
  problems: string[];
  webhook_url: string;
  fake_available: boolean;
  secrets_storage_available: boolean;
  fields: SettingField[];
}

export interface ConnectionTest {
  ok: boolean;
  outcome: string;
  detail?: string;
  environment?: string;
  model?: string;
  latency_ms?: number;
  /** Платіжний провайдер: жива звірка прайсів каталогу. */
  catalogue?: CatalogueRow[];
}

export interface AiModelOption {
  model: string;
  supports_location: boolean;
  input_usd_per_mtok: number;
  output_usd_per_mtok: number;
  search_usd_per_1k: number;
}

export interface AiProviderView {
  provider: string;
  enabled: boolean;
  model: string;
  key_configured: boolean;
  execution_configured: boolean;
  production_adapter: boolean;
  supports_web_search: boolean;
  supports_location: boolean;
  default_country: string | null;
  max_attempt_cost_usd: number | null;
  backend?: string;
  backends: string[];
  vertex?: {
    project_configured: boolean;
    location: string;
    credentials: string;
  };
  settings: SettingField[];
  models: AiModelOption[];
}

export interface PresencePolicyView {
  enabled: boolean;
  providers: Record<
    string,
    {
      enabled: boolean;
      model: string;
      default_country: string | null;
      backend: string | null;
      max_call_cost_usd: number | null;
    }
  >;
  runs_per_prompt: number;
  max_prompts: number;
  retry_limit: number;
  raw_retention_days: number;
  concurrency: number;
  modes: string[];
  min_observations_for_rate: number;
  provider_timeout_s: number;
  languages: string[];
}

export interface AiConfig {
  domain: string;
  policy: PresencePolicyView;
  providers: AiProviderView[];
  secrets_storage_available: boolean;
  pricing_version: string;
}

export interface AnalyticsByType {
  offer_type: string;
  purchases: number;
  gross_minor: number;
  refunds: number;
  refunded_minor: number;
}

export interface AnalyticsCurrency {
  currency: string;
  purchases: number;
  gross_minor: number;
  refunds: number;
  refunded_minor: number;
  net_minor: number;
  average_minor: number | null;
  by_type: AnalyticsByType[];
}

export interface Analytics {
  period: {
    from: string | null;
    to: string | null;
    bucket: "day" | "week" | "month";
    generated_at: string;
  };
  sales: {
    currencies: AnalyticsCurrency[];
    subscription_payments_recorded: boolean;
  };
  customers: {
    purchasing_total: number;
    new_in_period: number;
    repeat_in_period: number;
  };
  usage: {
    audits_executed: number;
    audits_failed: number;
    audits_by_source: Record<string, number>;
    presence_executed: number;
    presence_failed: number;
    presence_by_entitlement: Record<string, number>;
    analyses_total: number;
    unique_domains: number;
    admin_tests_excluded: { audits: number; presence: number };
  };
  credits: Record<
    string,
    { sold: number; granted: number; used: number; revoked: number }
  >;
  subscriptions: {
    active_now: number;
    new_in_period: number;
    cancelled_in_period: number;
  };
  timeline: {
    bucket: string;
    purchases: number;
    gross_minor: Record<string, number>;
    audits: number;
    presence: number;
  }[];
}

export interface TestAuditRow {
  id: string;
  url: string;
  status: string;
  score_overall: number | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface TestIssueRow {
  id: string;
  module: string;
  code: string;
  issue_key: string;
  severity: string;
  confidence: string | null;
  title: string;
  description: string;
  recommendation: string;
  evidence: Record<string, unknown>;
  page_url: string | null;
  msg: string;
  text_locale: string;
  verdict: string | null;
}

export interface TestAuditDetail {
  run: Record<string, unknown> & {
    id: string;
    url: string;
    status: string;
    score_overall: number | null;
    scores: Record<string, number>;
    error: string | null;
    quota_source: string | null;
    degraded: unknown[];
    skipped_modules: string[];
    versions: Record<string, unknown>;
    progress: Record<string, unknown>;
    pages: { url: string; status_code: number | null; response_ms: number | null; depth: number }[];
  };
  issues: TestIssueRow[];
}

export interface TestPresenceRow {
  id: string;
  url: string;
  brand: string;
  status: string;
  observations_ok: number;
  observations_total: number;
  cost_usd: number;
  created_at: string | null;
  finished_at: string | null;
}

export interface TestObservation {
  provider: string;
  model: string;
  tool_version: string;
  prompt_id: string;
  prompt_text: string;
  category: string;
  segment: string;
  language: string;
  country: string | null;
  mode: string;
  run_index: number;
  status: string;
  searched: boolean;
  search_queries: string[];
  brand_mentioned: boolean;
  matched_alias: string | null;
  domain_cited: boolean;
  domain_linked: boolean;
  pages_cited: string[];
  cited_domains: string[];
  recommended: boolean | null;
  answer_excerpt: string;
  error: string | null;
  input_tokens: number;
  output_tokens: number;
  searches: number;
  cost_usd: number;
  retries: number;
  duration_ms: number;
}

export interface TestPresenceDetail {
  run: {
    id: string;
    url: string;
    origin: string;
    brand: string;
    status: string;
    error: string | null;
    prompt_set_version: string;
    observations_total: number;
    observations_ok: number;
    cost_usd: number;
    entitlement_source: string | null;
    created_at: string | null;
    finished_at: string | null;
    policy_snapshot: Record<string, unknown>;
  };
  metrics: Record<string, unknown>;
  coverage: Record<string, number | Record<string, number>>;
  observations: TestObservation[];
}

// ── транспорт ─────────────────────────────────────────────────────────

const TIMEOUT_MS = 60_000;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      signal: abort.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "no-connection");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail && typeof body.detail === "object") {
        detail = JSON.stringify(body.detail);
      }
    } catch {
      /* тіло не JSON */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ── конфігурація ──────────────────────────────────────────────────────

export const getPaymentConfig = () => call<PaymentConfig>("/v1/admin/config/payment");

export const savePaymentConfig = (values: Record<string, string | null>) =>
  call<PaymentConfig>("/v1/admin/config/payment", {
    method: "PUT",
    body: JSON.stringify({ values }),
  });

export const testPaymentConnection = () =>
  call<ConnectionTest>("/v1/admin/config/payment/test", { method: "POST" });

/** Покупка, за яку подія провайдера не прийшла. */
export interface PendingPayment {
  purchase_id: string;
  /** `pending` — каса відкрита; `abandoned` — погашена, але жива. */
  status: "pending" | "abandoned";
  created_at: string;
  organization: string;
  /** Пошта акаунта. Порожня в гостьової покупки: акаунта в неї немає. */
  email: string | null;
  offer_code: string | null;
  /** Назва продукту з каталогу; порожня для покупки повного звіту. */
  product: string | null;
  audit_id: string | null;
  quantity: number;
  /** Ціна замовленого. Порожня, поки покупка не має ані суми, ані зліпка. */
  currency: string | null;
  amount_minor: number | null;
  provider: string;
  /** Провайдер більше не обслуговує касу: нову оплату через нього не приймаємо. */
  foreign: boolean;
  transaction_ref: string;
}

/** Відповідь провайдера про транзакцію. */
export interface SettlementAnswer {
  settlement: "paid" | "unpaid" | "unknown";
  amount_minor?: number | null;
  currency?: string | null;
  invoice?: string | null;
  customer_ref?: string | null;
  /** Пошта з боку провайдера, якщо він її віддає. */
  email?: string | null;
  detail?: string;
}

export const listPendingPayments = (includeClosed = false, includeUnspent = false) =>
  call<PendingPayment[]>(
    `/v1/admin/payments/pending?include_closed=${includeClosed}` +
      `&include_unspent=${includeUnspent}`,
  );

/** Підсумок гасіння покинутих кас. */
export interface SweepReport {
  /** Скільки погашено цим викликом (0 у підрахунку). */
  swept: number;
  /** Скільки можна погасити зараз (0 у застосуванні). */
  sweepable: number;
  /** Кого саме гасити — повертає підрахунок, приймає застосування. */
  ids: string[];
  /** Усіх незарахованих у базі, а не лише у видимому вікні. */
  pending_total: number;
  looked_at: number;
  checked: number;
  unpaid: number;
  /** Каси провайдера, який більше не обслуговує оплату. */
  foreign: number;
  paid: number;
  unknown: number;
}

/** Без `ids` — лише підрахунок; з ними — гасіння рівно цих кас. */
export const sweepPendingPayments = (ids: string[] | null) =>
  call<SweepReport>("/v1/admin/payments/sweep", {
    method: "POST",
    body: JSON.stringify({ purchase_ids: ids }),
  });

export const verifyAllPendingPayments = (includeClosed = false) =>
  call<Record<string, SettlementAnswer>>(
    `/v1/admin/payments/verify?include_closed=${includeClosed}`,
    { method: "POST" },
  );

export const verifyPendingPayment = (purchaseId: string) =>
  call<SettlementAnswer>(`/v1/admin/payments/${purchaseId}/verify`, { method: "POST" });

export const creditPendingPayment = (purchaseId: string) =>
  call<{
    purchase_id: string;
    credited: boolean;
    quantity: number;
    currency: string;
    amount_minor: number;
    invoice: string | null;
    email: string | null;
  }>(`/v1/admin/payments/${purchaseId}/credit`, { method: "POST" });

export const getAiConfig = () => call<AiConfig>("/v1/admin/config/ai");

export const saveAiConfig = (payload: {
  policy?: PresencePolicyView;
  values?: Record<string, string | null>;
}) =>
  call<AiConfig>("/v1/admin/config/ai", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const testAiProvider = (provider: string) =>
  call<ConnectionTest>(`/v1/admin/config/ai/${provider}/test`, { method: "POST" });

// ── аналітика ─────────────────────────────────────────────────────────

export function getAnalytics(range: { from?: string; to?: string }): Promise<Analytics> {
  const query = new URLSearchParams();
  if (range.from) query.set("date_from", range.from);
  if (range.to) query.set("date_to", range.to);
  const suffix = query.toString();
  return call<Analytics>(`/v1/admin/analytics${suffix ? `?${suffix}` : ""}`);
}

// ── тестування ────────────────────────────────────────────────────────

export const startTestAudit = (payload: {
  url: string;
  options: { max_pages: number; max_depth: number; render?: boolean | null };
}) =>
  call<{ id: string; status: string; url: string }>("/v1/admin/testing/audits", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const listTestAudits = () => call<TestAuditRow[]>("/v1/admin/testing/audits");

export const getTestAudit = (id: string, lang: string) =>
  call<TestAuditDetail>(`/v1/admin/testing/audits/${id}?lang=${lang}`);

export function testReportUrl(id: string, format: string, lang: string): string {
  return `${API_URL}/v1/admin/testing/audits/${id}/report?format=${format}&lang=${lang}`;
}

/** Ті самі два документи присутності, що бачить клієнт. */
export function testPresenceReportUrl(
  id: string,
  kind: "general" | "technical",
  lang: string,
): string {
  return `${API_URL}/v1/admin/testing/presence/${id}/report?kind=${kind}&lang=${lang}`;
}

export const startTestPresence = (payload: {
  url: string;
  brand: string;
  brand_aliases: string[];
  category: string;
  services: string[];
  location: string | null;
  language: string;
  provider: string | null;
  model?: string | null;
}) =>
  call<{ id: string; status: string; url: string; providers: string[]; prompts: number }>(
    "/v1/admin/testing/presence",
    { method: "POST", body: JSON.stringify(payload) },
  );

export const listTestPresence = () => call<TestPresenceRow[]>("/v1/admin/testing/presence");

/** Собівартість одного повного аудиту присутності — для ціноутворення. */
export interface ModelCost {
  provider: string;
  model: string;
  input_usd_per_mtok: number;
  output_usd_per_mtok: number;
  cached_input_usd_per_mtok: number | null;
  search_usd_per_1k: number;
  /** Вартість одного спостереження цієї моделі за виміряними обсягами. */
  cost_per_observation: number;
}

export interface AuditCost {
  modes: number;
  prompts: number;
  runs_per_prompt: number;
  reference_source: string;
  reference_date: string;
  /** Обрана модель кожного провайдера з чинної (збереженої) політики. */
  selected: Record<string, string>;
  /** Усі каталожні моделі з виміряним обсягом, ключ "provider/model". */
  models: Record<string, ModelCost>;
  /** Останній справжній адмінський аудит (усі провайдери разом). */
  last_audit: {
    at: string;
    url: string;
    total_usd: number;
    observations_total: number;
    per_provider: Record<string, number>;
  } | null;
}

export const getAuditCost = () =>
  call<AuditCost>("/v1/admin/ai/audit-cost");

export const getTestPresence = (id: string) =>
  call<TestPresenceDetail>(`/v1/admin/testing/presence/${id}`);
