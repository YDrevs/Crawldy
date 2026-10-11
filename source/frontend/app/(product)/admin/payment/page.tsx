"use client";

/**
 * Платіжний провайдер: те, чим справді користується каса.
 *
 * Значення приходять із робочої конфігурації сервера (збережене
 * адміністратором → оточення → дефолт), і кожне поле каже, звідки саме
 * воно взялося. Секрет не приходить сюди ніколи: видно «налаштовано» і
 * останні символи, а ввести можна лише нове значення.
 *
 * «Прибрати» не робить систему ненастроєною: воно видаляє збережений
 * рядок, і чинним знову стає значення з оточення, якщо воно там є.
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
} from "../../../components/primitives";
import {
  type CatalogueRow,
  type ConnectionTest,
  type PaymentConfig,
  type SettingField,
  ApiError,
  getPaymentConfig,
  savePaymentConfig,
  testPaymentConnection,
} from "../../../lib/admin-api";
import { useAdmin } from "../../../lib/admin-locale";
import { toAmountField } from "../../../lib/admin-pricing";
import { SecretField, StatusPill, useDraft } from "../ui";

export default function PaymentPage() {
  const { t } = useAdmin();
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [failed, setFailed] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [probe, setProbe] = useState<ConnectionTest | null>(null);
  const [probing, setProbing] = useState(false);
  const draft = useDraft();

  const load = useCallback(async () => {
    try {
      setConfig(await getPaymentConfig());
      setFailed("");
    } catch {
      setFailed(t("common.loadFailed"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed && config === null) return <Alert tone="danger">{failed}</Alert>;
  if (config === null) {
    return (
      <div className="flex justify-center py-16 text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const field = (key: string): SettingField =>
    config.fields.find((f) => f.key === key)!;

  const save = async () => {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      setConfig(await savePaymentConfig(draft.payload()));
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

  const runTest = async () => {
    setProbing(true);
    setProbe(null);
    try {
      setProbe(await testPaymentConnection());
    } catch (problem) {
      setProbe({
        ok: false,
        outcome: "network_error",
        detail: problem instanceof ApiError ? problem.message : "",
      });
    } finally {
      setProbing(false);
    }
  };

  const provider = field("billing_provider");
  const environment = field("paddle_env");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-primary">
          {t("payment.title")}
        </h1>
        <StatusPill
          tone={
            config.status === "configured"
              ? "success"
              : config.status === "fake"
                ? "warning"
                : "danger"
          }
          label={t(`payment.status.${config.status}`)}
        />
      </div>

      {config.problems.length > 0 ? (
        <Alert tone="danger">
          <ul className="flex flex-col gap-1">
            {config.problems.map((code) => (
              <li key={code}>{t(`payment.problem.${code}`)}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {config.status === "fake" ? (
        <Alert tone="warning">{t("payment.fakeWarning")}</Alert>
      ) : null}

      {!config.secrets_storage_available ? (
        <Alert tone="warning">{t("payment.secretsUnavailable")}</Alert>
      ) : null}

      <Panel>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field
            label={t("field.billing_provider")}
          >
            <Select
              value={draft.value(provider) ?? provider.value ?? ""}
              onChange={(e) => draft.set(provider.key, e.target.value)}
            >
              {provider.choices
                .filter((c) => c !== "fake" || config.fake_available)
                .map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
            </Select>
          </Field>

          <Field
            label={t("field.paddle_env")}
          >
            <Select
              value={draft.value(environment) ?? environment.value ?? ""}
              onChange={(e) => draft.set(environment.key, e.target.value)}
            >
              {environment.choices.map((choice) => (
                <option key={choice} value={choice}>
                  {choice}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Panel>

      <Panel>
        <div className="grid gap-4 sm:grid-cols-2">
          <SecretField field={field("paddle_api_key")} draft={draft} t={t} />
          <SecretField field={field("paddle_webhook_secret")} draft={draft} t={t} />
          <SecretField field={field("paddle_client_token")} draft={draft} t={t} />
          <Field
            label={t("field.paddle_timeout_s")}
          >
            <Input
              value={
                draft.value(field("paddle_timeout_s")) ??
                field("paddle_timeout_s").value ??
                ""
              }
              onChange={(e) => draft.set("paddle_timeout_s", e.target.value)}
            />
          </Field>
          <Field
            label={t("field.paddle_signature_tolerance_s")}
          >
            <Input
              value={
                draft.value(field("paddle_signature_tolerance_s")) ??
                field("paddle_signature_tolerance_s").value ??
                ""
              }
              onChange={(e) =>
                draft.set("paddle_signature_tolerance_s", e.target.value)
              }
            />
          </Field>
        </div>

        {error ? (
          <div className="mt-4">
            <Alert tone="danger">{error}</Alert>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button loading={busy} onClick={() => void save()}>
            {t("common.save")}
          </Button>
          {saved && !error ? (
            <span className="text-sm text-muted">{t("common.saved")}</span>
          ) : null}
        </div>
      </Panel>

      {/* Що продається і чи має це провайдер: лише стан. Ціни задаються
          на закладці «Ціни», прайси у провайдера створює й оновлює
          збереження — тут нічого не вписують (рішення власника 2026-09-05). */}
      <CataloguePanel
        rows={config.catalogue ?? []}
        published={config.published ?? null}
        provider={config.active_provider}
        t={t}
      />

      <Panel>
        <h2 className="text-base font-semibold text-foreground">
          {t("payment.webhook")}
        </h2>
        <p className="mt-2 break-all rounded-md bg-surface-sunken px-3 py-2 font-mono text-sm text-foreground">
          {config.webhook_url}
        </p>
        <p className="mt-2 text-sm text-muted">{t("payment.webhookHint")}</p>
      </Panel>

      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="quiet" loading={probing} onClick={() => void runTest()}>
            {t("common.test")}
          </Button>
          {probe ? (
            <StatusPill
              tone={probe.ok ? "success" : "danger"}
              label={t(`payment.test.${probe.outcome}`)}
            />
          ) : null}
          {probe?.latency_ms !== undefined ? (
            <span className="text-sm tabular-nums text-muted">{probe.latency_ms} ms</span>
          ) : null}
        </div>
        {probe?.detail ? (
          <p className="mt-2 break-words font-mono text-xs text-muted">{probe.detail}</p>
        ) : null}
        {probe?.catalogue ? <CatalogueCheck rows={probe.catalogue} t={t} /> : null}
      </Panel>
    </div>
  );
}

