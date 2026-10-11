"use client";

/**
 * Сторінка сайту.
 *
 * ## Не звіт і не другий екран результату
 *
 * Тут — сам сайт: хто він, як почувається зараз, коли міряли і що було
 * раніше. Повний результат живе на `/app/audits/{id}`, і дублювати його
 * сюди означало б мати два місця, які розходяться на першій же зміні
 * звіту.
 *
 * ## Історія тут та сама, що на спільному екрані
 *
 * Ті самі рядки, той самий контракт, лише відфільтровані за сайтом.
 * Окремий вигляд «історія сайту» був би третім місцем, де порожній бал
 * знову треба не перетворити на нуль.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "../../../../components/AppShell";
import { Icon } from "../../../../components/Icon";
import { NewAuditAction } from "../../../../components/NewAudit";
import { Score } from "../../../../components/Score";
import {
  EmptyState,
  Panel,
  PanelHeader,
  Spinner,
  cx,
} from "../../../../components/primitives";
import { getSite, listAudits } from "../../../../lib/api";
import { useLocale } from "../../../../lib/locale";
import { LatestState, OpenReport, hostOf, statusTone } from "../shared";
import type { AuditSummary, Site } from "../../../../lib/contracts";

export default function SiteDetailPage() {
  const params = useParams<{ id: string }>();
  const { t, d } = useLocale();

  const [site, setSite] = useState<Site | null>(null);
  const [history, setHistory] = useState<AuditSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSite(params.id), listAudits()])
      .then(([row, audits]) => {
        if (cancelled) return;
        setSite(row);
        setHistory(audits.filter((audit) => audit.site_id === row.id));
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  if (failed) {
    return (
      <>
        <PageHeader
          title={t("sites.title")}
          breadcrumb={{ href: "/app/sites", label: t("sites.title") }}
        />
        <Panel>
          <p className="text-secondary">{t("state.error")}</p>
        </Panel>
      </>
    );
  }

  if (site === null || history === null) {
    return (
      <div className="flex min-h-64 items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={site.display_name}
        breadcrumb={{ href: "/app/sites", label: t("sites.title") }}
        description={t("sites.addedOn", { date: d(site.created_at) })}
        action={<NewAuditAction initialUrl={site.origin} />}
      />

      <Latest site={site} />

      <section className="mt-6">
        <Panel padded={false}>
          <div className="p-5 pb-0">
            <PanelHeader title={t("sites.history")} />
          </div>
          {history.length === 0 ? (
            <EmptyState icon="list" title={t("history.none")} description={t("history.noneWhy")} />
          ) : (
            <ul className="mt-4 border-t border-border">
              {history.map((audit) => (
                <HistoryRow key={audit.id} audit={audit} />
              ))}
            </ul>
          )}
        </Panel>
      </section>
    </>
  );
}

/** Останній вимір: бал, стан і шлях до повного звіту. */
function Latest({ site }: { site: Site }) {
  const { t, d } = useLocale();
  const latest = site.latest_audit;

  return (
    <Panel>
      <PanelHeader title={t("sites.lastAudit")} />

      {/* `break-all`: у домені немає пробілів, і на телефоні його нема
          де перенести — довга адреса інакше виштовхує сторінку вбік. */}
      <p className="mt-1 break-all text-sm text-muted">{hostOf(site.origin)}</p>

      {!latest ? (
        <p className="mt-4 text-secondary">{t("sites.neverAudited")}</p>
      ) : (
        <>
          <div className="mt-4 flex items-center gap-4">
            {latest.score_overall === null ? (
              <span className="text-secondary">{t("sites.noScore")}</span>
            ) : (
              <Score value={latest.score_overall} size="lg" />
            )}
            <div className="flex flex-col gap-1">
              <LatestState latest={latest} />
              {latest.finished_at ? (
                <span className="text-xs text-muted">{d(latest.finished_at)}</span>
              ) : null}
            </div>
          </div>
          <div className="mt-4">
            <OpenReport id={latest.id} label={t("sites.openLatest")} />
          </div>
        </>
      )}
    </Panel>
  );
}

function HistoryRow({ audit }: { audit: AuditSummary }) {
  const { t, n, d } = useLocale();
  const failed = audit.failure_class !== null;

  return (
    <li className="flex items-center gap-4 border-b border-border px-5 py-3.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className={cx("font-medium", statusTone(audit.status, failed))}>
            {failed ? t(`failure.${audit.failure_class}`) : t(`status.${audit.status}`)}
          </span>
          <span className="text-muted">{d(audit.finished_at ?? audit.created_at)}</span>
          {audit.attempts > 1 ? (
            <span className="inline-flex items-center gap-1 text-muted">
              <Icon name="refresh" className="size-3.5" />
              {n("history.attempts", audit.attempts)}
            </span>
          ) : null}
        </div>
      </div>

      <div className="shrink-0">
        {audit.score_overall === null ? (
          <span className="text-sm text-muted">{t("sites.noScore")}</span>
        ) : (
          <Score value={audit.score_overall} size="sm" />
        )}
      </div>

      <Link
        href={`/app/audits/${audit.id}`}
        aria-label={t("dash.viewAudit")}
        className="shrink-0 text-muted hover:text-primary"
      >
        <Icon name="chevron-right" className="size-4" />
      </Link>
    </li>
  );
}
