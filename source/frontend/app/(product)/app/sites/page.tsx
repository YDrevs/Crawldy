"use client";

/**
 * Перелік сайтів.
 *
 * Не таблиця з колонками, а перелік рядків: у сайту три факти, і
 * частина з них порожня в половині випадків. Таблиця під це вимагала б
 * колонок, у яких частіше стоїть тире, ніж значення, — і кожне тире
 * читалося б як «дані загубились».
 *
 * Порядок фактів у рядку відповідає порядку питань: що це за сайт → як
 * він почувається → коли міряли.
 *
 * Усе, що тут показано, приходить із `GET /v1/sites` одним запитом
 * разом із сайтом. Зібрати останній аудит на клієнті означало б
 * відтворити правило «який із них останній» — за створенням, а не за
 * завершенням: запуск, що триває, і є той, про який хочуть знати.
 *
 * ## Це місце, де керують переліком сайтів
 *
 * Тут і тільки тут сайт додається окремою дією, і тут у кожного сайту
 * дві власні дії — повна перевірка й Actual AI Presence. Одна спільна
 * «нова перевірка» на весь екран не годиться: вона не каже, ЩО саме
 * запускає, а витрачає різні одиниці обліку.
 *
 * Присутність звідси не стартує одразу: кнопка веде у форму запуску з
 * підставленою адресою, бо для прогону потрібні бренд і категорія, і
 * вигадати їх за клієнта ми не можемо.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "../../../components/AppShell";
import { AddSiteAction } from "../../../components/AddSite";
import { Icon } from "../../../components/Icon";
import { Button, EmptyState, Panel, Spinner } from "../../../components/primitives";
import { ApiError, createAudit, listSites } from "../../../lib/api";
import { useLocale } from "../../../lib/locale";
import { LatestScore, LatestState, hostOf } from "./shared";
import type { Site } from "../../../lib/contracts";

export default function SitesPage() {
  const { t } = useLocale();
  const [sites, setSites] = useState<Site[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listSites()
      .then((rows) => {
        if (!cancelled) setSites(rows);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const added = (site: Site) =>
    setSites((rows) => (rows === null ? [site] : [site, ...rows]));

  return (
    <>
      <PageHeader
        title={t("sites.title")}
        action={<AddSiteAction onAdded={added} />}
      />

      {failed ? (
        <Panel>
          <p className="text-secondary">{t("state.offline")}</p>
        </Panel>
      ) : sites === null ? (
        <div className="flex min-h-64 items-center justify-center text-muted">
          <Spinner className="size-5" />
        </div>
      ) : sites.length === 0 ? (
        <Panel padded={false}>
          <EmptyState
            icon="globe"
            title={t("sites.none")}
            description={t("sites.noneWhy")}
          />
        </Panel>
      ) : (
        <Panel padded={false}>
          <ul>
            {sites.map((site) => (
              <SiteRow key={site.id} site={site} />
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}

function SiteRow({ site }: { site: Site }) {
  const { d } = useLocale();
  const latest = site.latest_audit;

  return (
    <li className="border-b border-border last:border-b-0">
      <div className="flex flex-wrap items-center gap-4 px-5 py-4">
        <Link
          href={`/app/sites/${site.id}`}
          className="-my-2 flex min-w-0 flex-1 items-center gap-4 rounded-md py-2 transition-colors duration-fast hover:bg-surface-sunken"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-primary">{site.display_name}</p>
            {/* `truncate` на домені: адреси бувають довші за телефон, і
                переносити їх нема де — у них немає пробілів. */}
            <p className="truncate text-sm text-muted">{hostOf(site.origin)}</p>

            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <LatestState latest={latest} />
              {latest?.finished_at ? (
                <span className="text-muted">{d(latest.finished_at)}</span>
              ) : null}
            </div>
          </div>

          <div className="shrink-0">
            <LatestScore latest={latest} />
          </div>

          <Icon name="chevron-right" className="size-4 shrink-0 text-muted" />
        </Link>

        <SiteActions site={site} />
      </div>
    </li>
  );
}

/**
 * Дві дії сайту, і кожна названа тим, що робить.
 *
 * Повна перевірка стартує одразу — у неї є все, що треба, адреса. У
 * присутності немає бренда й категорії, тож вона веде у форму запуску:
 * запустити її «одним кліком» означало б вигадати обовʼязкові поля.
 */
function SiteActions({ site }: { site: Site }) {
  const { t } = useLocale();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runFull() {
    setBusy(true);
    setError(null);
    try {
      const started = await createAudit({ urls: [site.origin] });
      router.push(`/app/audits/${started.id}`);
    } catch (problem) {
      setError(
        problem instanceof ApiError && problem.status === 402
          ? t("newAudit.noQuota")
          : t("newAudit.failed"),
      );
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="quiet" disabled={busy} onClick={() => void runFull()}>
          {t("sites.runFull")}
        </Button>
        <Button
          size="sm"
          variant="quiet"
          onClick={() => router.push(`/app/presence?site=${site.id}`)}
        >
          {t("sites.runPresence")}
        </Button>
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
