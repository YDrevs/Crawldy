/**
 * Типи відповідей API — дзеркало контрактів /v1.
 *
 * Це і є вся межа між інтерфейсом і бекендом. Фронтенд не знає ні схеми
 * PostgreSQL, ні ORM, ні внутрішньої структури двигуна аудиту: він знає
 * рівно ці форми, і поки вони не змінилися, бекенд вільний переписувати
 * під ними будь-що.
 *
 * Форми віддзеркалюють Pydantic-схеми бекенда, а їх, у свою чергу,
 * заморожує `tests/test_api_contracts.py`. Розходження між цим файлом і
 * контрактом ловиться не тут, а там — тому додаючи поле, треба
 * дописувати його в обох місцях.
 */

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type ModuleName =
  | "performance"
  | "seo"
  | "ai_ready"
  | "llm_visibility"
  | "tech"
  | "accessibility";

export type AuditStatus =
  | "queued"
  | "running"
  | "completed"
  | "partial"
  | "failed"
  | "skipped";

export type Verdict = "agreed" | "fixed" | "wont_fix" | "wrong" | "unclear";

export type FailureClass =
  | "site_unreachable"
  | "site_blocked"
  | "provider_failed"
  | "internal_error"
  | "cancelled";

export type QuotaState = "reserved" | "consumed" | "released";

/**
 * Стан оплати одним словом — уже розвʼязаний бекендом.
 *
 * `SubscriptionStatus` для цього замало: «активна, але скасована
 * наприкінці періоду» — це статус плюс прапорець, а для клієнта це
 * окремий стан із власним текстом. Складати їх тут означало б повторити
 * правило в кожному клієнті й одного дня розійтися в одному з них.
 */
export type BillingState =
  | "free"
  | "trialing"
  | "active"
  | "past_due"
  | "paused"
  | "cancelling"
  | "cancelled";

export type SubscriptionStatus =
  | "inactive"
  | "trialing"
  | "active"
  | "past_due"
  | "paused"
  | "cancelled";

/** Мови продукту. Не мова сайту, який аудитують, — то інша вісь. */
export type Locale =
  | "en" | "es" | "fr" | "de" | "pt" | "uk" | "ru" | "pl" | "ar" | "hi" | "zh" | "ja";

/**
 * Види Word-звіту звуться «загальний» і «технічний». Старі значення
 * (`docx`, `docx-owner`) сервер приймає й далі — за ними ходять уже
 * видані посилання, — але новий код називає вид явно.
 */
export type ReportFormat =
  | "json"
  | "docx"
  | "docx-owner"
  | "docx-general"
  | "docx-technical"
  | "llms-txt";

// ── аудит ─────────────────────────────────────────────────────────────────

export interface AuditSummary {
  id: string;
  /**
   * Сайт, до якого належить запуск. Порожньо для аудитів із CLI.
   *
   * Без цього поля інтерфейс зіставляв би аудит із сайтом за рядком
   * origin — тобто рівно тим способом, від якого сутність Site і рятує.
   */
  site_id: string | null;
  url: string;
  origin: string;
  status: AuditStatus;
  score_overall: number | null;
  scores: Record<string, number> | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  option_adjustments: Array<Record<string, unknown>>;
  quota_state: QuotaState;
  failure_class: FailureClass | null;
  /**
   * Скільки разів бралися виконувати. Більше одного означає повтори —
   * і що це **один** запуск, а не кілька аудитів. В історії вони не
   * розділяються: клієнт замовляв один аудит.
   */
  attempts: number;
  trigger: AuditTrigger;
  /** Мова звіту. Один клієнт може мати звіти двома мовами. */
  locale: string;
}

export interface Finding {
  id: string;
  module: ModuleName;
  code: string;
  severity: Severity;
  title: string;
  description: string;
  recommendation: string;
  evidence: Record<string, unknown>;
  page_url: string | null;
  /** Стабільний ключ проблеми. Ним оперує порівняння з конкурентами. */
  msg: string;
  verdict: Verdict | null;
  verdict_note: string;
  /** Мова, якою текст справді віддали — може відрізнятись від запитаної. */
  text_locale: string;
}

export interface Target {
  id: string;
  position: number;
  url: string;
  origin: string;
  status: AuditStatus;
  score_overall: number | null;
  scores: Record<string, number> | null;
  error: string | null;
  failure_class: FailureClass | null;
}

export interface Attempt {
  number: number;
  status: AuditStatus;
  failure_class: FailureClass | null;
  error: string;
  retry_decision: string;
  started_at: string;
  finished_at: string | null;
}

