"use client";

/**
 * Панель огляду.
 *
 * ## Не набір показників, а відповідь на два питання
 *
 * «Як почуваються мої сайти» і «що робити далі». Усе, що не відповідає
 * на одне з них, звідси прибрано: панель, зібрана з красивих чисел,
 * читається один раз із цікавості й більше ніколи.
 *
 * Звідси й порядок: спершу сайти з балом, потім те, що варто робити
 * першим. Квота стоїть у шапці рядком, а не карткою — вона потрібна раз
 * на місяць, а не щодня.
 *
 * ## Нічого не рахує
 *
 * «Що робити першим» — це `next_actions` останнього звіту з балом,
 * порахований бекендом порядок. Сортувати заново на клієнті означало б
 * завести другу копію пріоритезації, і клієнт побачив би два різні
 * «найважливіші».
 *
 * ## Дані живі
 *
 * `GET /v1/sites`, `GET /v1/account`, і один `GET /v1/audits/{id}/result`
 * для панелі пріоритетів. Порожній акаунт показує чесні порожні стани.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "../../components/AppShell";
import { Icon } from "../../components/Icon";
import { Score } from "../../components/Score";
import {
  EmptyState,
  Panel,
  PanelHeader,
  Spinner,
  cx,
} from "../../components/primitives";
import { getAccount, getAuditResult, listSites } from "../../lib/api";
import { useLocale, useT } from "../../lib/locale";
import type { Account, NextAction, Site } from "../../lib/contracts";

export default function DashboardPage() {
  const { t, locale } = useLocale();

  const [sites, setSites] = useState<Site[] | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [attention, setAttention] = useState<{
    host: string;
    auditId: string;
    actions: NextAction[];
  } | null>(null);
  const [attentionSettled, setAttentionSettled] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listSites(), getAccount(locale)])
      .then(([siteRows, accountRow]) => {
        if (cancelled) return;
        setSites(siteRows);
        setAccount(accountRow);

        // Пріоритети — з наймолодшого звіту, який має бал: він і є
        // «останнє, що ми знаємо про ваші сайти».
        const latest = siteRows
          .map((site) => site.latest_audit)
          .filter(
            (audit): audit is NonNullable<typeof audit> =>
              !!audit && audit.score_overall !== null && !!audit.finished_at,
          )
          .sort((a, b) => (a.finished_at! < b.finished_at! ? 1 : -1))[0];
        if (!latest) {
          setAttentionSettled(true);
          return;
        }
        const origin =
          siteRows.find((site) => site.latest_audit?.id === latest.id)?.origin ??
          "";
        getAuditResult(latest.id, locale)
          .then((result) => {
            if (cancelled) return;
            setAttention({
              host: hostOf(origin || result.origin),
              auditId: latest.id,
              actions: result.next_actions.slice(0, 4),
            });
          })
          .catch(() => undefined)
          .finally(() => {
            if (!cancelled) setAttentionSettled(true);
          });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  if (failed) {
    return (
      <>
        <PageHeader title={t("dash.title")} />
        <Panel>
          <p className="text-secondary">{t("state.offline")}</p>
        </Panel>
      </>
    );
  }

  if (sites === null || account === null) {
    return (
      <div className="flex min-h-64 items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  return (
    <>
      <PageHeader title={t("dash.title")} />

      <UsageStrip account={account} />

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.35fr_1fr] lg:items-start">
        <Panel padded={false}>
          <div className="p-5 pb-0">
            <PanelHeader
              title={t("dash.sites")}
              action={
                <Link
                  href="/app/sites"
                  className="text-sm text-accent-text hover:text-primary"
                >
                  {t("action.viewAll")}
                </Link>
              }
            />
          </div>

          {sites.length === 0 ? (
            <EmptyState
              icon="globe"
              title={t("dash.noSites")}
              description={t("dash.noSitesWhy")}
            />
          ) : (
            <ul className="border-t border-border">
              {sites.map((site) => (
                <SiteRow key={site.id} site={site} />
              ))}
            </ul>
          )}
        </Panel>

        <Panel padded={false}>
          <div className="p-5 pb-0">
            <PanelHeader title={t("dash.attention")} />
            {attention ? (
              <p className="mt-1 text-xs text-muted">
                {t("dash.attentionFrom", { host: attention.host })}
              </p>
            ) : null}
          </div>
          {!attentionSettled ? (
            <div className="flex min-h-24 items-center justify-center text-muted">
              <Spinner className="size-4" />
            </div>
          ) : !attention ? (
            <EmptyState icon="clock" title={t("dash.attentionNoData")} />
          ) : attention.actions.length === 0 ? (
            <EmptyState icon="check" title={t("dash.attentionEmpty")} />
          ) : (
            <ul className="mt-3 border-t border-border">
              {attention.actions.map((action) => (
                <AttentionRow
                  key={action.issue_key}
                  auditId={attention.auditId}
                  action={action}
                />
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}

/**
 * Скільки лишилось — одним підписом і двома числами.
 *
 * Дві окремі фрази поруч («Лишились 23 куплені перевірки» і «Перевірки
 * Actual AI Presence: 25») читались як два різні твердження про різні
 * речі, хоча відповідають на одне питання. Підпис тепер один, а
 * одиниця названа при кожному числі: вони списуються окремо, і
 * складати їх не можна.
 *
 * Нуль показується так само, як будь-яке інше значення: «нуль» — це
 * відповідь на питання «скільки лишилось», а порожнє місце — ні.
 * Порожній лишається тільки та половина, якої не існує: при безлімітному
 * тарифі число перевірок не має сенсу, і його каже сусідній блок.
 */
