"use client";

/**
 * Історія аудитів.
 *
 * ## Один запуск — один рядок
 *
 * Повтори не розділяються. Клієнт замовляв один аудит; те, що ми бралися
 * за нього двічі через таймаут сайту, — наша внутрішня справа, і рядок
 * про це каже позначкою, а не другим записом. Розділити їх означало б
 * показати три аудити там, де списано одну одиницю квоти, і перше ж
 * питання було б про рахунок.
 *
 * ## Історія показує те, що сталося, а не те, що зараз
 *
 * Бал у рядку — той, який був у момент вимірювання. Він не
 * перераховується за новими правилами й не звіряється з чинним станом
 * сайту: історія, яка змінюється заднім числом, перестає бути історією.
 *
 * ## Порожній бал ніколи не стає нулем
 *
 * `null` тут означає три різні речі — не пустили, впало, ще виконується,
 * — і кожна має власний підпис. Нуль сказав би, що вимірювання відбулося
 * і сайт його провалив.
 */

import { useEffect, useState } from "react";

import { PageHeader } from "../../../components/AppShell";
import { Icon } from "../../../components/Icon";
import { NewAuditAction } from "../../../components/NewAudit";
import { Score } from "../../../components/Score";
import {
  Button,
  EmptyState,
  Panel,
  Spinner,
  cx,
} from "../../../components/primitives";
import { listAudits } from "../../../lib/api";
import { useLocale } from "../../../lib/locale";
import { OpenReport, hostOf, statusTone } from "../sites/shared";
import type { AuditSummary } from "../../../lib/contracts";

/** Скільки рядків показуємо за раз. */
const PAGE = 20;

export default function AuditsPage() {
  const { t } = useLocale();
  const [shown, setShown] = useState(PAGE);
  const [audits, setAudits] = useState<AuditSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listAudits()
      .then((rows) => {
        if (!cancelled) setAudits(rows);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <>
        <PageHeader title={t("history.title")} />
        <Panel>
          <p className="text-secondary">{t("state.offline")}</p>
        </Panel>
      </>
    );
  }

  if (audits === null) {
    return (
      <div className="flex min-h-64 items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const visible = audits.slice(0, shown);

  return (
    <>
      <PageHeader title={t("history.title")} action={<NewAuditAction />} />

      {audits.length === 0 ? (
        <Panel padded={false}>
          <EmptyState
            icon="list"
            title={t("history.none")}
            description={t("history.noneWhy")}
          />
        </Panel>
      ) : (
        <>
          <Panel padded={false}>
            <ul>
              {visible.map((audit) => (
                <AuditRow key={audit.id} audit={audit} />
              ))}
            </ul>
          </Panel>

          {shown < audits.length ? (
            <div className="mt-4 flex justify-center">
              <Button variant="quiet" onClick={() => setShown((n) => n + PAGE)}>
                {t("history.more")}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}

function AuditRow({ audit }: { audit: AuditSummary }) {
  const { t, n, d } = useLocale();
  const failed = audit.failure_class !== null;

  return (
    <li className="flex items-center gap-4 border-b border-border px-5 py-4 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-primary">{hostOf(audit.origin)}</p>
        <p className="truncate text-sm text-muted">{audit.url}</p>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className={cx("font-medium", statusTone(audit.status, failed))}>
            {failed ? t(`failure.${audit.failure_class}`) : t(`status.${audit.status}`)}
          </span>
          {audit.locale ? (
            <span className="uppercase text-muted">{audit.locale}</span>
          ) : null}
          <span className="text-muted">
            {d(audit.finished_at ?? audit.created_at)}
          </span>
          {/* Повтори — позначка на тому самому рядку, а не окремі
              записи: це один запуск, за який списано одну одиницю. */}
          {audit.attempts > 1 ? (
            <span className="inline-flex items-center gap-1 text-muted">
              <Icon name="refresh" className="size-3.5" />
              {n("history.attempts", audit.attempts)}
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1.5">
        {audit.score_overall === null ? (
          <span className="text-sm text-muted">
            {audit.status === "queued" || audit.status === "running"
              ? t(`status.${audit.status}`)
              : t("sites.noScore")}
          </span>
        ) : (
          <Score value={audit.score_overall} size="sm" />
        )}
        <OpenReport id={audit.id} label={t("dash.viewAudit")} />
      </div>
    </li>
  );
}