export interface AuditDetail extends AuditSummary {
  locale: string;
  options: Record<string, unknown>;
  targets: Target[];
  pages_count: number;
  issues_count: number;
  issues_by_severity: Record<string, number>;
  issues: Finding[];
  attempt_log: Attempt[];
}

// ── результат аудиту ──────────────────────────────────────────────────────

/**
 * Відповідь `GET /v1/audits/{id}/result` — усе для головного екрана
 * одним запитом.
 *
 * **Тут нічого не рахується на клієнті.** Ні пріоритети, ні impact, ні
 * смуги, ні потенційний бал: усе приходить готовим. Порахувати щось із
 * цього ще раз у React означає завести другу копію бізнес-логіки, яку
 * не покривають тести двигуна, — і одного дня клієнт побачить два різні
 * «найважливіші».
 */

export type Effort = "low" | "medium" | "high";

/**
 * Наскільки твердо ми це стверджуємо.
 *
 * Статус відповіді — факт, висновок моделі — судження. Знахідка з
 * низькою впевненістю опускається на смугу нижче в пріоритезації й не
 * потрапляє в «Що робити першим»; інтерфейс мусить показувати різницю,
 * інакше обіцяє однакову надійність там, де її немає.
 */
export type Confidence = "high" | "medium" | "low";

/**
 * Смуга інтерпретації бала. Межі рахує бекенд, не UI.
 *
 * `unknown` — не п'ята смуга якості, а відсутність оцінки: напрям
 * виключено зі скора, бо даних не було. Пропустити це значення означає
 * збрехати типом рівно в тому випадку, заради якого продукт і мовчить
 * замість вигаданого числа.
 */
export type Band = "critical" | "poor" | "medium" | "good" | "unknown";

export interface AccessibilityFinding {
  audit_id: string;
  title: string;
  impact: string;
  /** Наш чек, який говорить про це саме — і лише якщо він СПРАВДІ
   *  спрацював у цьому аудиті. null означає «більше ніде не сказано»,
   *  а не «мапи немає». */
  also_reported_as: string | null;
  also_reported_module: ModuleName | null;
}

/**
 * Доступність ОДНІЄЇ сторінки, а не оцінка сайту.
 *
 * Бала 0..100 тут немає навмисно: ми міряємо одну сторінку одним
 * зовнішнім інструментом, і бал поруч із балами по всьому сайту
 * читався б як рівне з рівним. `available: false` означає «не
 * виміряли» — це не нуль знайдених проблем.
 */
export interface AccessibilitySnapshot {
  available: boolean;
  measured_url: string | null;
  strategy: string;
  applicable: number | null;
  passed: number | null;
  failed: number | null;
  findings: AccessibilityFinding[];
  /** Бал Lighthouse для цієї сторінки: зовнішній орієнтир, не наш бал. */
  lighthouse_score: number | null;
  /** Доступність показана знімком, але свою частку загального бала поки
   *  зберігає. Без цього видимі ваги модулів сходяться до 90%, і читач
   *  не має звідки дізнатися, чому. */
  counts_toward_overall: boolean;
  overall_weight: number | null;
}

export interface PassedCheck {
  key: string;
  module: ModuleName;
  /** Про що твердження: origin | site | page | sampled. Page-scoped факт
   *  ніколи не подається як site-level. */
  scope: string;
  /** Локалізований сервером заголовок. */
  title: string;
  facts: Record<string, unknown>;
}

export interface ModuleScore {
  module: ModuleName;
  score: number | null;
  band: Band;
  weight: number;
  issues_count: number;
  /** Напрям виключено зі скора: даних не було або клієнт його вимкнув. */
  excluded: boolean;
  /** Оцінка є, але побудована не на всіх сигналах напряму. */
  partial: boolean;
}

/**
 * Скільки сайту ми справді прочитали.
 *
 * Стоїть поруч із балом, а не в доказах: 20 адрес із 3407 дають бал,
 * поданий так само впевнено, як бал за прочитаним повністю сайтом.
 */
export interface Coverage {
  /** Чи репрезентує прочитане живий сайт: scored |
   *  scored_with_coverage_limitation | withheld. Причини — слаги фактів,
   *  а не пороги. */
  state: string;
  state_reasons: string[];
  pages_read: number;
  pages_fetched: number;
  pages_failed: number;
  urls_known: number;
}

export interface ResultSummary {
  issues_total: number;
  by_severity: Record<string, number>;
  by_module: Record<string, number>;
  coverage: Coverage;
  /** Завжди true. Бали окремих проблем незалежні — сумувати не можна. */
  impact_is_independent: boolean;
}

