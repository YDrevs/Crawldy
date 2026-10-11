"use client";

/**
 * Тестування: справжні конвеєри без комерційних обмежень.
 *
 * Дві вкладки — перевірка сайту й Actual AI Presence. Обидві ставлять
 * задачу в ту саму чергу, яку виконує той самий воркер: жодного
 * макетного шляху тут немає, інакше тест не доводив би нічого.
 *
 * Прогони не витрачають квоту й кредити клієнта, не створюють продажу
 * й виключені з аналітики — це властивість самого запису (аудит із
 * джерелом `admin_test`, прогін без організації), а не фільтра екрана.
 *
 * Показується ВСЕ, що записав конвеєр: бал і бали напрямів, кожна
 * знахідка з доказом, деградації, версії, сторінки, спроби. Клієнтський
 * екран стискає це до головного; калібрування дивиться на все.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Disclosure,
  Field,
  Input,
  Panel,
  Select,
  Spinner,
  Table,
  Tabs,
  Td,
  Th,
} from "../../../components/primitives";
import {
  type AuditCost,
  type TestAuditDetail,
  type TestAuditRow,
  type TestPresenceDetail,
  type TestPresenceRow,
  ApiError,
  getAiConfig,
  getAuditCost,
  getTestAudit,
  getTestPresence,
  listTestAudits,
  listTestPresence,
  startTestAudit,
  startTestPresence,
  testPresenceReportUrl,
  testReportUrl,
} from "../../../lib/admin-api";
import { useAdmin } from "../../../lib/admin-locale";
import { cx } from "../../../lib/cx";
import { StatusPill, TABLE_SPACING } from "../ui";

/** Стан прогону — кольором, а не лише словом. */
function runTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "completed") return "success";
  if (status === "partial") return "warning";
  if (status === "failed") return "danger";
  return "neutral";
}

export default function TestingPage() {
  const { t, locale } = useAdmin();
  const [tab, setTab] = useState("audit");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-primary">
          {t("testing.title")}
        </h1>
      </div>

      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          { id: "audit", label: t("testing.tab.audit") },
          { id: "presence", label: t("testing.tab.presence") },
        ]}
      />

      {tab === "audit" ? <AuditTesting t={t} lang={locale} /> : <PresenceTesting t={t} lang={locale} />}
    </div>
  );
}

// ── перевірка сайту ─────────────────────────────────────────────────────

