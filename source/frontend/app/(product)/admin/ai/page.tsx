"use client";

/**
 * AI-моделі: провайдери, якими вимірюється Actual AI Presence.
 *
 * Це НЕ перевірки AI-готовності сайту (ai_ready, llm_visibility) — ті
 * рахує двигун аудиту й провайдерів не питає. Тут — виконавці живих
 * запитів до асистентів, і кожне поле сторінки справді впливає на
 * прогін: увімкнення пише політику, з якої раннер читає перелік
 * провайдерів, а модель іде в сам виклик.
 *
 * Дві половини конфігурації живуть у різних місцях і зберігаються
 * різними механізмами: політика (увімкнено, модель, бюджети) — в
 * `ai_domain_settings`, ключі — в робочій конфігурації. Сторінка
 * показує їх поруч, бо адміністраторові байдуже, де вони лежать, і
 * зберігає одним запитом, який усередині розкладає їх назад.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Field,
  Input,
  Panel,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "../../../components/primitives";
import {
  type AiConfig,
  type AiProviderView,
  type AuditCost,
  type ConnectionTest,
  type PresencePolicyView,
  ApiError,
  getAiConfig,
  getAuditCost,
  saveAiConfig,
  testAiProvider,
} from "../../../lib/admin-api";
import { cx } from "../../../lib/cx";
import { useAdmin } from "../../../lib/admin-locale";
import { SecretField, StatusPill, TABLE_SPACING, useDraft } from "../ui";

export default function AiModelsPage() {
  const { t, locale } = useAdmin();
  const [config, setConfig] = useState<AiConfig | null>(null);
  const [policy, setPolicy] = useState<PresencePolicyView | null>(null);
  const [failed, setFailed] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [probes, setProbes] = useState<Record<string, ConnectionTest | null>>({});
  const [probing, setProbing] = useState("");
  const [cost, setCost] = useState<AuditCost | null>(null);
  const draft = useDraft();

  const load = useCallback(async () => {
    try {
      const next = await getAiConfig();
      setConfig(next);
      setPolicy(next.policy);
      setFailed("");
    } catch {
      setFailed(t("common.loadFailed"));
    }
    // Каталог собівартості: вартість спостереження кожної моделі й
    // останній справжній аудит. Оцінку рахуємо тут із живих полів.
    void getAuditCost()
      .then(setCost)
      .catch(() => undefined);
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed && config === null) return <Alert tone="danger">{failed}</Alert>;
  if (config === null || policy === null) {
    return (
      <div className="flex justify-center py-16 text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const patchProvider = (
    name: string,
    patch: Partial<PresencePolicyView["providers"][string]>,
  ) =>
    setPolicy((prev) =>
      prev === null
        ? prev
        : {
            ...prev,
            providers: {
              ...prev.providers,
              [name]: { ...prev.providers[name]!, ...patch },
            },
          },
    );

  const save = async () => {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const next = await saveAiConfig({ policy, values: draft.payload() });
      setConfig(next);
      setPolicy(next.policy);
      draft.clear();
      setSaved(true);
    } catch (problem) {
      setError(
        problem instanceof ApiError
          ? `${t("common.saveFailed")} (${problem.status}): ${problem.message}`
          : t("common.saveFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const runTest = async (provider: string) => {
    setProbing(provider);
    setProbes((prev) => ({ ...prev, [provider]: null }));
    try {
      const outcome = await testAiProvider(provider);
      setProbes((prev) => ({ ...prev, [provider]: outcome }));
    } catch (problem) {
      setProbes((prev) => ({
        ...prev,
        [provider]: {
          ok: false,
          outcome: "error",
          detail: problem instanceof ApiError ? problem.message : "",
        },
      }));
    } finally {
      setProbing("");
    }
  };

  // `type="number"` навмисно не використовується: браузер домальовує до
  // нього власні стрілки, яких немає в жодному іншому полі продукту, і
  // поле починає виглядати чужим. `inputMode` дає числову клавіатуру на
  // телефоні, а межі значень усе одно перевіряє сервер.
  const num = (key: keyof PresencePolicyView, label: string) => (
    <Field label={label}>
      <Input
        inputMode="decimal"
        value={String(policy[key] as number)}
        onChange={(e) =>
          setPolicy({ ...policy, [key]: Number(e.target.value) } as PresencePolicyView)
        }
      />
    </Field>
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-primary">
          {t("ai.title")}
        </h1>
      </div>

      {!config.secrets_storage_available ? (
        <Alert tone="warning">{t("payment.secretsUnavailable")}</Alert>
      ) : null}

      <Panel>
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="size-4"
            checked={policy.enabled}
            onChange={(e) => setPolicy({ ...policy, enabled: e.target.checked })}
          />
          {t("ai.master")}
        </label>
        {!policy.enabled ? (
          <p className="mt-2 text-sm text-muted">{t("ai.masterOff")}</p>
        ) : null}
      </Panel>

      {config.providers.map((provider) => (
        <ProviderPanel
          key={provider.provider}
          provider={provider}
          policy={policy.providers[provider.provider]!}
          onPatch={(patch) => patchProvider(provider.provider, patch)}
          draft={draft}
          probe={probes[provider.provider] ?? null}
          probing={probing === provider.provider}
          onTest={() => void runTest(provider.provider)}
          t={t}
        />
      ))}

      <Panel>
        <h2 className="text-base font-semibold text-foreground">{t("ai.runParams")}</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {num("runs_per_prompt", t("ai.runsPerPrompt"))}
          {num("max_prompts", t("ai.maxPrompts"))}
          {num("retry_limit", t("ai.retryLimit"))}
          {num("provider_timeout_s", t("ai.timeout"))}
          {num("concurrency", t("ai.concurrency"))}
          {num("raw_retention_days", t("ai.retention"))}
        </div>
      </Panel>

      {cost ? (
        <AuditCostPanel
          t={t}
          lang={locale}
          cost={cost}
          providers={config.providers}
          policy={policy}
        />
      ) : null}

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <div className="flex items-center gap-3">
        <Button loading={busy} onClick={() => void save()}>
          {t("common.save")}
        </Button>
        {saved && !error ? (
          <span className="text-sm text-muted">{t("common.saved")}</span>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Собівартість одного повного аудиту присутності — окрема таблиця для
 * ціноутворення. Не чіпає налаштування провайдерів вище: лише читає з
 * них обрані моделі й параметри.
 *
 * Оцінка рахується ТУТ, із живих полів форми: кількість спостережень на
 * провайдера = промпти × режими × повтори, а вартість спостереження
 * береться за обраною моделлю кожного провайдера. Тому зміна моделі або
 * поля повторів/промптів одразу перераховує число — ще до збереження.
 *
 * Один аудит проганяє сітку через КОЖНОГО ввімкненого провайдера, тож
 * підсумок — сума рядків. Це й є число, від якого рахують продажну ціну.
 */