/**
 * Пріоритезована проблема — одна, а не одне входження.
 *
 * Пʼять сторінок без canonical — це один пункт, бо це одна дія. Порядок
 * уже правильний: спершу смуга серйозності, всередині — вигода на
 * вартість, помножена на важливість сторінки. Сортувати заново на
 * клієнті означає зламати цей порядок.
 */
export interface Priority {
  rank: number;
  issue_key: string;
  module: ModuleName;
  severity: Severity;
  title: string;
  problem: string;
  action: string;
  /** Наслідок простою мовою — для того, хто ухвалює рішення. */
  consequence: string;
  scope: "site" | "page";
  affected_pages: number;
  affected_examples: string[];
  evidence: Record<string, unknown>;
  /** Сумувати не можна: кожен міряний окремо проти того самого базового бала. */
  impact_points: number;
  impact_by_module: Record<string, number>;
  effort: Effort;
  confidence: Confidence;
}

/** Що робити першим. Коротший зріз пріоритетів для тих, хто діє. */
export interface NextAction {
  rank: number;
  issue_key: string;
  module: ModuleName;
  action: string;
  why: string;
  expected_gain_points: number;
  expected_gain: string;
  effort: Effort;
  affected_pages: number;
}

/** Чого не виміряли і чому. Мовчання про це гірше за пропуск. */
export interface MissingData {
  scope: string;
  kind: string;
  reason: string;
  affects: string[];
  note: string;
}

export interface ResultFinding {
  id: string | null;
  code: string;
  issue_key: string;
  module: ModuleName;
  severity: Severity;
  title: string;
  description: string;
  recommendation: string;
  page_url: string | null;
  evidence: Record<string, unknown>;
  verdict: Verdict | null;
  verdict_note: string;
}

/** Якою мовою відповідь і чи довелося падати у фолбек. */
export interface Localization {
  locale: string;
  fallback_locale: string;
  /** Скільки рядків віддано не запитаною мовою. Нуль — переклад повний. */
  fell_back_strings: number;
}

export interface AuditResult {
  contract_version: number;
  audit_id: string;
  site_id: string | null;
  url: string;
  origin: string;
  status: AuditStatus;
  generated_at: string;
  finished_at: string | null;

  overall_score: number | null;
  overall_band: Band;
  /** Бал після виправлення всього з next_actions. Не сума impact_points. */
  potential_score: number | null;

  modules: ModuleScore[];
  summary: ResultSummary;
  priorities: Priority[];
  next_actions: NextAction[];
  findings: ResultFinding[];
  missing_data: MissingData[];
  /** Доступність подається знімком сторінки замість бала модуля. */
  accessibility: AccessibilitySnapshot | null;
  /** Пройдені перевірки: явний доказ, ніколи не тиша чека. Адитивне
   *  поле — старі відповіді його не мають. */
  passed_checks?: PassedCheck[];

  /** Чим саме порахований аудит. Без версій дві точки історії нечитані. */
  engine_versions: Record<string, unknown>;
  localization: Localization;
}

// ── сайти й розклади ──────────────────────────────────────────────────────

/**
 * Останній запуск сайту — стільки, скільки треба переліку.
 *
 * Бал буває порожнім не лише в невдалого аудиту: сайт, що не пустив
 * краулер, теж не має числа. Тому поруч завжди статус і клас невдачі,
 * щоб інтерфейс сказав, **чому** бала немає, замість намалювати нуль.
 */
export interface LatestAudit {
  id: string;
  status: AuditStatus;
  score_overall: number | null;
  failure_class: FailureClass | null;
  created_at: string;
  finished_at: string | null;
}

/** Розклад сайту у двох словах. Повний — у переліку розкладів. */
export interface ScheduleSummary {
  id: string;
  enabled: boolean;
  next_run_at: string | null;
  needs_attention: boolean;
}

/**
 * Сайт — бізнес-ресурс, до якого чіпляється історія.
 *
 * Не те саме, що `AuditTarget`: той — історичний зліпок адреси, з якої
 * колись читали. Сайт переживає переїзд на інший хост, ціль — ні.
 */
export interface Site {
  id: string;
  origin: string;
  display_name: string;
  created_at: string;
  archived_at: string | null;
  /**
   * Порожні там, де сайт віддається сам по собі — після створення чи
   * перейменування. У переліку й на сторінці сайту заповнені.
   */
  latest_audit?: LatestAudit | null;
  schedule?: ScheduleSummary | null;
}

export type Cadence = "daily" | "weekly" | "monthly";