function amountOf(row: CatalogueRow): string {
  return row.amount_minor === null
    ? "—"
    : `${toAmountField(row.amount_minor, row.currency)} ${row.currency}`;
}

/**
 * Продукти каталогу й стан їхніх прайсів у чинного провайдера.
 *
 * Читається, не редагується: сума живе на закладці «Ціни», а прайс у
 * провайдера пише сервер при її збереженні. Після збереження налаштувань
 * провайдера тут же видно, що саме перепубліковано, а що ні — і чому.
 */
function CataloguePanel({
  rows,
  published,
  provider,
  t,
}: {
  rows: CatalogueRow[];
  published: CatalogueRow[] | null;
  provider: string;
  t: (key: string) => string;
}) {
  const failed = (published ?? []).filter((row) => row.outcome !== "published");
  return (
    <Panel>
      <h2 className="text-base font-semibold text-foreground">{t("catalogue.title")}</h2>
      <p className="mt-2 text-sm text-muted">{t("catalogue.hint")}</p>
      {published !== null ? (
        <div className="mt-3">
          <Alert tone={failed.length === 0 ? "success" : "danger"}>
            {failed.length === 0 ? (
              t("catalogue.saved")
            ) : (
              <>
                {t("catalogue.savedPartly")}{" "}
                {failed
                  .map((row) => `${row.name} — ${t(`catalogue.outcome.${row.outcome}`)}`)
                  .join("; ")}
              </>
            )}
          </Alert>
        </div>
      ) : null}
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("catalogue.empty")}</p>
      ) : (
        <ul className="mt-4 divide-y divide-border">
          {rows.map((row) => (
            <li
              key={`${row.kind}:${row.code}`}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground">{row.name}</div>
                <div className="text-xs text-muted">
                  <span className="tabular-nums">{amountOf(row)}</span>
                  {row.published && row.price_ref ? (
                    <span className="ms-2 font-mono">{row.price_ref}</span>
                  ) : null}
                </div>
              </div>
              <StatusPill
                tone={row.amount_minor === null ? "warning" : row.published ? "success" : "danger"}
                label={
                  row.amount_minor === null
                    ? t("catalogue.noPrice")
                    : row.published
                      ? `${t("catalogue.published")} · ${provider}`
                      : `${t("catalogue.unpublished")} · ${provider}`
                }
              />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Жива звірка після «Перевірити»: що провайдер має під нашими прайсами зараз. */
function CatalogueCheck({ rows, t }: { rows: CatalogueRow[]; t: (key: string) => string }) {
  return (
    <ul className="mt-3 flex flex-col gap-1.5">
      {rows.map((row) => {
        const tone = row.matches ? "success" : "danger";
        const label = row.matches
          ? t("catalogue.check.ok")
          : row.provider_has
            ? t("catalogue.check.mismatch")
            : t("catalogue.check.missing");
        const providerAmount =
          row.provider_amount_minor !== undefined && row.provider_currency
            ? `${toAmountField(row.provider_amount_minor, row.provider_currency)} ${row.provider_currency}`
            : null;
        return (
          <li key={`${row.kind}:${row.code}`} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-foreground">{row.name}</span>
            <span className="tabular-nums text-muted">{amountOf(row)}</span>
            <StatusPill tone={tone} label={label} />
            {!row.matches && providerAmount ? (
              <span className="tabular-nums text-muted">{providerAmount}</span>
            ) : null}
            {row.detail ? <span className="font-mono text-xs text-muted">{row.detail}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}
