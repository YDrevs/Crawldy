"use client";

/**
 * Результат аудиту в кабінеті.
 *
 * Сторінка — лише доступ і обгортка: заголовок із хлібними крихтами,
 * кнопки завантаження кабінету й завантаження даних. Саме подання
 * звіту живе в `AuditResultView` і **спільне з оплаченим гостьовим
 * переглядом**: доступ у них різний, звіт — один, і два екрани з часом
 * розійшлися б у різні продукти.
 *
 * Живий шлях: `GET /v1/audits/{id}` каже стан, `GET /v1/audits/{id}/result`
 * віддає звіт, коли він є. Аудит, що ще виконується, сторінка дочікує
 * сама — опитуванням раз на пʼять секунд, як гостьовий екран.
 */

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "../../../../components/AppShell";
import {
  AuditResultView,
  fullDate,
  hostOf,
} from "../../../../components/AuditResultView";
import { Icon } from "../../../../components/Icon";
import { Panel, Spinner, cx } from "../../../../components/primitives";
import { API_URL, getAudit, getAuditResult } from "../../../../lib/api";
import { useLocale } from "../../../../lib/locale";
import type { AuditResult, AuditSummary } from "../../../../lib/contracts";

const POLL_MS = 5_000;

export default function AuditResultPage() {
  const params = useParams<{ id: string }>();
  const { t, locale } = useLocale();

  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [result, setResult] = useState<AuditResult | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const row = await getAudit(params.id, locale);
        if (cancelled) return;
        setSummary(row);
        if (row.status === "completed" || row.status === "partial") {
          const view = await getAuditResult(params.id, locale);
          if (!cancelled) setResult(view);
          return;
        }
        if (row.status === "queued" || row.status === "running") {
          timer = setTimeout(() => void poll(), POLL_MS);
        }
        // failed / skipped: підсумок уже каже все, що ми знаємо.
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    void poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [params.id, locale]);

  if (failed) {
    return (
      <>
        <PageHeader
          title={t("history.title")}
          breadcrumb={{ href: "/app/audits", label: t("history.title") }}
        />
        <Panel>
          <p className="text-secondary">{t("state.error")}</p>
        </Panel>
      </>
    );
  }

  if (summary === null) {
    return (
      <div className="flex min-h-64 items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  if (summary.status === "queued" || summary.status === "running") {
    return (
      <>
        <PageHeader
          title={hostOf(summary.origin)}
          breadcrumb={{ href: "/app/audits", label: t("history.title") }}
        />
        <Panel>
          <div className="flex items-center gap-3">
            <Spinner className="size-4" />
            <div>
              <p className="font-medium text-primary">{t("free.auditRunningTitle")}</p>
              <p className="mt-0.5 text-sm text-secondary">
                {t("free.auditRunningLead")}
              </p>
            </div>
          </div>
        </Panel>
      </>
    );
  }

  if (result === null) {
    // Термінальний стан без звіту: не пустили, впало, пропущено.
    const failedRun = summary.failure_class !== null;
    return (
      <>
        <PageHeader
          title={hostOf(summary.origin)}
          breadcrumb={{ href: "/app/audits", label: t("history.title") }}
        />
        <Panel>
          {/* Сирого `summary.error` тут немає навмисно: це діагностика
              двигуна зі службовими кодами й українськими рядками
              незалежно від мови кабінету. Локалізований клас невдачі —
              усе, що тут правда для людини. */}
          <p className="font-medium text-danger">
            {failedRun
              ? t(`failure.${summary.failure_class}`)
              : t(`status.${summary.status}`)}
          </p>
        </Panel>
      </>
    );
  }

  const site = result.site_id;
  return (
    <>
      <PageHeader
        title={hostOf(result.origin)}
        breadcrumb={
          site
            ? { href: `/app/sites/${site}`, label: hostOf(result.origin) }
            : { href: "/app/audits", label: t("history.title") }
        }
        description={
          result.finished_at
            ? t("result.finished", { date: fullDate(locale, result.finished_at) })
            : undefined
        }
        action={<Downloads id={result.audit_id} />}
      />
      <AuditResultView result={result} />
    </>
  );
}

/**
 * Звіт файлом — маршрутом кабінету.
 *
 * Лишається тут, а не в спільному поданні, бо адреса залежить від
 * способу доступу: кабінет тягне `/v1/audits/{id}/report` під сесією,
 * оплачений гість — своє постійне посилання `/r/{token}`. Це справжні
 * посилання на справжній ендпойнт, а не заглушки. Мова в адресі — мова
 * інтерфейсу: документ складається на бекенді.
 */
function Downloads({ id }: { id: string }) {
  const { t, locale } = useLocale();
  return (
    <div className="flex items-center gap-2">
      {[
        { format: "docx-general", label: t("result.downloadGeneral") },
        { format: "docx-technical", label: t("result.downloadTechnical") },
        { format: "json", label: t("result.downloadJson") },
      ].map((item) => (
        <a
          key={item.format}
          href={`${API_URL}/v1/audits/${id}/report?format=${item.format}&lang=${locale}`}
          className={cx(
            "inline-flex h-9 items-center gap-2 rounded-md border border-border px-3",
            "text-sm text-secondary transition-colors duration-fast",
            "hover:bg-surface-sunken hover:text-primary",
          )}
        >
          <Icon name="download" className="size-4" />
          {item.label}
        </a>
      ))}
    </div>
  );
}