/** Звідки взявся запуск. Історія без цього не пояснює несподіваних аудитів. */
export type AuditTrigger = "manual" | "scheduled" | "api";

export interface Schedule {
  id: string;
  site_id: string;
  cadence: Cadence;
  timezone: string;
  hour_local: number;
  minute_local: number;
  /** Для тижневого: 0 — понеділок. Порожньо для решти частот. */
  day_of_week: number | null;
  /** Для місячного: число місяця. Порожньо для решти частот. */
  day_of_month: number | null;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  consecutive_failures: number;
  last_failure_reason: string;
  needs_attention: boolean;
}

// ── історія ───────────────────────────────────────────────────────────────

export interface ScorePoint {
  audit_id: string;
  at: string;
  overall: number | null;
  scores: Record<string, number>;
  versions: Record<string, unknown>;
  can_be_recomputed: boolean;
}

export interface HistoryStep {
  before: ScorePoint;
  after: ScorePoint;
  days_between: number;
  overall_delta: number | null;
  by_module: Record<string, number>;
  /** Обидва аудити пораховані однаково — різницю можна приписати сайту. */
  comparable: boolean;
  changed_in_us: string[];
  rebased: boolean;
}

export interface SiteHistory {
  site: { id: string; origin: string; name: string };
  /** Вікно видимості тарифу. null — показано все. */
  visible_days: number | null;
  points: ScorePoint[];
  steps: HistoryStep[];
  incomparable_steps: number;
  fixable_by_recompute: number;
}

// ── акаунт ────────────────────────────────────────────────────────────────

export interface Account {
  organization: {
    id: string;
    name: string;
    slug: string;
    is_personal: boolean;
    default_locale: string;
  };
  role: string;
  plan: { code: string; name: string };
  subscription: {
    status: SubscriptionStatus;
    cancel_at_period_end: boolean;
    current_period_start: string | null;
    current_period_end: string | null;
    trial_end: string | null;
    grace_until: string | null;
  } | null;
  entitlements: Record<string, unknown>;
  /**
   * Скільки аудитів доступно — з двох різних джерел.
   *
   * **Два числа, а не одне.** Квота періоду згорає при поновленні,
   * куплені окремо кредити — ні. Показати суму означало б, що частина
   * числа одного дня зникне сама, і клієнт дізнається про це постфактум.
   *
   * Провайдера тут немає навмисно: інтерфейс не знає, через кого пройшов
   * платіж, і не ламається від того, що через рік це буде інший.
   */
  billing_state: BillingState;
  usage: {
    audits_used: number;
    audits_limit: number | null;
    /** Скільки лишилось. Рахує бекенд: тут можлива перевитрата й безліміт. */
    audits_remaining: number | null;
    period_start: string;
    period_end: string;
    /** Коли поновиться. Порожньо — не поновиться взагалі. */
    renews_at: string | null;
    /** Куплені окремо. Без періоду, при поновленні не змінюються. */
    one_off_available: number;
    presence_used: number;
    presence_limit: number | null;
    presence_remaining: number | null;
    presence_credits_available: number;
  };
}

export interface Me {
  user: {
    id: string;
    email: string;
    display_name: string;
    /** Мова інтерфейсу. Порожньо — не обирав; діє мова організації. */
    locale: string;
    /**
     * Роль у команді Crawldy або `null`. Інтерфейс питає її рівно для
     * одного: чи пропонувати службові екрани. Прав вона не дає — їх
     * перевіряє кожен службовий маршрут, і 403 приходить незалежно від
     * того, що намалював фронтенд.
     */
    platform_role: string | null;
  } | null;
  organization: { id: string; name: string; slug: string };
  auth: string;
}

/**
 * Пропозиція каталогу очима адміністратора: усе, чим він керує, включно
 * з посиланням на прайс провайдера й неактивними записами.
 */
export interface AdminOffer {
  code: string;
  offer_type: string;
  active: boolean;
  display_name: string;
  description: string;
  provider: string;
  provider_price_ref: string;
  currency: string;
  display_amount_minor: number | null;
  audit_credits: number;
  presence_credits: number;
  promo_eligible: boolean;
  sort_order: number;
  display_name_i18n: Record<string, string>;
  description_i18n: Record<string, string>;
}

export interface AdminPlanPrice {
  provider: string;
  provider_price_id: string;
  currency: string;
  interval: string;
  display_amount_minor: number | null;
}

