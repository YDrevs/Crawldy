"use client";

/**
 * Зарахування оплат, про які провайдер не повідомив.
 *
 * Тут перелічені покупки, за які людина заплатила (або відкрила касу й
 * пішла), а перевіреної події від провайдера ми не отримали: збій
 * доставки, недоступний сервер, помилка адреси сповіщень.
 *
 * Дві дії й різниця між ними принципова. «Звірити» лише питає провайдера
 * і нічого не змінює. «Зарахувати» питає його ще раз і, ЯКЩО він
 * підтверджує оплату, видає куплене. Кнопка не має повноважень відкрити
 * доступ самотужки — вона має повноваження запитати.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Panel,
  Spinner,
  Table,
  Td,
  Th,
} from "../../../components/primitives";
import {
  ApiError,
  sweepPendingPayments,
  creditPendingPayment,
  listPendingPayments,
  verifyAllPendingPayments,
  verifyPendingPayment,
  type PendingPayment,
  type SettlementAnswer,
  type SweepReport,
} from "../../../lib/admin-api";
import { useAdmin } from "../../../lib/admin-locale";
import { cx } from "../../../lib/cx";
import { StatusPill, TABLE_SPACING } from "../ui";

/** Сума в мінімальних одиницях → рядок із валютою. */
function money(amountMinor: number | null | undefined, currency: string | null): string {
  if (amountMinor === null || amountMinor === undefined || !currency) return "—";
  return `${(amountMinor / 100).toFixed(2)} ${currency}`;
}

