"use client";

/**
 * Спільні шматки сайтів, історії й розкладів.
 *
 * ## Стан вимірювання не можна звести до бала
 *
 * `score_overall === null` означає щонайменше три різні речі: аудит
 * упав, сайт не пустив краулер, або аудит ще виконується. Намалювати в
 * усіх трьох випадках тире означало б сказати «нічого не відомо» там, де
 * відомо багато. Тому стан збирається з трьох полів разом — статусу,
 * бала й класу невдачі, — і кожне поєднання має власний підпис.
 *
 * Нуль замість порожнечі не малюється ніде. Це найдешевша неправда, яку
 * може сказати інтерфейс: клієнт бачить «0» і думає, що його сайт
 * провалив вимірювання, тоді як вимірювання не відбулося.
 */

import Link from "next/link";

import { Icon } from "../../../components/Icon";
import { Score } from "../../../components/Score";
import { cx } from "../../../components/primitives";
import { useLocale } from "../../../lib/locale";
import type { AuditStatus, FailureClass, LatestAudit } from "../../../lib/contracts";

export function hostOf(origin: string): string {
  try {
    return new URL(origin).host;
  } catch {
    return origin;
  }
}

/** Тон статусу аудиту. Проблема має виглядати проблемою, а не рядком тексту. */
export function statusTone(status: AuditStatus, failed: boolean): string {
  if (failed || status === "failed") return "text-danger";
  if (status === "partial") return "text-warning";
  if (status === "completed") return "text-success";
  return "text-muted";
}

/**
 * Бал сайту в переліку — або пояснення, чому його немає.
 *
 * Три різні «немає бала» розводяться явно: не пустили, впало, ще йде.
 */
export function LatestScore({ latest }: { latest: LatestAudit | null | undefined }) {
  const { t } = useLocale();

  if (!latest) {
    return <span className="text-sm text-muted">{t("sites.neverAudited")}</span>;
  }
  if (latest.score_overall === null) {
    return (
      <span className="text-sm text-muted">
        {latest.status === "queued" || latest.status === "running"
          ? t(`status.${latest.status}`)
          : t("sites.noScore")}
      </span>
    );
  }
  return (
    <div className="flex flex-col items-end gap-0.5">
      <Score value={latest.score_overall} size="sm" />
      {latest.status === "partial" ? (
        <span className="text-2xs text-warning">{t("sites.partial")}</span>
      ) : null}
    </div>
  );
}

/** Підпис стану останнього аудиту: статус плюс причина, якщо вона є. */
export function LatestState({ latest }: { latest: LatestAudit | null | undefined }) {
  const { t } = useLocale();
  if (!latest) return null;
  const failed = latest.failure_class !== null;
  return (
    <span className={cx("text-xs font-medium", statusTone(latest.status, failed))}>
      {failed ? t(`failure.${latest.failure_class}`) : t(`status.${latest.status}`)}
    </span>
  );
}

/** Посилання «відкрити звіт» — той самий вигляд у переліку й на сайті. */
export function OpenReport({ id, label }: { id: string; label: string }) {
  return (
    <Link
      href={`/app/audits/${id}`}
      className="inline-flex items-center gap-1.5 text-sm text-accent-text hover:text-primary"
    >
      {label}
      <Icon name="arrow-right" className="size-4" />
    </Link>
  );
}

export type { FailureClass };
