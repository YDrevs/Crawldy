"use client";

/**
 * Actual AI Presence — окремий розділ, не частина звіту аудиту.
 *
 * Межа вимірювання стоїть поруч із провайдерами й результатом, а не
 * бейджем у шапці: читач питає про неї саме там, де дивиться на числа.
 * Змішаного «AI-балу» тут немає і не буде: кожна метрика показує x із
 * N, свій обсяг і те, чого вона НЕ означає.
 *
 * ## Сайт оголошується, а не вгадується
 *
 * Прогін, замовлений для сайту кабінету, несе його `site_id` — від
 * форми до бази. Порівнювати адреси, щоб «здогадатися», якому сайту
 * належить прогін, не можна: два сайти під одним доменом і один сайт
 * під двома адресами — звичайні випадки, а не крайні.
 *
 * Провайдери підписані офіційними назвами БЕЗ логотипів: правила
 * брендів (Google насамперед) вимагають окремого дозволу на логотип, а
 * текстова назва — номінативне використання, дозволене завжди. Жодних
 * «ChatGPT каже» чи «ви №N в AI»: спостереження через API — це
 * спостереження через API, і підписи кажуть рівно це.
 */

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../../components/AppShell";
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  Panel,
  Spinner,
} from "../../../components/primitives";
import {
  ApiError,
  createPresenceRun,
  suggestPresence,
  downloadPresenceReport,
  getPresencePlan,
  getPresenceRun,
  listPresenceRuns,
  listSites,
} from "../../../lib/api";
import { PROVIDER_LABELS, ProviderMark } from "../../../components/ProviderMark";
import { useLocale } from "../../../lib/locale";
import { problemKey } from "../../../lib/problem";
import type {
  PresenceMetric,
  PresencePlan,
  PresenceObservationRow,
  PresenceRun,
  PresenceRunDetail,
  Site,
} from "../../../lib/contracts";


const METRIC_ORDER = [
  "mention_presence",
  "citation_presence",
  "link_presence",
  "recommendation_presence",
  "branded_citation",
  "searched_share",
] as const;

const MODE_ORDER = ["natural", "explicit"] as const;

/**
 * `useSearchParams` вимагає межі очікування: без неї збірка Next
 * відмовляється прередерити сторінку. Прихід зі сторінки «Сайти»
 * несе `?site=`, тож параметр адреси тут не декоративний.
 */
export default function PresencePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-64 items-center justify-center text-muted">
          <Spinner className="size-5" />
        </div>
      }
    >
      <PresenceScreen />
    </Suspense>
  );
}

