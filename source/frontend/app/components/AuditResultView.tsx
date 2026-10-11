"use client";

/**
 * Повне подання результату аудиту — одне на весь продукт.
 *
 * Його рендерять два екрани з різним доступом: кабінет (сесія,
 * організація) і оплачений гостьовий перегляд (спроможність). Доступ
 * різний — подання одне: два звіти з часом розійшлися б, і клієнт,
 * який купив разовий аудит, бачив би інший продукт, ніж передплатник.
 *
 * Тому тут немає ані завантаження даних, ані способу авторизації, ані
 * завантажень файлів: `result` приходить готовим, а `downloads` —
 * вузол від викликача, бо адреси файлів у кабінету й гостя різні.
 *
 * ## Порядок відповідає порядку рішень, а не структурі даних
 *
 * Наскільки все погано → де саме → що робити першим → усе інше → чого
 * ми не бачили. Перелік із двадцяти однієї знахідки, поданий першим,
 * читається як докір; той самий перелік після трьох дій, з яких варто
 * почати, читається як довідник.
 *
 * ## Екран нічого не рахує
 *
 * Пріоритети, наслідки, приріст у балах, смуги, потенційний бал — усе
 * приходить готовим із сервера. Тут немає жодного `sort`, жодного
 * порівняння з порогом і жодної суми: відсортувати заново «за балами»
 * означало б мовчки видати інший план дій, ніж у звіті Word.
 *
 * ## Три речі, які легко намалювати неправдиво
 *
 * 1. **Виключений напрям — не нуль.** У нього `score: null` і власний
 *    підпис.
 * 2. **Приріст не сумується.** Кожен міряний окремо проти того самого
 *    базового бала.
 * 3. **Судження — не факт.** Низька впевненість підписана явно.
 */

import { Icon } from "./Icon";
import { Score, ScoreBar } from "./Score";
import {
  Alert,
  Badge,
  Disclosure,
  Panel,
  PanelHeader,
  SeverityBadge,
  cx,
} from "./primitives";
import { useLocale } from "../lib/locale";
import type {
  AccessibilitySnapshot,
  AuditResult,
  Coverage,
  PassedCheck,
  MissingData,
  ModuleScore,
  NextAction,
  Priority,
} from "../lib/contracts";

export function AuditResultView({ result }: { result: AuditResult }) {
  const { t } = useLocale();
  // Без загального бала приріст не «нуль», а невідомий: рахувати його
  // немає від чого. Різниця видима на екрані, тож вона й у типі.
  const scored = result.overall_score !== null;

  return (
    <>
      {result.localization.fell_back_strings > 0 ? (
        <div className="mb-6">
          <Alert tone="info">
            {t("result.fellBack", { count: result.localization.fell_back_strings })}
          </Alert>
        </div>
      ) : null}

      <Verdict result={result} />

      <section className="mt-6">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted">
          {t("result.dimensions")}
        </h2>
        <ul className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {result.modules.map((module) => (
            <ModuleCard key={module.module} module={module} />
          ))}
        </ul>
        <WeightGap result={result} />
      </section>

      <AccessibilityPanel snapshot={result.accessibility} />

      <PassedChecks checks={result.passed_checks ?? []} />

      {result.missing_data.length > 0 ? (
        <section className="mt-6">
          <Panel>
            <PanelHeader title={t("audit.missingData")} />
            <ul className="mt-3 flex flex-col gap-3">
              {result.missing_data.map((gap, index) => (
                <MissingRow key={`${gap.scope}-${gap.kind}-${index}`} gap={gap} />
              ))}
            </ul>
          </Panel>
        </section>
      ) : null}

      {result.next_actions.length > 0 ? (
        <section className="mt-6">
          <Panel padded={false}>
            <div className="p-5 pb-0">
              <PanelHeader
                title={t("audit.priorities")}
                description={t("result.independent")}
              />
            </div>
            <ol className="mt-4 border-t border-border">
              {result.next_actions.map((action) => (
                <ActionRow key={action.issue_key} action={action} scored={scored} />
              ))}
            </ol>
          </Panel>
        </section>
      ) : null}

      <section className="mt-6">
        <Panel padded={false}>
          <div className="p-5 pb-0">
            <PanelHeader
              title={t("result.everything")}
              action={
                <span className="text-sm text-muted">
                  {t("audit.findings")}: {result.summary.issues_total}
                </span>
              }
            />
          </div>
          <ol className="mt-4 border-t border-border">
            {result.priorities.map((priority) => (
              <PriorityRow key={priority.issue_key} priority={priority} scored={scored} />
            ))}
          </ol>
        </Panel>
      </section>

    </>
  );
}

