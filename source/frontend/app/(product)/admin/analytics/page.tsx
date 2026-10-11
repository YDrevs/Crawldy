"use client";

/**
 * Аналітика: продажі, клієнти, використання — з наявних таблиць.
 *
 * Жодне число тут не обчислюється в браузері: усе приходить готовим із
 * `/v1/admin/analytics`, бо правила обліку (що вважати продажем, як
 * рахувати повернення, кого виключати) — доменне рішення, а не
 * оформлення. Сторінка лише розкладає їх по картках і таблицях.
 *
 * Валюти не змішуються: кожна має власний блок. Сума двох валют — не
 * число, і показувати її означало б вигадати курс.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Field,
  Input,
  Panel,
  Spinner,
  Table,
  Td,
  Th,
} from "../../../components/primitives";
import { type Analytics, getAnalytics } from "../../../lib/admin-api";
import { useAdmin } from "../../../lib/admin-locale";
import { cx } from "../../../lib/cx";
import { Kpi, TABLE_SPACING } from "../ui";

function money(minor: number, currency: string): string {
  return `${(minor / 100).toFixed(2)} ${currency}`;
}

export default function AnalyticsPage() {
  const { t } = useAdmin();
  const [data, setData] = useState<Analytics | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState("");

  const load = useCallback(
    async (range: { from?: string; to?: string }) => {
      setBusy(true);
      try {
        setData(await getAnalytics(range));
        setFailed("");
      } catch {
        setFailed(t("common.loadFailed"));
      } finally {
        setBusy(false);
      }
    },
    [t],
  );

  useEffect(() => {
    void load({});
  }, [load]);

  if (failed && data === null) return <Alert tone="danger">{failed}</Alert>;
  if (data === null) {
    return (
      <div className="flex justify-center py-16 text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const { sales, customers, usage, credits, subscriptions, timeline } = data;
  const peakGross = Math.max(
    1,
    ...timeline.map((p) => Object.values(p.gross_minor).reduce((a, b) => a + b, 0)),
  );
  const peakRuns = Math.max(1, ...timeline.map((p) => p.audits + p.presence));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-primary">
          {t("analytics.title")}
        </h1>
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("analytics.from")}>
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label={t("analytics.to")}>
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
          <Button
            loading={busy}
            onClick={() =>
              void load({ from: from || undefined, to: to || undefined })
            }
          >
            {t("analytics.apply")}
          </Button>
          <Button
            variant="quiet"
            onClick={() => {
              setFrom("");
              setTo("");
              void load({});
            }}
          >
            {t("analytics.allTime")}
          </Button>
        </div>
      </div>

      {/* ── виручка ─────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-foreground">
          {t("analytics.revenue")}
        </h2>
        {sales.currencies.length === 0 ? (
          <Panel>
            <p className="text-sm text-muted">{t("analytics.empty")}</p>
          </Panel>
        ) : (
          sales.currencies.map((row) => (
            <Panel key={row.currency}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <Kpi
                  label={t("analytics.gross")}
                  value={money(row.gross_minor, row.currency)}
                />
                <Kpi
                  label={t("analytics.refunded")}
                  value={money(row.refunded_minor, row.currency)}
                  note={`${row.refunds}`}
                />
                <Kpi
                  label={t("analytics.net")}
                  value={money(row.net_minor, row.currency)}
                />
                <Kpi label={t("analytics.purchases")} value={String(row.purchases)} />
                <Kpi
                  label={t("analytics.average")}
                  value={
                    row.average_minor === null
                      ? t("common.none")
                      : money(row.average_minor, row.currency)
                  }
                />
              </div>
              {row.by_type.length > 0 ? (
                <div className={cx("mt-4", TABLE_SPACING)}>
                  <Table>
                    <thead>
                      <tr>
                        <Th>{t("analytics.byType")}</Th>
                        <Th numeric>{t("analytics.purchases")}</Th>
                        <Th numeric>{t("analytics.gross")}</Th>
                        <Th numeric>{t("analytics.refunded")}</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {row.by_type.map((kind) => (
                        <tr key={kind.offer_type}>
                          <Td>
                            {t(`analytics.type.${kind.offer_type}`) ===
                            `analytics.type.${kind.offer_type}`
                              ? kind.offer_type
                              : t(`analytics.type.${kind.offer_type}`)}
                          </Td>
                          <Td numeric>{kind.purchases}</Td>
                          <Td numeric>{money(kind.gross_minor, row.currency)}</Td>
                          <Td numeric>{money(kind.refunded_minor, row.currency)}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              ) : null}
            </Panel>
          ))
        )}
        {!sales.subscription_payments_recorded ? (
          <p className="text-xs text-muted">{t("analytics.noSubscriptionPayments")}</p>
        ) : null}
      </section>

      {/* ── клієнти ─────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-foreground">
          {t("analytics.customers")}
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Kpi
            label={t("analytics.customersTotal")}
            value={String(customers.purchasing_total)}
          />
          <Kpi
            label={t("analytics.customersNew")}
            value={String(customers.new_in_period)}
          />
          <Kpi
            label={t("analytics.customersRepeat")}
            value={String(customers.repeat_in_period)}
          />
        </div>
      </section>

      {/* ── використання ──────────────────────────────────────────────
          Службові прогони команди сюди не потрапляють: їх виключає сам
          запит (аудит із джерелом `admin_test`, прогін без організації).
          Рядок «виключено стільки-то» з екрана прибрано на прохання
          власника — правило від цього не змінилось. */}
      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-foreground">
          {t("analytics.usage")}
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            label={t("analytics.audits")}
            value={String(usage.audits_executed)}
            note={`${t("analytics.failed")}: ${usage.audits_failed}`}
          />
          <Kpi
            label={t("analytics.presence")}
            value={String(usage.presence_executed)}
            note={`${t("analytics.failed")}: ${usage.presence_failed}`}
          />
          <Kpi label={t("analytics.analyses")} value={String(usage.analyses_total)} />
          <Kpi label={t("analytics.domains")} value={String(usage.unique_domains)} />
        </div>
      </section>

      {/* ── одиниці й підписки ──────────────────────────────────────── */}
      {/* Одна під одною, а не поруч: у половині ширини чотири числові
          колонки не вміщались, і замість читабельної таблиці зʼявлялися
          дві смуги прокрутки (рішення власника 2026-09-06). */}
      <section className="grid gap-3">
        <Panel>
          <h2 className="text-base font-semibold text-foreground">
            {t("analytics.credits")}
          </h2>
          <div className={cx("mt-3", TABLE_SPACING)}>
            <Table>
              <thead>
                <tr>
                  <Th> </Th>
                  <Th numeric>{t("analytics.creditsSold")}</Th>
                  <Th numeric>{t("analytics.creditsGranted")}</Th>
                  <Th numeric>{t("analytics.creditsUsed")}</Th>
                  <Th numeric>{t("analytics.creditsRevoked")}</Th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(credits).map(([kind, row]) => (
                  <tr key={kind}>
                    <Td>
                      {t(`analytics.credit.${kind}`) === `analytics.credit.${kind}`
                        ? kind
                        : t(`analytics.credit.${kind}`)}
                    </Td>
                    <Td numeric>{row.sold}</Td>
                    <Td numeric>{row.granted}</Td>
                    <Td numeric>{row.used}</Td>
                    <Td numeric>{row.revoked}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {Object.keys(credits).length === 0 ? (
              <p className="text-sm text-muted">{t("analytics.empty")}</p>
            ) : null}
          </div>
        </Panel>

        <Panel>
          <h2 className="text-base font-semibold text-foreground">
            {t("analytics.subscriptions")}
          </h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Kpi
              label={t("analytics.subsActive")}
              value={String(subscriptions.active_now)}
            />
            <Kpi
              label={t("analytics.subsNew")}
              value={String(subscriptions.new_in_period)}
            />
            <Kpi
              label={t("analytics.subsCancelled")}
              value={String(subscriptions.cancelled_in_period)}
            />
          </div>
        </Panel>
      </section>

      {/* ── динаміка ────────────────────────────────────────────────── */}
      {timeline.length > 0 ? (
        <Panel>
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="text-base font-semibold text-foreground">
              {t("analytics.timeline")}
            </h2>
            <span className="text-xs text-muted">
              {t(`analytics.bucket.${data.period.bucket}`)}
            </span>
          </div>
          <div className="mt-4 overflow-x-auto">
            <div className="flex min-w-full items-end justify-start gap-2">
              {timeline.map((point) => {
                const gross = Object.values(point.gross_minor).reduce(
                  (a, b) => a + b,
                  0,
                );
                const runs = point.audits + point.presence;
                return (
                  <div
                    key={point.bucket}
                    // Стовпчик має стелю ширини: на двох точках пара
                    // смуг розтягувалася на пів екрана й читалася як
                    // заливка, а не як графік.
                    className="flex min-w-8 max-w-24 flex-1 flex-col items-center gap-1"
                    title={`${point.bucket} · ${point.purchases} · ${runs}`}
                  >
                    <div className="flex h-24 w-full items-end gap-0.5">
                      <div
                        className="w-1/2 rounded-t bg-brand"
                        style={{ height: `${Math.round((gross / peakGross) * 100)}%` }}
                      />
                      <div
                        className="w-1/2 rounded-t bg-accent"
                        style={{ height: `${Math.round((runs / peakRuns) * 100)}%` }}
                      />
                    </div>
                    <span className="text-2xs text-muted">
                      {point.bucket.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="mt-3 flex gap-4 text-xs text-muted">
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-sm bg-brand" />
              {t("analytics.gross")}
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-sm bg-accent" />
              {t("analytics.analyses")}
            </span>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