function PresenceScreen() {
  const { t, d } = useLocale();
  const params = useSearchParams();
  const [runs, setRuns] = useState<PresenceRun[] | null>(null);
  const [plan, setPlan] = useState<PresencePlan | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  // Сайт прогону: з переліку сайтів або з вибору у формі. Порожньо —
  // прогін поза контекстом сайту, і це дозволений стан.
  const [siteId, setSiteId] = useState<string>("");
  const [disabled, setDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<PresenceRunDetail | null>(null);
  const [form, setForm] = useState({
    url: "", brand: "", aliases: "", category: "", location: "",
  });
  // Що ми підставили з аудиту й звідки — щоб людина бачила, що правити.
  const [prefilled, setPrefilled] = useState<Record<string, string> | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Ключ ідемпотентності живе разом із заповненою формою: подвійний
  // клік шле той самий ключ і не створює другого прогону; нова форма —
  // новий ключ, тобто свідомий новий запуск.
  const idempotencyKey = useMemo(
    () => crypto.randomUUID(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [form.url, form.brand, form.category, form.location, form.aliases],
  );

  // Підстановка з аудиту: щойно адреса введена, бренд, варіанти
  // написання, категорія й місто беруться з прочитаного сайту.
  // Заповнене людиною не перезаписується — лише порожні поля.
  const prefill = useCallback(async (url: string) => {
    if (!url.trim()) return;
    try {
      const facts = await suggestPresence(url);
      setForm((prev) => ({
        ...prev,
        brand: prev.brand || facts.brand,
        aliases:
          prev.aliases ||
          facts.brand_aliases.filter((a: string) => a !== facts.brand).join(", "),
        category: prev.category || facts.category,
        location: prev.location || (facts.location ?? ""),
      }));
      setPrefilled(facts.sources);
    } catch {
      // Аудиту цього сайту ще немає — форма лишається порожньою, і це
      // чесно: вигадувати бренд і місто нам нема з чого.
      setPrefilled(null);
    }
  }, []);

  const reload = useCallback(async () => {
    try {
      setRuns(await listPresenceRuns());
      setPlan(await getPresencePlan().catch(() => null));
      setDisabled(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setDisabled(true);
      } else {
        // Ключ каталогу, не сирий detail: службові рядки бекенда — не
        // текст для людини.
        setError(problemKey(err));
      }
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    let cancelled = false;
    listSites()
      .then((rows) => {
        if (!cancelled) setSites(rows);
      })
      // Без переліку сайтів форма лишається робочою: адресу можна
      // ввести руками, і саме так запускають присутність для сайту,
      // якого в кабінеті ще немає.
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Прихід зі сторінки «Сайти»: сайт уже обраний, адреса підставлена,
  // решта полів заповнюється з прочитаного аудиту цього сайту.
  const requested = params.get("site");
  useEffect(() => {
    if (!requested) return;
    const site = sites.find((row) => row.id === requested);
    if (!site) return;
    setSiteId(site.id);
    setForm((prev) => (prev.url ? prev : { ...prev, url: site.origin }));
    void prefill(site.origin);
  }, [requested, sites, prefill]);

  // Остання присутність обраного сайту — за `site_id`, а не за
  // схожістю адрес. Перелік уже звужений організацією актора.
  const latestForSite =
    siteId && runs
      ? runs.filter((run) => run.site_id === siteId)[0] ?? null
      : null;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await createPresenceRun({
        url: form.url,
        site_id: siteId || null,
        brand: form.brand,
        brand_aliases: form.aliases
          .split(",")
          .map((a) => a.trim())
          .filter(Boolean),
        category: form.category,
        location: form.location.trim() || null,
        idempotency_key: idempotencyKey,
      });
      setForm({ url: "", brand: "", aliases: "", category: "", location: "" });
      setSiteId("");
      setPrefilled(null);
      await reload();
    } catch (err) {
      // 402 тут означає «немає перевірок присутності», і в цього стану
      // давно є власне речення.
      setError(problemKey(err, { 402: "presence.plan.noEntitlement" }));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <PageHeader
        title={t("presence.title")}
        description={t("presence.subtitle")}
      />

      {disabled ? (
        <Panel>
          <EmptyState icon="search" title={t("presence.unavailable")} />
        </Panel>
      ) : (
        <>
          {plan ? <PlanPanel plan={plan} /> : null}

          <Panel className="mb-6 p-5">
            <h2 className="mb-1 text-sm font-semibold">{t("presence.start")}</h2>
            <p className="mb-3 text-xs text-muted">{t("presence.start.note")}</p>
            {sites.length > 0 ? (
              <label className="mb-2 block">
                <span className="mb-1 block text-xs text-muted">
                  {t("presence.site")}
                </span>
                <select
                  value={siteId}
                  onChange={(e) => {
                    const chosen = sites.find((row) => row.id === e.target.value);
                    setSiteId(e.target.value);
                    if (chosen) {
                      setForm((prev) => ({ ...prev, url: chosen.origin }));
                      void prefill(chosen.origin);
                    }
                  }}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm sm:w-80"
                >
                  <option value="">{t("presence.siteAny")}</option>
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {latestForSite ? (
              <p className="mb-2 text-xs text-muted">
                {t("presence.siteLatest", {
                  date: d(latestForSite.finished_at ?? latestForSite.created_at),
                })}{" "}
                · {t("presence.observations")}: {latestForSite.observations_ok}/
                {latestForSite.observations_total}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ["url", "presence.form.url"],
                  ["brand", "presence.form.brand"],
                  ["aliases", "presence.form.aliases"],
                  ["category", "presence.form.category"],
                  ["location", "presence.form.location"],
                ] as const
              ).map(([field, key]) => (
                <input
                  key={field}
                  value={form[field]}
                  onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                  onBlur={field === "url" ? () => void prefill(form.url) : undefined}
                  placeholder={t(key)}
                  className="min-w-52 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                />
              ))}
              <Button
                icon="plus"
                onClick={() => void submit()}
                disabled={
                  submitting || !form.url || !form.brand || !form.category ||
                  (plan !== null && !plan.can_start)
                }
              >
                {t("presence.run")}
              </Button>
            </div>
            {prefilled ? (
              <p className="mt-2 text-xs text-muted">{t("presence.prefilled")}</p>
            ) : null}
            {plan !== null && !plan.can_start ? (
              <p className="mt-2 text-xs text-danger">{t("presence.noChecks")}</p>
            ) : null}
          </Panel>

          {error ? <Alert tone="danger">{t(error)}</Alert> : null}

          {runs && runs.length === 0 ? (
            <Panel>
              <EmptyState
                icon="search"
                title={t("presence.empty.title")}
                description={t("presence.empty.body")}
              />
            </Panel>
          ) : null}

          {runs?.map((run) => (
            <Panel key={run.id} className="mb-3 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-medium">{run.brand}</span>
                <span className="text-sm text-muted">{run.url}</span>
                <Badge tone={run.status === "completed" ? "success" : "neutral"}>
                  {/* Стан ішов сирим значенням бази: клієнт бачив
                      «completed» і «queued» англійською в будь-якій
                      мові кабінету. Каталог статусів існує давно. */}
                  {t(`status.${run.status}`)}
                </Badge>
                <span className="text-xs text-muted">
                  {t("presence.observations")}: {run.observations_ok}/
                  {run.observations_total}
                </span>
                <EntitlementBadge run={run} />
                <Button
                  variant="ghost"
                  onClick={() =>
                    void getPresenceRun(run.id).then(setDetail).catch(() => undefined)
                  }
                >
                  {t("presence.details")}
                </Button>
              </div>
              {detail?.id === run.id ? <RunDetail detail={detail} /> : null}
            </Panel>
          ))}
        </>
      )}

    </>
  );
}

/** Що саме буде виміряно — до запуску, разом з обмеженнями методу. */
function PlanPanel({ plan }: { plan: PresencePlan }) {
  const { t } = useLocale();
  return (
    <Panel className="mb-4 p-5">
      <h2 className="mb-2 text-sm font-semibold">{t("presence.plan.title")}</h2>
      <div className="mb-2 flex flex-wrap gap-2">
        {plan.providers.map((p) => (
          <Badge key={p.provider} tone={p.configured ? "neutral" : "warning"}>
            <ProviderMark provider={p.provider} muted={!p.configured} />
            {p.configured ? "" : ` — ${t("presence.plan.notConfigured")}`}
          </Badge>
        ))}
      </div>
      <p className="text-xs text-muted">
        {t("presence.plan.scope", {
          prompts: plan.prompts_planned,
          repeats: plan.runs_per_prompt,
          modes: plan.modes.length,
          total: plan.observations_planned_total,
        })}
      </p>
      <p className="mt-1 text-xs text-muted">{t("presence.plan.stochastic")}</p>
      <p className="mt-1 text-xs text-muted">{t("presence.plan.charge")}</p>
      <p className="mt-1 text-xs text-muted">
        {plan.allowance_available
          ? t("presence.plan.allowance")
          : t("presence.plan.credits", { count: plan.credits_available })}
      </p>
      <p className="mt-2 text-[11px] text-muted">
        {t("presence.plan.independence")}
      </p>
      {/* §4.3: не бейдж у шапці, а речення там, де дивляться на
          провайдерів. Воно тримає ту саму межу, що й звіт: ми міряємо
          відповіді API та пошукових можливостей, а не застосунки. */}
      <p className="mt-1 text-[11px] text-muted">{t("presence.boundary")}</p>
    </Panel>
  );
}

function EntitlementBadge({ run }: { run: PresenceRun }) {
  const { t } = useLocale();
  if (!run.entitlement_settled) return null;
  return run.deliverable ? (
    <Badge tone="neutral">{t("presence.entitlement.used")}</Badge>
  ) : (
    <Badge tone="warning">{t("presence.entitlement.returned")}</Badge>
  );
}

/**
 * Порядок результату — від огляду до доказів: покриття провайдерів,
 * згадки, цитати, промпти зі згадкою, конкуренти, стабільність, докази.
 */
function RunDetail({ detail }: { detail: PresenceRunDetail }) {
  // Експорт іде мовою кабінету: раніше тут стояло зашите "uk", і
  // англійський кабінет отримував український документ.
  const { t, n, locale } = useLocale();
  const modes = detail.metrics.modes ?? {};
  const ok = detail.observations.filter((o) => o.status === "ok");

  const mentionedPrompts = Array.from(
    new Set(
      ok.filter((o) => o.brand_mentioned).map((o) => o.prompt_text),
    ),
  );

  // Стабільність між повторами: скільки клітинок (промпт × провайдер ×
  // режим) дали РІЗНІ відповіді про згадку на повторах.
  const byCell = new Map<string, Set<boolean>>();
  for (const o of ok) {
    const key = `${o.provider}|${o.prompt_id}|${o.mode}`;
    if (!byCell.has(key)) byCell.set(key, new Set());
    byCell.get(key)!.add(o.brand_mentioned);
  }
  const unstable = Array.from(byCell.values()).filter((s) => s.size > 1).length;

  return (
    <div className="mt-4 border-t border-border pt-4">
      {/* Версія набору промптів — наш інструмент звірки двох
          прогонів, а не факт про бренд. Той самий клас, що й відбитки
          двигуна у звіті аудиту: читач із неї не дізнається нічого й
          діяти на неї не може. */}
      <p className="mb-3 text-xs text-muted">
        {t("presence.detail.provenance")}
      </p>

      {MODE_ORDER.map((mode) => {
        const block = modes[mode];
        if (!block) return null;
        return (
          <div key={mode} className="mb-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted">
              {t(`presence.mode.${mode}`)}
            </h3>
            <ProviderCoverage perProvider={block.per_provider} />
            <div className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {METRIC_ORDER.map((key) => {
                const metric = block.combined[key];
                if (!metric || metric.denominator === 0) return null;
                return <MetricCard key={key} id={key} metric={metric} />;
              })}
            </div>
          </div>
        );
      })}

      {mentionedPrompts.length > 0 ? (
        <div className="mt-4">
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted">
            {t("presence.mentionedPrompts")}
          </h3>
          <ul className="list-disc pl-5 text-sm">
            {mentionedPrompts.slice(0, 8).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {detail.metrics.observed_domains.length > 0 ? (
        <div className="mt-4">
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted">
            {t("presence.domains")}
          </h3>
          <p className="text-sm">
            {detail.metrics.observed_domains
              .slice(0, 10)
              .map((d) => `${d.domain} (${d.citations})`)
              .join(" · ")}
          </p>
        </div>
      ) : null}

      <p className="mt-3 text-xs text-muted">
        {n("presence.variance", unstable)}
      </p>

      <Evidence observations={ok} />

      <p className="mt-3 text-xs text-muted">
        {t("presence.coverage")}: {detail.coverage.observations_ok}/
        {detail.coverage.observations_total} ·{" "}
        {t("presence.providers")}: {detail.coverage.providers_observed}/
        {detail.coverage.providers_configured}
      </p>
      <p className="mt-1 text-[11px] text-muted">{t("presence.limitations")}</p>
      <p className="mt-1 text-[11px] text-muted">{t("presence.marks")}</p>
      {/* Два види одного прогону: загальний власнику, технічний
          спеціалісту. Дані під ними ті самі — різниться подання. */}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          variant="quiet"
          onClick={() =>
            void downloadPresenceReport(detail.id, locale, "general").catch(
              () => undefined,
            )
          }
        >
          {t("presence.exportGeneral")}
        </Button>
        <Button
          variant="quiet"
          onClick={() =>
            void downloadPresenceReport(detail.id, locale, "technical").catch(
              () => undefined,
            )
          }
        >
          {t("presence.exportTechnical")}
        </Button>
      </div>
    </div>
  );
}

/** Покриття по провайдерах: справжні/заплановані, згадки, цитати. */
function ProviderCoverage({
  perProvider,
}: {
  perProvider: Record<string, Record<string, PresenceMetric>>;
}) {
  const { t } = useLocale();
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {Object.entries(perProvider).map(([provider, metricsMap]) => {
        const mention = metricsMap.mention_presence;
        const citation = metricsMap.citation_presence;
        if (!mention) return null;
        return (
          <div
            key={provider}
            className="rounded-xl border border-border bg-surface p-3"
          >
            <div className="text-sm font-semibold">
              <ProviderMark provider={provider} />
            </div>
            <div className="mt-1 text-xs text-muted">
              {t("presence.providerLine", {
                mentioned: mention.numerator,
                observed: mention.denominator,
                cited: citation?.numerator ?? 0,
                unavailable: mention.unavailable,
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Уривки відповідей — доказ, який людина може перечитати сама. */
function Evidence({ observations }: { observations: PresenceObservationRow[] }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const interesting = observations.filter(
    (o) => o.brand_mentioned || o.domain_cited,
  );
  if (interesting.length === 0) return null;
  return (
    <div className="mt-4">
      <Button variant="ghost" onClick={() => setOpen(!open)}>
        {t("presence.evidence")} ({interesting.length})
      </Button>
      {open ? (
        <div className="mt-2 space-y-2">
          {interesting.slice(0, 10).map((o, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-surface p-3 text-xs"
            >
              <div className="font-semibold">
                <ProviderMark provider={o.provider} />{" · "}
                {t(`presence.mode.${o.mode}`)}{" · "}
                {o.searched
                  ? t("presence.searched")
                  : t("presence.noSearch")}
              </div>
              <div className="mt-1 text-muted">{o.prompt_text}</div>
              <div className="mt-1">{o.answer_excerpt}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MetricCard({ id, metric }: { id: string; metric: PresenceMetric }) {
  const { t } = useLocale();
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="text-xs font-semibold">{t(`presence.metric.${id}`)}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">
        {metric.numerator}/{metric.denominator}
        {metric.rate !== null ? (
          <span className="ml-2 text-sm text-muted">
            {Math.round(metric.rate * 100)}%
          </span>
        ) : null}
      </div>
      <div className="mt-1 text-[11px] leading-snug text-muted">
        {t(`presence.notmeaning.${metric.not_meaning}`)}
      </div>
    </div>
  );
}
