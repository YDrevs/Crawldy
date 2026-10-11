/**
 * Бал і його смуга — продуктовий елемент, а не прикраса.
 *
 * Три правила, які тримають його аналітичним:
 *
 * 1. **`null` — не нуль.** Порожній бал означає, що покрито замало
 *    напрямів, щоб число щось означало. Намалювати нуль — вигадати
 *    вимірювання, якого не було.
 * 2. **Різниця в один-три бали не подія.** Шкала гіперболічна, і на
 *    середині сайту такий рух дає одна дрібна знахідка. Дельта нижче
 *    порога показується сірим і без стрілки.
 * 3. **Ніяких кілець, що заповнюються, і кольорових градієнтів.** Це
 *    звіт для того, хто ухвалює рішення, а не результат гри.
 */

import { cx } from "../lib/cx";
import { Icon } from "./Icon";
import type { Band } from "../lib/contracts";

export type { Band };

/**
 * Смуга з голого числа — і єдина причина, чому вона тут рахується.
 *
 * `AuditResult` і `ModuleScore` несуть `band` з API, і на екрані звіту
 * ця функція не викликається жодного разу. Але `AuditSummary` несе лише
 * `score_overall`, а панелі огляду потрібен колір — тож межі поки
 * продубльовані з `scoring.BANDS`.
 *
 * Дублювання свідоме й тимчасове: правильне місце для смуги — контракт.
 * Поки скоринг заморожений, розходження неможливе; щойно `band`
 * зʼявиться в `AuditSummary`, ця функція зникає.
 */
export function bandOf(score: number | null | undefined): Band {
  if (score === null || score === undefined) return "unknown";
  if (score < 40) return "critical";
  if (score < 60) return "poor";
  if (score < 80) return "medium";
  return "good";
}

/* Смуга оцінки має власні кольори, не позичені в серйозності: це різні
 * шкали, і збіг у них випадковий. Середня смуга нейтральна — 62 бали не
 * попередження, а «посередньо». */
const BAND_TEXT: Record<Band, string> = {
  critical: "text-band-critical",
  poor: "text-band-poor",
  medium: "text-band-medium",
  good: "text-band-good",
  unknown: "text-band-unknown",
};

const BAND_BAR: Record<Band, string> = {
  critical: "bg-band-critical",
  poor: "bg-band-poor",
  medium: "bg-band-medium",
  good: "bg-band-good",
  unknown: "bg-band-unknown",
};

/**
 * Рух менший за це — шум шкали, а не поліпшення сайту. Показуємо число,
 * але не малюємо його як подію.
 */
export const MEANINGFUL_DELTA = 4;

export function Score({
  value,
  size = "md",
  bandLabel,
  emptyLabel,
}: {
  value: number | null;
  size?: "sm" | "md" | "lg";
  bandLabel?: string;
  emptyLabel?: string;
}) {
  const band = bandOf(value);
  const digits = {
    sm: "text-lg",
    md: "text-2xl",
    lg: "text-4xl",
  }[size];

  if (value === null) {
    return (
      <span className="inline-flex items-baseline gap-2">
        <span className={cx(digits, "font-semibold text-muted")}>—</span>
        {emptyLabel ? <span className="text-xs text-muted">{emptyLabel}</span> : null}
      </span>
    );
  }

  return (
    <span className="inline-flex items-baseline gap-2">
      <span className={cx(digits, "font-semibold tabular-nums tracking-tight", BAND_TEXT[band])}>
        {value}
      </span>
      {/* На вузькому екрані підпис смуги («Посередньо») бере 14px: він
          стоїть поруч із балом як пояснення, а не як службова позначка. */}
      {bandLabel ? (
        <span className="text-sm text-secondary sm:text-xs">{bandLabel}</span>
      ) : null}
    </span>
  );
}

/** Горизонтальна смуга під бал напряму. Читається швидше за число в ряду. */
export function ScoreBar({ value }: { value: number | null }) {
  const band = bandOf(value);
  return (
    <span className="block h-1 w-full overflow-hidden rounded-full bg-surface-sunken">
      <span
        className={cx("block h-full rounded-full transition-all", BAND_BAR[band])}
        style={{ inlineSize: `${value ?? 0}%` }}
      />
    </span>
  );
}

/**
 * Зміна бала між аудитами.
 *
 * `comparable = false` означає, що між аудитами змінилися наші правила, і
 * різницю не можна приписати сайту. Показати її стрілкою було б
 * неправдою: клієнт побачив би поліпшення там, де ми просто інакше
 * порахували.
 */
export function ScoreDelta({
  delta,
  comparable = true,
  incomparableLabel,
}: {
  delta: number | null;
  comparable?: boolean;
  incomparableLabel?: string;
}) {
  if (delta === null) return null;

  if (!comparable) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted">
        <Icon name="info" className="size-3.5" />
        {incomparableLabel ?? `${delta > 0 ? "+" : ""}${delta}`}
      </span>
    );
  }

  const meaningful = Math.abs(delta) >= MEANINGFUL_DELTA;
  if (!meaningful) {
    return (
      <span className="text-xs tabular-nums text-muted">
        {delta > 0 ? "+" : ""}
        {delta}
      </span>
    );
  }

  const up = delta > 0;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
        up ? "text-delta-up" : "text-delta-down",
      )}
    >
      <Icon name={up ? "arrow-up" : "arrow-down"} className="size-3.5" />
      {up ? "+" : ""}
      {delta}
    </span>
  );
}