export default function PaymentsPage() {
  const { t } = useAdmin();
  const [rows, setRows] = useState<PendingPayment[] | null>(null);
  const [failed, setFailed] = useState("");
  const [answers, setAnswers] = useState<Record<string, SettlementAnswer>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  // Погашені каси не зникли — їх лише прибрано з робочого переліку.
  // Перемикач повертає їх на екран: без нього питання «куди все зникло»
  // лишається без відповіді.
  const [closed, setClosed] = useState(false);
  // Третій стан анонімної воронки: гроші прийшли, кредити зараховані, а
  // сайт покупець ще не назвав. Це не незарахована оплата й не виданий
  // доступ, тож без окремого перемикача його не видно ніде.
  const [unspent, setUnspent] = useState(false);
  const load = useCallback(
    async (withClosed = closed, withUnspent = unspent) => {
      try {
        setRows(await listPendingPayments(withClosed, withUnspent));
        setFailed("");
      } catch {
        setRows([]);
        setFailed(t("common.loadFailed"));
      }
    },
    [closed, unspent, t],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const verify = async (id: string) => {
    setBusy(id);
    setError("");
    setDone("");
    try {
      setAnswers((prior) => ({ ...prior, [id]: { settlement: "unknown" } }));
      const answer = await verifyPendingPayment(id);
      setAnswers((prior) => ({ ...prior, [id]: answer }));
    } catch (problem) {
      setError(
        problem instanceof ApiError ? problem.message : t("common.loadFailed"),
      );
    } finally {
      setBusy(null);
    }
  };

  const verifyAll = async () => {
    setBusy("all");
    setError("");
    setDone("");
    try {
      const all = await verifyAllPendingPayments(closed);
      setAnswers(all);
      const paid = Object.values(all).filter((a) => a.settlement === "paid").length;
      setDone(t("payments.checkedAll", { paid, total: Object.keys(all).length }));
    } catch (problem) {
      setError(
        problem instanceof ApiError ? problem.message : t("common.loadFailed"),
      );
    } finally {
      setBusy(null);
    }
  };

  // Гасіння у два кроки: спершу підрахунок із переліком, потім згода на
  // рівно цей перелік. Число на кнопці тоді не є обіцянкою набору, якого
  // дія не виконає: сервер гасить лише ті з надісланих, що й далі
  // підпадають під правило.
  const [sweep, setSweep] = useState<SweepReport | null>(null);
  const runSweep = async (ids: string[] | null) => {
    setBusy("sweep");
    setError("");
    try {
      const report = await sweepPendingPayments(ids);
      if (ids) {
        setSweep(null);
        setDone(t("payments.swept", { swept: report.swept }));
        await load();
      } else {
        setSweep(report);
        setDone("");
      }
    } catch (problem) {
      setError(
        problem instanceof ApiError ? problem.message : t("common.saveFailed"),
      );
    } finally {
      setBusy(null);
    }
  };

  const credit = async (id: string) => {
    setBusy(id);
    setError("");
    setDone("");
    try {
      const result = await creditPendingPayment(id);
      setDone(
        t("payments.credited", {
          quantity: result.quantity,
          amount: money(result.amount_minor, result.currency),
        }),
      );
      await load();
    } catch (problem) {
      setError(
        problem instanceof ApiError ? problem.message : t("common.saveFailed"),
      );
    } finally {
      setBusy(null);
    }
  };

  // Дії стосуються лише відкритих кас: погашена вже прибрана, і гасити
  // її вдруге нема сенсу.
  const open = (rows ?? []).filter((row) => row.status !== "abandoned");

  if (failed && rows === null) return <Alert tone="danger">{failed}</Alert>;
  if (rows === null) {
    return (
      <div className="flex justify-center py-16 text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-primary">
          {t("payments.title")}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          {/* Дії видно завжди: порожня таблиця — це стан, а не привід
              ховати функціонал (рішення власника 2026-09-06). */}
          <label className="flex items-center gap-2 text-sm text-secondary">
            <input
              type="checkbox"
              className="size-4"
              checked={closed}
              onChange={(e) => {
                setClosed(e.target.checked);
                void load(e.target.checked, unspent);
              }}
            />
            {t("payments.showClosed")}
          </label>
          <label className="flex items-center gap-2 text-sm text-secondary">
            <input
              type="checkbox"
              className="size-4"
              checked={unspent}
              onChange={(e) => {
                setUnspent(e.target.checked);
                void load(closed, e.target.checked);
              }}
            />
            {t("payments.showUnspent")}
          </label>
            <Button
              variant="quiet"
              loading={busy === "all"}
              // Звірка — читання, і на погашених касах вона потрібна саме
              // для того, щоб побачити оплату, яка прийшла після гасіння.
              disabled={rows.length === 0}
              onClick={() => void verifyAll()}
            >
              {t("payments.verifyAll")}
            </Button>
            {sweep === null ? (
              <Button
                variant="quiet"
                loading={busy === "sweep"}
                disabled={open.length === 0}
                onClick={() => void runSweep(null)}
              >
                {t("payments.sweep")}
              </Button>
            ) : (
              <Button
                variant="danger"
                loading={busy === "sweep"}
                disabled={sweep.sweepable === 0}
                onClick={() => void runSweep(sweep.ids)}
              >
                {t("payments.sweepConfirm", { count: sweep.sweepable })}
              </Button>
            )}
        </div>
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {done ? <Alert tone="success">{done}</Alert> : null}

      {/* Нуль без знаменника читається як поломка, тому поруч завжди
          стоять числа, з яких він вийшов. */}
      {sweep ? (
        <Alert tone={sweep.sweepable > 0 ? "warning" : "info"}>
          {t("payments.sweepSummary", {
            total: sweep.pending_total,
            checked: sweep.checked,
            unpaid: sweep.unpaid,
            foreign: sweep.foreign,
            paid: sweep.paid,
            unknown: sweep.unknown,
          })}
        </Alert>
      ) : null}

      <Panel>
        {rows.length === 0 ? (
          <p className="text-sm text-muted">
            {closed ? t("payments.emptyAll") : t("payments.empty")}
          </p>
        ) : (
          <div className={cx(TABLE_SPACING)}>
            <Table>
              <thead>
                <tr>
                  <Th>{t("payments.created")}</Th>
                  <Th>{t("payments.customer")}</Th>
                  <Th>{t("payments.product")}</Th>
                  <Th numeric>{t("payments.quantity")}</Th>
                  <Th numeric>{t("payments.amount")}</Th>
                  <Th>{t("payments.transaction")}</Th>
                  <Th>{t("payments.settlement")}</Th>
                  <Th> </Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const answer = answers[row.purchase_id];
                  const paid = answer?.settlement === "paid";
                  return (
                    <tr key={row.purchase_id}>
                      <Td>
                        <div className="flex flex-col">
                          <span>{row.created_at.slice(0, 16).replace("T", " ")}</span>
                          {row.status === "abandoned" ? (
                            <span className="text-xs text-muted">
                              {t("payments.closed")}
                            </span>
                          ) : null}
                        </div>
                      </Td>
                      <Td>
                        <div className="flex flex-col">
                          <span>{row.email ?? answer?.email ?? t("payments.guest")}</span>
                          <span className="text-xs text-muted">{row.organization}</span>
                        </div>
                      </Td>
                      <Td>
                        <div className="flex flex-col">
                          <span>{row.product ?? t("payments.auditReport")}</span>
                          {row.audit_id ? (
                            <span className="font-mono text-xs text-muted">
                              {row.audit_id.slice(0, 8)}
                            </span>
                          ) : null}
                        </div>
                      </Td>
                      <Td numeric>{row.quantity}</Td>
                      <Td numeric>{money(row.amount_minor, row.currency)}</Td>
                      <Td>
                        <div className="flex flex-col">
                          <span className="font-mono text-xs break-all">
                            {row.transaction_ref}
                          </span>
                          <span className="text-xs text-muted">
                            {row.provider}
                            {row.foreign ? ` · ${t("payments.foreign")}` : ""}
                          </span>
                        </div>
                      </Td>
                      <Td>
                        {answer ? (
                          <div className="flex flex-col gap-1">
                            <StatusPill
                              tone={
                                paid
                                  ? "success"
                                  : answer.settlement === "unpaid"
                                    ? "danger"
                                    : "warning"
                              }
                              label={
                                row.foreign && answer.settlement === "unknown"
                                  ? t("payments.settlement.foreign")
                                  : t(`payments.settlement.${answer.settlement}`)
                              }
                            />
                            {answer.amount_minor !== undefined && answer.amount_minor !== null ? (
                              <span className="text-xs tabular-nums text-muted">
                                {money(answer.amount_minor, answer.currency ?? null)}
                              </span>
                            ) : null}
                            {answer.invoice ? (
                              <span className="font-mono text-xs text-muted">
                                {answer.invoice}
                              </span>
                            ) : null}
                            {answer.detail ? (
                              <span className="text-xs text-muted">{answer.detail}</span>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-sm text-muted">—</span>
                        )}
                      </Td>
                      <Td>
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            variant="ghost"
                            loading={busy === row.purchase_id}
                            onClick={() => void verify(row.purchase_id)}
                          >
                            {t("payments.verify")}
                          </Button>
                          <Button
                            loading={busy === row.purchase_id}
                            disabled={!paid}
                            onClick={() => void credit(row.purchase_id)}
                          >
                            {t("payments.credit")}
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </div>
        )}
      </Panel>
    </div>
  );
}