function AuditTesting({
  t,
  lang,
}: {
  t: (key: string) => string;
  lang: string;
}) {
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState("25");
  const [maxDepth, setMaxDepth] = useState("2");
  const [render, setRender] = useState(true);
  const [rows, setRows] = useState<TestAuditRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState("");
  const [detail, setDetail] = useState<TestAuditDetail | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await listTestAudits());
    } catch {
      setRows([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Поки прогін іде, перелік оновлюється сам: інакше єдиний спосіб
  // побачити завершення — тиснути кнопку, і людина тисне.
  useEffect(() => {
    const pending = (rows ?? []).some(
      (r) => r.status === "queued" || r.status === "running",
    );
    if (!pending) return;
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [rows, refresh]);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await startTestAudit({
        url,
        options: {
          max_pages: Number(maxPages),
          max_depth: Number(maxDepth),
          render,
        },
      });
      setUrl("");
      await refresh();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "error");
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    if (openId === id) {
      setOpenId("");
      setDetail(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    try {
      setDetail(await getTestAudit(id, lang));
    } catch {
      setDetail(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t("testing.url")}>
            <Input
              value={url}
              placeholder="https://example.com"
              onChange={(e) => setUrl(e.target.value)}
            />
          </Field>
          <Field label={t("testing.maxPages")}>
            <Input
              inputMode="numeric"
              value={maxPages}
              onChange={(e) => setMaxPages(e.target.value)}
            />
          </Field>
          <Field label={t("testing.maxDepth")}>
            <Input
              inputMode="numeric"
              value={maxDepth}
              onChange={(e) => setMaxDepth(e.target.value)}
            />
          </Field>
          <Field label={t("testing.render")}>
            <label className="flex h-10 items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="size-4"
                checked={render}
                onChange={(e) => setRender(e.target.checked)}
              />
              {t("common.yes")}
            </label>
          </Field>
        </div>
        {error ? (
          <div className="mt-4">
            <Alert tone="danger">{error}</Alert>
          </div>
        ) : null}
        <div className="mt-4">
          <Button loading={busy} disabled={!url.trim()} onClick={() => void start()}>
            {t("testing.start")}
          </Button>
        </div>
      </Panel>

      <Panel>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground">
            {t("testing.recent")}
          </h2>
          <Button variant="ghost" onClick={() => void refresh()}>
            {t("common.refresh")}
          </Button>
        </div>
        {rows === null ? (
          <div className="flex justify-center py-8 text-muted">
            <Spinner className="size-5" />
          </div>
        ) : rows.length === 0 ? (
          <p className="mt-3 text-sm text-muted">{t("testing.noRuns")}</p>
        ) : (
          <div className={cx("mt-3", TABLE_SPACING)}>
            <Table>
              <thead>
                <tr>
                  <Th>{t("testing.url")}</Th>
                  <Th>{t("testing.status")}</Th>
                  <Th numeric>{t("testing.score")}</Th>
                  <Th>{t("testing.finished")}</Th>
                  <Th> </Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <Td>
                      <span className="break-all">{row.url}</span>
                    </Td>
                    <Td>
                      <StatusPill tone={runTone(row.status)} label={row.status} />
                    </Td>
                    <Td numeric>{row.score_overall ?? "—"}</Td>
                    <Td>{row.finished_at?.slice(0, 19).replace("T", " ") ?? "—"}</Td>
                    <Td>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button variant="ghost" onClick={() => void open(row.id)}>
                          {t("testing.details")}
                        </Button>
                        {row.status === "completed" || row.status === "partial" ? (
                          <>
                            <a
                              className="text-sm text-accent hover:underline"
                              href={testReportUrl(row.id, "json", lang)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {t("testing.reportJson")}
                            </a>
                            <a
                              className="text-sm text-accent hover:underline"
                              href={testReportUrl(row.id, "docx", lang)}
                            >
                              {t("testing.reportDocx")}
                            </a>
                            <a
                              className="text-sm text-accent hover:underline"
                              href={testReportUrl(row.id, "docx_owner", lang)}
                            >
                              {t("testing.reportOwner")}
                            </a>
                          </>
                        ) : null}
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Panel>

      {openId ? (
        detail === null ? (
          <div className="flex justify-center py-8 text-muted">
            <Spinner className="size-5" />
          </div>
        ) : (
          <AuditDiagnostics detail={detail} t={t} />
        )
      ) : null}
    </div>
  );
}

function AuditDiagnostics({
  detail,
  t,
}: {
  detail: TestAuditDetail;
  t: (key: string) => string;
}) {
  const run = detail.run;
  const scores = Object.entries(run.scores ?? {});
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill tone={runTone(run.status)} label={run.status} />
          <span className="text-sm text-muted">{run.url}</span>
          <span className="ms-auto text-xl font-semibold tabular-nums text-primary">
            {run.score_overall ?? "—"}
          </span>
        </div>
        {run.error ? (
          <p className="mt-2 font-mono text-xs text-danger">{run.error}</p>
        ) : null}
        {scores.length > 0 ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {scores.map(([module, value]) => (
              <div
                key={module}
                className="rounded-md border border-border bg-surface-sunken px-3 py-2"
              >
                <p className="text-2xs uppercase tracking-wide text-muted">{module}</p>
                <p className="text-base font-semibold tabular-nums text-primary">
                  {value}
                </p>
              </div>
            ))}
          </div>
        ) : null}
      </Panel>

      <Panel>
        <h2 className="text-base font-semibold text-foreground">
          {t("testing.issues")} · {detail.issues.length}
        </h2>
        <div className="mt-3 flex flex-col gap-2">
          {detail.issues.map((issue) => (
            <Disclosure
              key={issue.id}
              summary={
                <span className="flex flex-wrap items-center gap-2 text-start">
                  <span className="font-mono text-2xs text-muted">{issue.issue_key}</span>
                  <span className="text-sm text-foreground">{issue.title}</span>
                  <span className="text-2xs uppercase tracking-wide text-muted">
                    {issue.severity}
                    {issue.confidence ? ` · ${issue.confidence}` : ""}
                  </span>
                </span>
              }
            >
              <div className="flex flex-col gap-2 text-sm text-secondary">
                <p>{issue.description}</p>
                <p className="text-foreground">{issue.recommendation}</p>
                {issue.page_url ? (
                  <p className="break-all text-xs text-muted">
                    {t("testing.page")}: {issue.page_url}
                  </p>
                ) : null}
                <pre className="overflow-x-auto rounded-md bg-surface-sunken p-3 text-2xs text-muted">
                  {JSON.stringify(issue.evidence, null, 2)}
                </pre>
              </div>
            </Disclosure>
          ))}
        </div>
      </Panel>

      <Panel>
        <h2 className="text-base font-semibold text-foreground">
          {t("testing.diagnostics")}
        </h2>
        <div className="mt-3 flex flex-col gap-2">
          <Disclosure summary={<span>degraded · {run.degraded.length}</span>}>
            <pre className="overflow-x-auto rounded-md bg-surface-sunken p-3 text-2xs text-muted">
              {JSON.stringify(run.degraded, null, 2)}
            </pre>
          </Disclosure>
          <Disclosure summary={<span>pages · {run.pages.length}</span>}>
            <div className={TABLE_SPACING}>
            <Table>
              <thead>
                <tr>
                  <Th>URL</Th>
                  <Th numeric>HTTP</Th>
                  <Th numeric>ms</Th>
                  <Th numeric>depth</Th>
                </tr>
              </thead>
              <tbody>
                {run.pages.map((page) => (
                  <tr key={page.url}>
                    <Td>
                      <span className="break-all">{page.url}</span>
                    </Td>
                    <Td numeric>{page.status_code ?? "—"}</Td>
                    <Td numeric>{page.response_ms ?? "—"}</Td>
                    <Td numeric>{page.depth}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            </div>
          </Disclosure>
          <Disclosure summary={<span>{t("testing.raw")}</span>}>
            <pre className="overflow-x-auto rounded-md bg-surface-sunken p-3 text-2xs text-muted">
              {JSON.stringify(
                {
                  quota_source: run.quota_source,
                  skipped_modules: run.skipped_modules,
                  versions: run.versions,
                  progress: run.progress,
                  evidence: run.evidence,
                  attempt_log: run.attempt_log,
                  options: run.options,
                },
                null,
                2,
              )}
            </pre>
          </Disclosure>
        </div>
      </Panel>
    </div>
  );
}

// ── Actual AI Presence ──────────────────────────────────────────────────

function PresenceTesting({
  t,
  lang,
}: {
  t: (key: string) => string;
  lang: string;
}) {
  const [url, setUrl] = useState("");
  const [brand, setBrand] = useState("");
  const [aliases, setAliases] = useState("");
  const [category, setCategory] = useState("");
  const [services, setServices] = useState("");
  const [location, setLocation] = useState("");
  const [language, setLanguage] = useState("en");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [providers, setProviders] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<AuditCost | null>(null);
  const [rows, setRows] = useState<TestPresenceRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState("");
  const [detail, setDetail] = useState<TestPresenceDetail | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await listTestPresence());
    } catch {
      setRows([]);
    }
    // Перелік моделей для benchmark-override — з каталогу собівартості.
    void getAuditCost()
      .then(setCatalog)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void refresh();
    // Перелік провайдерів — з тієї самої конфігурації, що керує
    // виконанням: вимкнений провайдер не має пропонуватися до запуску.
    void getAiConfig()
      .then((config) =>
        setProviders(
          config.providers.filter((p) => p.enabled).map((p) => p.provider),
        ),
      )
      .catch(() => setProviders([]));
  }, [refresh]);

  // Моделі, доступні для обраного провайдера — з каталогу собівартості.
  // Benchmark-override має сенс лише для одного провайдера, тож поле
  // моделі зʼявляється тільки коли провайдер обрано.
  const modelOptions = Object.values(catalog?.models ?? {})
    .filter((m) => m.provider === provider)
    .map((m) => m.model);

  useEffect(() => {
    const pending = (rows ?? []).some(
      (r) => r.status === "queued" || r.status === "running",
    );
    if (!pending) return;
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [rows, refresh]);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await startTestPresence({
        url,
        brand,
        brand_aliases: aliases
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        category,
        services: services
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        location: location.trim() || null,
        language,
        provider: provider || null,
        model: provider && model ? model : null,
      });
      await refresh();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "error");
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    if (openId === id) {
      setOpenId("");
      setDetail(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    try {
      setDetail(await getTestPresence(id));
    } catch {
      setDetail(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t("testing.url")}>
            <Input
              value={url}
              placeholder="https://example.com"
              onChange={(e) => setUrl(e.target.value)}
            />
          </Field>
          <Field label={t("testing.brand")}>
            <Input value={brand} onChange={(e) => setBrand(e.target.value)} />
          </Field>
          <Field label={t("testing.aliases")}>
            <Input value={aliases} onChange={(e) => setAliases(e.target.value)} />
          </Field>
          <Field label={t("testing.category")}>
            <Input value={category} onChange={(e) => setCategory(e.target.value)} />
          </Field>
          <Field label={t("testing.services")}>
            <Input value={services} onChange={(e) => setServices(e.target.value)} />
          </Field>
          <Field label={t("testing.location")}>
            <Input value={location} onChange={(e) => setLocation(e.target.value)} />
          </Field>
          <Field label={t("testing.language")}>
            <Select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en">en</option>
              <option value="uk">uk</option>
            </Select>
          </Field>
          <Field label={t("testing.provider")}>
            <Select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setModel("");
              }}
            >
              <option value="">{t("testing.allProviders")}</option>
              {providers.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </Field>
          {provider && modelOptions.length > 0 ? (
            <Field label={t("testing.model")}>
              <Select value={model} onChange={(e) => setModel(e.target.value)}>
                <option value="">{t("testing.modelDefault")}</option>
                {modelOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}
        </div>
        {error ? (
          <div className="mt-4">
            <Alert tone="danger">{error}</Alert>
          </div>
        ) : null}
        <div className="mt-4">
          <Button
            loading={busy}
            disabled={!url.trim() || !brand.trim()}
            onClick={() => void start()}
          >
            {t("testing.start")}
          </Button>
        </div>
      </Panel>

      <Panel>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground">
            {t("testing.recent")}
          </h2>
          <Button variant="ghost" onClick={() => void refresh()}>
            {t("common.refresh")}
          </Button>
        </div>
        {rows === null ? (
          <div className="flex justify-center py-8 text-muted">
            <Spinner className="size-5" />
          </div>
        ) : rows.length === 0 ? (
          <p className="mt-3 text-sm text-muted">{t("testing.noRuns")}</p>
        ) : (
          <div className={cx("mt-3", TABLE_SPACING)}>
            <Table>
              <thead>
                <tr>
                  <Th>{t("testing.url")}</Th>
                  <Th>{t("testing.brand")}</Th>
                  <Th>{t("testing.status")}</Th>
                  <Th numeric>{t("testing.observations")}</Th>
                  <Th numeric>{t("testing.cost")}</Th>
                  <Th> </Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    {/* Колонка зветься «адреса сайту» — у ній і має бути
                        адреса. Бренд стоїть окремо: у присутності це
                        інша величина, і саме його шукають у відповідях
                        асистентів. */}
                    <Td>
                      <span className="break-all">{row.url}</span>
                    </Td>
                    <Td>{row.brand}</Td>
                    <Td>
                      <StatusPill tone={runTone(row.status)} label={row.status} />
                    </Td>
                    <Td numeric>
                      {row.observations_ok}/{row.observations_total}
                    </Td>
                    <Td numeric>{row.cost_usd.toFixed(4)}</Td>
                    <Td>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button variant="ghost" onClick={() => void open(row.id)}>
                          {t("testing.details")}
                        </Button>
                        {row.status === "completed" ? (
                          <>
                            <a
                              className="text-sm text-accent hover:underline"
                              href={testPresenceReportUrl(row.id, "general", lang)}
                            >
                              {t("testing.reportOwner")}
                            </a>
                            <a
                              className="text-sm text-accent hover:underline"
                              href={testPresenceReportUrl(row.id, "technical", lang)}
                            >
                              {t("testing.reportDocx")}
                            </a>
                          </>
                        ) : null}
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Panel>

      {openId ? (
        detail === null ? (
          <div className="flex justify-center py-8 text-muted">
            <Spinner className="size-5" />
          </div>
        ) : (
          <PresenceDiagnostics detail={detail} t={t} />
        )
      ) : null}
    </div>
  );
}

function PresenceDiagnostics({
  detail,
  t,
}: {
  detail: TestPresenceDetail;
  t: (key: string) => string;
}) {
  const { run, observations, coverage } = detail;
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill tone={runTone(run.status)} label={run.status} />
          <span className="text-sm text-muted">{run.brand}</span>
          <span className="text-sm text-muted">{run.origin}</span>
          <span className="ms-auto text-sm tabular-nums text-muted">
            ${run.cost_usd.toFixed(4)}
          </span>
        </div>
        {run.error ? (
          <p className="mt-2 font-mono text-xs text-danger">{run.error}</p>
        ) : null}
        <pre className="mt-3 overflow-x-auto rounded-md bg-surface-sunken p-3 text-2xs text-muted">
          {JSON.stringify(coverage, null, 2)}
        </pre>
      </Panel>

      <Panel>
        <h2 className="text-base font-semibold text-foreground">
          {t("testing.mentions")} · {observations.length}
        </h2>
        <div className="mt-3 flex flex-col gap-2">
          {observations.map((o, index) => (
            <Disclosure
              key={`${o.provider}-${o.prompt_id}-${o.mode}-${o.run_index}-${index}`}
              summary={
                <span className="flex flex-wrap items-center gap-2 text-start">
                  <span className="font-mono text-2xs text-muted">
                    {o.provider} · {o.model}
                  </span>
                  <span className="text-sm text-foreground">{o.prompt_text}</span>
                  <span className="text-2xs uppercase tracking-wide text-muted">
                    {o.status}
                    {o.brand_mentioned ? ` · ${t("testing.mentioned")}` : ""}
                    {o.domain_cited ? ` · ${t("testing.cited")}` : ""}
                    {o.domain_linked ? ` · ${t("testing.linked")}` : ""}
                  </span>
                </span>
              }
            >
              <div className="flex flex-col gap-2 text-sm text-secondary">
                {o.error ? (
                  <p className="font-mono text-xs text-danger">{o.error}</p>
                ) : null}
                {o.answer_excerpt ? (
                  <p className="whitespace-pre-wrap rounded-md bg-surface-sunken p-3 text-xs">
                    {o.answer_excerpt}
                  </p>
                ) : null}
                <p className="text-xs text-muted">
                  {t("testing.tokens")}: {o.input_tokens} / {o.output_tokens} ·{" "}
                  {t("testing.searched")}: {o.searched ? t("common.yes") : t("common.no")}{" "}
                  · {t("testing.duration")}: {o.duration_ms} · ${o.cost_usd.toFixed(6)}
                </p>
                {o.cited_domains.length > 0 ? (
                  <p className="break-all text-xs text-muted">
                    {o.cited_domains.join(", ")}
                  </p>
                ) : null}
              </div>
            </Disclosure>
          ))}
        </div>
      </Panel>

      <Panel>
        <Disclosure summary={<span>{t("testing.raw")}</span>}>
          <pre className="overflow-x-auto rounded-md bg-surface-sunken p-3 text-2xs text-muted">
            {JSON.stringify(
              { policy_snapshot: run.policy_snapshot, metrics: detail.metrics },
              null,
              2,
            )}
          </pre>
        </Disclosure>
      </Panel>
    </div>
  );
}