function AuditCostPanel({
  t,
  lang,
  cost,
  providers,
  policy,
}: {
  t: (key: string, params?: Record<string, string | number>) => string;
  lang: string;
  cost: AuditCost;
  providers: AiProviderView[];
  policy: PresencePolicyView;
}) {
  const money = (v: number | null) => (v === null ? "—" : `$${v.toFixed(2)}`);
  const when = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString(lang === "uk" ? "uk-UA" : "en-US") : "—";

  // Спостережень на провайдера — з ЖИВОЇ форми, не зі збереженого.
  const observations =
    Number(policy.max_prompts) * cost.modes * Number(policy.runs_per_prompt);

  // Рядок на кожного ВВІМКНЕНОГО провайдера з його обраною моделлю.
  const rows = providers
    .filter((p) => policy.providers[p.provider]?.enabled)
    .map((p) => {
      const model = policy.providers[p.provider]!.model;
      const cat = cost.models[`${p.provider}/${model}`] ?? null;
      const estimated = cat ? cat.cost_per_observation * observations : null;
      const actual = cost.last_audit?.per_provider[p.provider] ?? null;
      return { provider: p.provider, model, cat, estimated, actual };
    });

  const estTotal = rows.reduce((sum, r) => sum + (r.estimated ?? 0), 0);
  const hasEstGap = rows.some((r) => r.estimated === null);

  return (
    <Panel>
      <h2 className="text-base font-semibold text-foreground">
        {t("economics.title")}
      </h2>
      <p className="mt-1 text-sm text-muted">
        {t("economics.basis", {
          obs: observations,
          prompts: Number(policy.max_prompts),
          modes: cost.modes,
          repeats: Number(policy.runs_per_prompt),
        })}
      </p>

      <div className={cx("mt-3", TABLE_SPACING)}>
        <Table>
          <thead>
            <tr>
              <Th>{t("economics.model")}</Th>
              <Th numeric>{t("economics.price")}</Th>
              <Th numeric>{t("economics.obs")}</Th>
              <Th numeric>{t("economics.estimated")}</Th>
              <Th numeric>{t("economics.lastActual")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.provider}>
                <Td>
                  <span className="font-medium text-foreground">{r.model}</span>
                  <span className="ms-2 text-xs text-muted">{r.provider}</span>
                </Td>
                <Td numeric>
                  {r.cat ? (
                    <>
                      <span className="tabular-nums">
                        ${r.cat.input_usd_per_mtok} / ${r.cat.output_usd_per_mtok}
                      </span>
                      <span className="ms-1 text-xs text-muted">/M</span>
                    </>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </Td>
                <Td numeric>
                  <span className="tabular-nums">{observations}</span>
                </Td>
                <Td numeric>
                  <span className="tabular-nums text-foreground">
                    {money(r.estimated)}
                  </span>
                </Td>
                <Td numeric>
                  <span className="tabular-nums text-foreground">
                    {money(r.actual)}
                  </span>
                </Td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border font-medium">
              <Td>{t("economics.total")}</Td>
              <Td />
              <Td numeric>
                <span className="tabular-nums">{observations * rows.length}</span>
              </Td>
              <Td numeric>
                <span className="tabular-nums text-foreground">
                  {hasEstGap ? "≈ " : ""}
                  {money(estTotal)}
                </span>
              </Td>
              <Td numeric>
                <span className="tabular-nums text-foreground">
                  {money(cost.last_audit?.total_usd ?? null)}
                </span>
                {cost.last_audit ? (
                  <span className="ms-1 text-xs text-muted">
                    {when(cost.last_audit.at)}
                  </span>
                ) : null}
              </Td>
            </tr>
          </tfoot>
        </Table>
      </div>

      <p className="mt-3 text-xs text-muted">
        {t("economics.note", { source: cost.reference_source })}
      </p>
    </Panel>
  );
}

function ProviderPanel({
  provider,
  policy,
  onPatch,
  draft,
  probe,
  probing,
  onTest,
  t,
}: {
  provider: AiProviderView;
  policy: PresencePolicyView["providers"][string];
  onPatch: (patch: Partial<PresencePolicyView["providers"][string]>) => void;
  draft: ReturnType<typeof useDraft>;
  probe: ConnectionTest | null;
  probing: boolean;
  onTest: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  const models = provider.models.map((m) => m.model);
  // Налаштована модель могла зникнути з каталогу — вона лишається в
  // переліку, інакше форма мовчки переписала б її першою відомою.
  if (!models.includes(policy.model)) models.unshift(policy.model);

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">
          {t(`ai.provider.${provider.provider}`)}
        </h2>
        <div className="flex items-center gap-3">
          {/* Позначка каже про КЛЮЧ, прапорець — про вибір. Поки вона
              повторювала слово «увімкнено» поруч із тим самим словом,
              вона не додавала нічого. */}
          <StatusPill
            tone={provider.execution_configured ? "success" : "danger"}
            label={
              provider.execution_configured
                ? t("common.configured")
                : t("common.notConfigured")
            }
          />
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="size-4"
              checked={policy.enabled}
              onChange={(e) => onPatch({ enabled: e.target.checked })}
            />
            {t("common.enabled")}
          </label>
        </div>
      </div>

      {!provider.execution_configured ? (
        <p className="mt-2 text-sm text-danger">{t("ai.keyMissing")}</p>
      ) : null}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={t("common.model")}>
          <Select
            value={policy.model}
            onChange={(e) => onPatch({ model: e.target.value })}
          >
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </Select>
        </Field>

        {provider.backends.length > 0 ? (
          <Field label={t("ai.backend")}>
            <Select
              value={policy.backend ?? provider.backends[0]!}
              onChange={(e) => onPatch({ backend: e.target.value })}
            >
              {provider.backends.map((backend) => (
                <option key={backend} value={backend}>
                  {backend}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}

        {/* Без placeholder: сірий «US» у порожньому полі читався як
            значення, яке неможливо стерти. Формат пояснює підказка. */}
        {provider.supports_location ? (
          <Field label={t("ai.country")} hint={t("ai.countryHint")}>
            <Input
              value={policy.default_country ?? ""}
              onChange={(e) =>
                onPatch({ default_country: e.target.value.trim() || null })
              }
            />
          </Field>
        ) : null}

        {provider.settings.map((field) =>
          field.secret ? (
            <SecretField key={field.key} field={field} draft={draft} t={t} />
          ) : (
            <Field
              key={field.key}
              label={t(`field.${field.key}`)}
            >
              <Input
                value={draft.value(field) ?? field.value ?? ""}
                onChange={(e) => draft.set(field.key, e.target.value)}
              />
            </Field>
          ),
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="quiet" loading={probing} onClick={onTest}>
          {t("common.test")}
        </Button>
        {probe ? (
          <StatusPill
            tone={probe.ok ? "success" : "danger"}
            label={t(`ai.test.${probe.outcome}`)}
          />
        ) : null}
        {probe?.latency_ms !== undefined ? (
          <span className="text-sm tabular-nums text-muted">{probe.latency_ms} ms</span>
        ) : null}
        {provider.max_attempt_cost_usd !== null ? (
          <span className="text-xs text-muted">
            {t("ai.maxAttempt")}: ${provider.max_attempt_cost_usd}
          </span>
        ) : null}
      </div>
      {probe?.detail ? (
        <p className="mt-2 break-words font-mono text-xs text-muted">{probe.detail}</p>
      ) : null}
    </Panel>
  );
}