function Remaining({
  checks,
  presence,
}: {
  /** `null` — перевірки безлімітні, число тут було б вигадкою. */
  checks: number | null;
  presence: number;
}) {
  const { t, n } = useLocale();
  return (
    <p className="text-sm text-secondary">
      {t("dash.remaining")}:{" "}
      {checks !== null ? (
        <>
          <span className="tabular-nums text-primary">
            {n("dash.remainingChecks", checks)}
          </span>
          <span className="mx-1.5 text-muted">·</span>
        </>
      ) : null}
      <span className="tabular-nums text-primary">
        {presence} Actual AI Presence
      </span>
    </p>
  );
}

/**
 * Квота рядком, а не карткою.
 *
 * Число «23 з 50» цікавить раз на місяць; смуга під ним каже те саме без
 * читання. Картка на всю ширину під це забирала б перший екран у сайтів,
 * заради яких сюди й заходять.
 */
function UsageStrip({ account }: { account: Account }) {
  const { t, d } = useLocale();
  const { audits_used: used, audits_limit: limit, period_end } = account.usage;
  // Присутність — окрема одиниця обліку: вона витрачається окремо від
  // перевірок і в пакеті йде своєю кількістю (рішення власника
  // 2026-09-06). На «Тарифі» цей рядок був завжди; на «Огляді» його не
  // було, і кількість доводилось шукати іншою сторінкою.
  const presenceLeft =
    (account.usage.presence_remaining ?? 0) + account.usage.presence_credits_available;
  // Стан без підписки — чесний: «активного тарифу немає» плюс реальні
  // куплені перевірки, і жодної смуги «0 з 0» чи вигаданого «1 of 1».
  // Безкоштовні превʼю сюди не рахуються — вони необмежені й живуть
  // своїм шляхом.
  const free =
    account.billing_state === "free" || account.billing_state === "cancelled";
  const share = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  if (free) {
    return (
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-border bg-surface px-5 py-4">
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wide text-muted">
            {t("plan.row.plan")}
          </p>
          <p className="mt-0.5 text-sm text-primary">{t("plan.none")}</p>
        </div>
        <Remaining
          checks={account.usage.one_off_available}
          presence={presenceLeft}
        />
        <Link
          href="/app/plan"
          className="text-sm text-accent-text hover:text-primary"
        >
          {t("nav.plan")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-border bg-surface px-5 py-4">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-muted">{t("dash.usage")}</p>
        <p className="mt-0.5 text-sm text-primary">
          {limit === null
            ? t("dash.usageUnlimited", { used })
            : t("dash.usageLeft", { left: limit - used, limit })}
        </p>
      </div>

      {limit !== null ? (
        <div className="min-w-32 flex-1">
          <span className="block h-1 overflow-hidden rounded-full bg-surface-sunken">
            <span
              className="block h-full rounded-full bg-brand"
              style={{ inlineSize: `${share}%` }}
            />
          </span>
        </div>
      ) : null}

      <Remaining checks={null} presence={presenceLeft} />

      {account.usage.renews_at ? (
        <p className="text-xs text-muted">
          {t("dash.renews", { date: d(period_end) })}
        </p>
      ) : null}
      <Link
        href="/app/plan"
        className="text-sm text-accent-text hover:text-primary"
      >
        {account.plan.name}
      </Link>
    </div>
  );
}

/**
 * Один сайт: бал, стан, коли міряли.
 *
 * Стани трапляються всі й у перший же тиждень: сайт із балом, сайт із
 * невдалим аудитом і сайт, який ще не міряли. Рядок, намальований лише
 * під перший, у двох випадках із трьох показує порожнечу або, гірше,
 * нуль.
 */
function SiteRow({ site }: { site: Site }) {
  const { t, d, n } = useLocale();
  const latest = site.latest_audit;
  const scored = latest?.score_overall ?? null;
  const failed = (latest?.failure_class ?? null) !== null;

  return (
    <li>
      <Link
        href={`/app/sites/${site.id}`}
        className="flex items-center gap-4 border-b border-border px-5 py-4 transition-colors duration-fast last:border-b-0 hover:bg-surface-sunken"
      >
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-primary">{site.display_name}</p>
          <p className="truncate text-sm text-muted">{hostOf(site.origin)}</p>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            {latest ? (
              <StatusChip status={latest.status} failed={failed} />
            ) : (
              <span className="text-muted">{t("dash.neverAudited")}</span>
            )}
            {latest?.finished_at ? (
              <span className="text-muted">{relative(latest.finished_at, t, n, d)}</span>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          {/* Порожній бал уже показується тире самим компонентом —
              другий підпис поруч давав два тире підряд. */}
          <Score value={scored} size="sm" />
        </div>

        <Icon name="chevron-right" className="size-4 shrink-0 text-muted" />
      </Link>
    </li>
  );
}

/**
 * Одна дія з переліку «що робити першим» — рядок `next_actions` звіту.
 *
 * Причина стоїть поруч із дією, а не за розкриттям: у переліку
 * пріоритетів людина вирішує, чи братися, і вирішує вона саме за
 * поясненням, а не за технічною назвою.
 */
function AttentionRow({
  auditId,
  action,
}: {
  auditId: string;
  action: NextAction;
}) {
  const { t, n } = useLocale();
  return (
    <li>
      <Link
        href={`/app/audits/${auditId}#${action.issue_key}`}
        className="block border-b border-border px-5 py-4 transition-colors duration-fast last:border-b-0 hover:bg-surface-sunken"
      >
        <div className="flex items-center gap-2">
          <span className="truncate text-xs text-muted">
            {t(`module.${action.module}`)}
          </span>
          <span className="ms-auto shrink-0 text-xs tabular-nums text-accent-text">
            {action.expected_gain}
          </span>
        </div>

        <p className="mt-1.5 font-medium text-primary">{action.action}</p>
        <p className="mt-1 text-sm text-secondary">{action.why}</p>
        {action.affected_pages > 0 ? (
          <p className="mt-2 text-xs text-muted">
            {n("dash.affected", action.affected_pages)}
          </p>
        ) : null}
      </Link>
    </li>
  );
}

function StatusChip({ status, failed }: { status: string; failed: boolean }) {
  const t = useT();
  const tone = failed
    ? "text-danger"
    : status === "partial"
      ? "text-warning"
      : status === "completed"
        ? "text-success"
        : "text-muted";
  return <span className={cx("font-medium", tone)}>{t(`status.${status}`)}</span>;
}

// ── дрібне форматування ────────────────────────────────────────────────────

function hostOf(origin: string): string {
  try {
    return new URL(origin).host;
  } catch {
    return origin;
  }
}

/**
 * «2 дні тому» замість дати.
 *
 * Для свіжого аудиту людина думає проміжками, а не датами: «позавчора»
 * зрозуміліше за «21 серп.» рівно доти, доки проміжок малий. Далі —
 * навпаки, і тому після тижня показується дата.
 */
function relative(
  iso: string,
  t: (key: string) => string,
  n: (key: string, count: number) => string,
  d: (iso: string) => string,
): string {
  const days = Math.round((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return t("dash.today");
  if (days < 7) return n("dash.ago", days);
  return d(iso);
}