export interface AdminPlan {
  code: string;
  name: string;
  description: string;
  is_public: boolean;
  archived: boolean;
  sort_order: number;
  /** Сирі ключі прав. Сторінка цін показує з них лише Presence на місяць. */
  entitlements: Record<string, unknown>;
  prices: AdminPlanPrice[];
  name_i18n: Record<string, string>;
  description_i18n: Record<string, string>;
}

export interface LlmModel {
  id: string;
  label: string;
  cost_per_audit: number;
  note: string;
  default: boolean;
}

/**
 * Actual AI Presence: синтетичні спостереження через API провайдерів.
 *
 * `provenance` — незмінна частина контракту: кожен екран мусить казати,
 * що це контрольовані API-перевірки, а не вимір споживчих продуктів.
 */
export interface PresenceRun {
  id: string;
  url: string;
  brand: string;
  /** Сайт кабінету, якщо прогін замовлено для нього. */
  site_id: string | null;
  status: "queued" | "running" | "completed" | "failed";
  evidence_family: "synthetic";
  prompt_set_version: string;
  created_at: string;
  finished_at: string | null;
  observations_total: number;
  observations_ok: number;
  cost_usd: number;
  error: string | null;
  provenance: string;
  entitlement_source: string | null;
  entitlement_settled: boolean;
  deliverable: boolean | null;
}

export interface PresenceMetric {
  key: string;
  numerator: number;
  denominator: number;
  rate: number | null;
  unavailable: number;
  provider_scope: string[];
  prompt_scope: string;
  not_meaning: string;
  evidence_family: "synthetic";
}

export interface PresenceObservationRow {
  provider: string;
  model: string;
  prompt_id: string;
  prompt_text: string;
  category: string;
  segment: string;
  run_index: number;
  mode: string;
  status: string;
  searched: boolean;
  search_queries: string[];
  brand_mentioned: boolean;
  domain_cited: boolean;
  domain_linked: boolean;
  pages_cited: string[];
  cited_domains: string[];
  recommended: boolean | null;
  answer_excerpt: string;
  error: string | null;
}

export interface PresenceRunDetail extends PresenceRun {
  metrics: {
    evidence_family: "synthetic";
    providers: string[];
    per_provider: Record<string, Record<string, PresenceMetric>>;
    combined: Record<string, PresenceMetric>;
    modes: Record<string, {
      per_provider: Record<string, Record<string, PresenceMetric>>;
      combined: Record<string, PresenceMetric>;
    }>;
    observed_domains: { domain: string; citations: number }[];
    min_observations_for_rate: number;
  };
  coverage: {
    providers_observed: number;
    providers_configured: number;
    prompts_observed: number;
    prompts_declared: number;
    observations_total: number;
    observations_ok: number;
    unavailable_by_status: Record<string, number>;
  };
  observations: PresenceObservationRow[];
}

export interface PresenceSuggestion {
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

export interface PresenceRunCreate {
  url: string;
  /**
   * Сайт кабінету, для якого замовлено прогін. Оголошується явно — з
   * переліку сайтів або з вибору у формі; за схожістю адрес звʼязок не
   * виводиться ніколи.
   */
  site_id?: string | null;
  brand: string;
  brand_aliases?: string[];
  category: string;
  services?: string[];
  location?: string | null;
  language?: string;
  idempotency_key?: string;
}

/** Обсяг майбутнього прогону — до запуску, без резервування права. */
export interface PresencePlan {
  enabled: boolean;
  providers: { provider: string; model: string; configured: boolean }[];
  modes: string[];
  prompts_planned: number;
  runs_per_prompt: number;
  observations_planned_per_provider: number;
  observations_planned_total: number;
  allowance_available: boolean;
  credits_available: number;
  can_start: boolean;
}

/** Комерційна пропозиція: як купити той самий продукт. */
export interface Offer {
  code: string;
  offer_type: "single" | "pack";
  display_name: string;
  description: string;
  currency: string;
  display_amount_minor: number | null;
  /** Знаків після коми в цій валюті — бекенд каже, клієнт не вгадує. */
  exponent: number;
  audit_credits: number;
  presence_credits: number;
  promo_eligible: boolean;
}

/**
 * Що з покупкою — і чи взяв за неї гроші провайдер.
 *
 * `charged` має три значення, і третє не зайве: `null` означає, що
 * провайдер не відповів. Показати на нього «кошти не списано» —
 * запросити до другої оплати того, хто вже заплатив.
 */
export interface PurchaseState {
  purchase_id: string;
  state: string;
  charged: boolean | null;
}

export interface OfferCheckout {
  purchase_id: string;
  provider_ref: string;
  url: string;
  discount_applied: boolean;
}