/**
 * Бал, покриття й те, що з нього випливає.
 *
 * Покриття стоїть тут, а не в доказах: 20 адрес із 3407 дають бал,
 * поданий інакше так само впевнено, як бал за прочитаним сайтом. Без
 * цього рядка число бреше не помиляючись.
 */
function CoverageStateNote({ coverage }: { coverage: Coverage }) {
  const { t } = useLocale();
  // «scored» — звичайний випадок, і зайвий рядок був би шумом. Стан
  // показується лише тоді, коли він щось каже: бал притримано або
  // ширшому оглядові щось матеріально завадило.
  if (coverage.state !== "withheld" && coverage.state !== "scored_with_coverage_limitation") {
    return null;
  }
  const reasons = coverage.state_reasons
    .map((slug) => t(`coverage.reason.${slug}`))
    .join("; ");
  const key = coverage.state === "withheld" ? "coverage.withheld" : "coverage.limited";
  return <p className="mt-1 text-sm text-muted">{t(key, { reasons })}</p>;
}

function Verdict({ result }: { result: AuditResult }) {
  const { t, n } = useLocale();
  const { coverage } = result.summary;

  if (result.overall_score === null) {
    return (
      <Panel>
        <div className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold text-primary">{t("result.noScoreTitle")}</h2>
          <p className="max-w-measure text-secondary">{t("result.noScoreWhy")}</p>
          <p className="mt-1 text-sm text-muted">
            {n("audit.pagesRead", coverage.urls_known, { read: coverage.pages_read, known: coverage.urls_known })}
          </p>
          <CoverageStateNote coverage={coverage} />
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="flex flex-wrap items-start gap-x-10 gap-y-5">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">{t("audit.overall")}</p>
          <div className="mt-1">
            <Score value={result.overall_score} size="lg" />
          </div>
          <p className="mt-1 text-sm text-secondary">{t(`band.${result.overall_band}`)}</p>
        </div>

        <div className="min-w-56 flex-1">
          <ScoreBar value={result.overall_score} />
          {result.potential_score !== null &&
          result.potential_score > result.overall_score ? (
            <p className="mt-3 text-sm text-accent-text">
              {t("audit.potential", { score: result.potential_score })}
            </p>
          ) : null}
          <p className="mt-1 text-sm text-muted">
            {n("audit.pagesRead", coverage.urls_known, { read: coverage.pages_read, known: coverage.urls_known })}
          </p>
          <CoverageStateNote coverage={coverage} />
        </div>

        <dl className="flex gap-6">
          {(["critical", "high", "medium", "low"] as const).map((severity) => (
            <div key={severity}>
              <dt className="text-xs text-muted">{t(`severity.${severity}`)}</dt>
              <dd className="mt-0.5 text-lg tabular-nums text-primary">
                {result.summary.by_severity[severity] ?? 0}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </Panel>
  );
}

/**
 * Один із шести напрямів.
 *
 * Виключений напрям не має ані числа, ані шкали — лише підпис, чому його
 * тут немає. Порожня шкала на нулі читалась би як провал.
 */
function WeightGap({ result }: { result: AuditResult }) {
  const { t } = useLocale();
  const snapshot = result.accessibility;
  // Доступність пішла з переліку напрямів, а її вклад у загальний бал
  // лишився — тож видимі ваги сходяться до 90%. Мовчання тут читалося б
  // або як зламаний звіт, або як «цей знімок на бал не впливає».
  if (!snapshot || !snapshot.counts_toward_overall || !snapshot.overall_weight) {
    return null;
  }
  const shown = result.modules
    .filter((module) => !module.excluded)
    .reduce((sum, module) => sum + module.weight, 0);
  return (
    <p className="mt-3 text-xs text-muted">
      {t("result.weightGap", {
        shown: `${Math.round(shown * 100)}%`,
        hidden: `${Math.round(snapshot.overall_weight * 100)}%`,
      })}
    </p>
  );
}

function PassedChecks({ checks }: { checks: PassedCheck[] }) {
  const { t } = useLocale();
  // Нуль явно пройдених — секції немає: порожній зелений розділ
  // виглядав би як докір, а не довідка.
  if (checks.length === 0) {
    return null;
  }
  const byModule = new Map<string, PassedCheck[]>();
  for (const check of checks) {
    const list = byModule.get(check.module) ?? [];
    list.push(check);
    byModule.set(check.module, list);
  }
  return (
    <section className="mt-6">
      {/* <details> згорнуто за замовчуванням і доступне з клавіатури
          та для читачів екрана без жодного власного JS. */}
      <details className="rounded-lg border border-border bg-surface">
        <summary className="cursor-pointer select-none p-4 text-sm font-medium text-secondary">
          {t("passed.title", { count: String(checks.length) })}
          <span className="ml-2 text-xs font-normal text-muted">{t("passed.note")}</span>
        </summary>
        <div className="border-t border-border p-4">
          <ul className="flex flex-col gap-3">
            {[...byModule.entries()].map(([module, list]) => (
              <li key={module} className="text-sm">
                <span className="font-medium text-primary">{t(`module.${module}`)}</span>
                <ul className="mt-1 flex flex-col gap-1">
                  {list.map((check) => (
                    <li key={check.key} className="text-secondary">
                      {check.title}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      </details>
    </section>
  );
}

function AccessibilityPanel({ snapshot }: { snapshot: AccessibilitySnapshot | null }) {
  const { t } = useLocale();

  // Немає даних — кажемо це прямо. Нуль провалених перевірок при нулі
  // застосовних читався б як «усе гаразд», хоча означає протилежне.
  if (!snapshot || !snapshot.available) {
    return (
      <section className="mt-6">
        <Panel>
          <PanelHeader title={t("a11y.title")} />
          <p className="mt-3 text-sm text-muted">{t("a11y.unavailable")}</p>
          <p className="mt-2 text-xs text-muted">
            {snapshot && snapshot.counts_toward_overall && snapshot.overall_weight
              ? t("a11y.stillWeighted", {
                  percent: `${Math.round(snapshot.overall_weight * 100)}%`,
                })
              : t("a11y.notWeighted")}
          </p>
        </Panel>
      </section>
    );
  }

  const applicable = String(snapshot.applicable ?? 0);
  const failed = snapshot.failed ?? 0;

  return (
    <section className="mt-6">
      <Panel>
        <PanelHeader title={t("a11y.title")} />
        <p className="mt-3 text-sm text-secondary">
          {t("a11y.scope", { url: snapshot.measured_url ?? "" })}
        </p>
        <p className="mt-1 text-sm text-secondary">
          {failed > 0
            ? t("a11y.counts", {
                applicable,
                passed: String(snapshot.passed ?? 0),
                failed: String(failed),
              })
            : t("a11y.clean", { applicable })}
        </p>

        {snapshot.findings.length > 0 ? (
          <ul className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
            {snapshot.findings.map((finding) => (
              <li key={finding.audit_id} className="text-sm">
                <span className="text-primary">{finding.title || finding.audit_id}</span>
                {/* Посилання стоїть лише там, де наш чек справді спрацював:
                    мапа правил сама по собі покриття не доводить. */}
                {finding.also_reported_module ? (
                  <span className="ml-2 text-xs text-muted">
                    {t("a11y.alsoReported", {
                      module: t(`module.${finding.also_reported_module}`),
                    })}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}

        {snapshot.lighthouse_score !== null ? (
          <p className="mt-4 text-xs text-muted">
            {t("a11y.reference", { score: String(Math.round(snapshot.lighthouse_score)) })}
          </p>
        ) : null}
        <p className="mt-2 text-xs text-muted">{t("a11y.caveat")}</p>
        <p className="mt-2 text-xs text-muted">
          {snapshot.counts_toward_overall && snapshot.overall_weight
            ? t("a11y.stillWeighted", {
                percent: `${Math.round(snapshot.overall_weight * 100)}%`,
              })
            : t("a11y.notWeighted")}
        </p>
      </Panel>
    </section>
  );
}

function ModuleCard({ module }: { module: ModuleScore }) {
  const { t } = useLocale();
  const percent = `${Math.round(module.weight * 100)}%`;

  return (
    <li className="bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-medium text-primary">{t(`module.${module.module}`)}</h3>
        {module.excluded ? (
          <span className="text-sm text-muted">{t("result.notMeasured")}</span>
        ) : (
          <Score value={module.score} size="sm" />
        )}
      </div>

      {module.excluded ? (
        <p className="mt-2 text-xs text-muted">{t("result.excludedNote")}</p>
      ) : (
        <>
          <div className="mt-2">
            <ScoreBar value={module.score} />
          </div>
          <p className="mt-2 flex items-center gap-2 text-xs text-muted">
            <span>{t("result.weight", { percent })}</span>
            <span aria-hidden>·</span>
            <span>{t("audit.findings")}: {module.issues_count}</span>
          </p>
          {module.partial ? (
            <p className="mt-1 text-xs text-warning">{t("result.partialNote")}</p>
          ) : null}
        </>
      )}
    </li>
  );
}

/** Один пункт із «що робити першим»: дія, навіщо, скільки дасть. */
function ActionRow({ action, scored }: { action: NextAction; scored: boolean }) {
  const { t } = useLocale();
  return (
    <li className="flex gap-4 border-b border-border px-5 py-4 last:border-b-0">
      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-xs font-medium tabular-nums text-secondary">
        {action.rank}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-primary">{action.action}</p>
        <p className="mt-1 text-sm text-secondary">{action.why}</p>
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <Badge tone="neutral">{t(`module.${action.module}`)}</Badge>
          <span>{t(`effort.${action.effort}`)}</span>
          <Scope pages={action.affected_pages} />
        </p>
      </div>
      <Gain points={action.expected_gain_points} scored={scored} />
    </li>
  );
}

/**
 * Одна проблема з повного переліку.
 *
 * Доказ схований за розкриттям, наслідок — ні: рішення «братися чи ні»
 * ухвалюється за наслідком, а доказ потрібен уже тому, хто взявся.
 */
function PriorityRow({ priority, scored }: { priority: Priority; scored: boolean }) {
  const { t } = useLocale();
  const evidence = Object.entries(priority.evidence).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );

  return (
    <li id={priority.issue_key} className="scroll-mt-6 border-b border-border px-5 py-4 last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge
          severity={priority.severity}
          label={t(`severity.${priority.severity}`)}
        />
        <Badge tone="neutral">{t(`module.${priority.module}`)}</Badge>
        <Scope pages={priority.affected_pages} />
        {priority.confidence === "low" ? (
          <span className="inline-flex items-center gap-1 text-xs text-warning">
            <Icon name="alert" className="size-3.5" />
            {t("result.lowConfidence")}
          </span>
        ) : null}
        <span className="ms-auto shrink-0">
          <Gain points={priority.impact_points} scored={scored} small />
        </span>
      </div>

      <h3 className="mt-2 font-medium text-primary">{priority.title}</h3>
      <p className="mt-1 text-sm text-secondary">{priority.consequence}</p>

      <div className="mt-3">
        <Disclosure summary={t("result.evidence")}>
          <div className="flex flex-col gap-3 border-s-2 border-border ps-4 text-sm">
            <Detail label={t("result.problem")} text={priority.problem} />
            <Detail label={t("result.action")} text={priority.action} />

            {priority.confidence === "low" ? (
              <p className="text-warning">{t("result.lowConfidenceWhy")}</p>
            ) : null}

            {priority.affected_examples.length > 0 ? (
              <div>
                <p className="text-xs uppercase tracking-wide text-muted">
                  {t("result.examples")}
                </p>
                <ul className="mt-1 flex flex-col gap-0.5">
                  {priority.affected_examples.slice(0, 5).map((url) => (
                    <li key={url} className="truncate text-secondary">
                      {url}
                    </li>
                  ))}
                </ul>
                {priority.affected_examples.length > 5 ? (
                  <p className="mt-1 text-xs text-muted">
                    {t("result.moreExamples", {
                      count: priority.affected_examples.length - 5,
                    })}
                  </p>
                ) : null}
              </div>
            ) : null}

            {evidence.length > 0 ? (
              <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[auto_1fr]">
                {evidence.map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="font-mono text-xs text-muted">{key}</dt>
                    <dd className="break-words font-mono text-xs text-secondary">
                      {render(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>
        </Disclosure>
      </div>
    </li>
  );
}

/**
 * Скільки дасть виправлення — або чесне мовчання.
 *
 * «+0 to the score» — найгірший із можливих підписів: він каже, що дія
 * не варта нічого. Насправді нуль означає одне з двох, і жодне з них не
 * є «марно». Або бал зросте менше ніж на одиницю після округлення —
 * тоді так і пишемо. Або загального бала немає взагалі: на сайті, що
 * віддав 403, приріст рахувати немає від чого, і найцінніша дія в
 * переліку — «пустіть краулерів» — стояла б із підписом «+0».
 */
function Gain({
  points,
  scored,
  small = false,
}: {
  points: number;
  scored: boolean;
  small?: boolean;
}) {
  const { t } = useLocale();
  const size = small ? "text-xs" : "text-sm";

  if (!scored) return null;
  if (points <= 0) {
    return <span className={cx("shrink-0", size, "text-muted")}>{t("result.gainNone")}</span>;
  }
  return (
    <span className={cx("shrink-0 tabular-nums", size, "text-accent-text")}>
      {t("result.gain", { points })}
    </span>
  );
}

function Detail({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-secondary">{text}</p>
    </div>
  );
}

/**
 * Скільки сторінок зачеплено.
 *
 * Нуль тут означає не «жодної», а «проблема стосується сайту цілком» —
 * так двигун позначає знахідки з областю `site`. Надрукувати «0 pages»
 * було б просто неправдою.
 */
function Scope({ pages }: { pages: number }) {
  const { t, n } = useLocale();
  return (
    <span className="text-xs text-muted">
      {pages > 0 ? n("result.affected", pages) : t("result.siteWide")}
    </span>
  );
}

function MissingRow({ gap }: { gap: MissingData }) {
  const { t } = useLocale();
  return (
    <li className="border-s-2 border-warning ps-4">
      <p className="text-sm text-primary">{gap.reason}</p>
      {gap.note ? <p className="mt-0.5 text-sm text-muted">{gap.note}</p> : null}
      {gap.affects.length > 0 ? (
        <p className="mt-1 flex flex-wrap gap-1.5">
          {gap.affects.map((field) => (
            <Badge key={field} tone="neutral">
              {t(`module.${moduleOf(field)}`)}
            </Badge>
          ))}
        </p>
      ) : null}
    </li>
  );
}

// ── дрібне форматування ────────────────────────────────────────────────────

export function hostOf(origin: string): string {
  try {
    return new URL(origin).host;
  } catch {
    return origin;
  }
}

export function fullDate(locale: string, iso: string): string {
  return new Date(iso).toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** `seo_score` → `seo`. Поле звіту й назва модуля різняться історично. */
function moduleOf(field: string): string {
  const name = field.replace(/_score$/, "");
  return name === "speed" ? "performance" : name;
}

function render(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

