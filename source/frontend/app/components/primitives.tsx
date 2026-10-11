"use client";

/**
 * Примітиви інтерфейсу Crawldy.
 *
 * Один набір на весь продукт: кабінет, публічні сторінки й адмінка беруть
 * ті самі елементи. Окремий візуальний стиль на кожну сторінку — це
 * найшвидший спосіб перетворити продукт на набір сторінок.
 *
 * Правила, спільні для всього файлу:
 *
 * - колір називається роллю (`bg-surface`), ніколи відтінком;
 * - розміри зі шкали токенів, ніколи «на око»;
 * - логічні властивості (`ms-`, `pe-`, `text-start`) замість лівого й
 *   правого: арабська прийде пізніше, а переписувати сотні класів потім
 *   означає переписувати все;
 * - жодного тексту для клієнта — усе приходить пропсами.
 */

import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useEffect, useId, useRef, useState } from "react";

import { Icon, type IconName } from "./Icon";
import { cx } from "../lib/cx";

export { cx };


// ── поверхні ───────────────────────────────────────────────────────────────

/**
 * Панель — базова поверхня. Межа й відступ, майже без тіні: глибина тут
 * створюється простором, а не розмиттям.
 */
export function Panel({
  children,
  className,
  padded = true,
  ...props
}: HTMLAttributes<HTMLDivElement> & { padded?: boolean }) {
  return (
    <div
      {...props}
      className={cx(
        "rounded-lg border border-border bg-surface shadow-card",
        padded && "p-5",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold tracking-tight text-primary">{title}</h2>
        {description ? (
          <p className="mt-1 max-w-measure text-sm text-secondary">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

// ── кнопки ─────────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "accent" | "quiet" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand text-brand-ink hover:bg-brand-hover",
  accent: "bg-accent text-accent-ink hover:bg-accent-hover",
  quiet: "border border-border bg-surface text-primary hover:border-border-strong",
  ghost: "text-secondary hover:bg-surface-sunken hover:text-primary",
  danger: "border border-danger text-danger hover:bg-surface-sunken",
};

const BUTTON_SIZE: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-xs",
  md: "h-10 gap-2 px-4 text-sm",
  lg: "h-12 gap-2 px-6 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  iconEnd,
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  iconEnd?: IconName;
  loading?: boolean;
}) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center rounded-md font-medium",
        "transition-colors duration-fast",
        "disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANT[variant],
        BUTTON_SIZE[size],
        className,
      )}
    >
      {loading ? <Spinner /> : icon ? <Icon name={icon} /> : null}
      {children}
      {iconEnd ? <Icon name={iconEnd} /> : null}
    </button>
  );
}

/** Кнопка, у якої підпис — сама іконка. Назва обовʼязкова. */
export function IconButton({
  icon,
  label,
  variant = "ghost",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: IconName;
  label: string;
  variant?: ButtonVariant;
}) {
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={cx(
        "inline-flex size-9 items-center justify-center rounded-md",
        "transition-colors duration-fast disabled:opacity-50",
        BUTTON_VARIANT[variant],
        className,
      )}
    >
      <Icon name={icon} />
    </button>
  );
}

// ── поля вводу ─────────────────────────────────────────────────────────────

/* Межа поля вводу — `border-control`, а не декоративна `border`.
 * WCAG 1.4.11 вимагає для неї 3:1: поле, межу якого не видно, для
 * частини людей просто не існує. */
const CONTROL =
  "w-full rounded-md border border-control bg-surface px-3 text-base text-primary " +
  "placeholder:text-muted transition-colors duration-fast " +
  "focus:border-accent-text focus:outline-none disabled:opacity-60";

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-secondary">
        {label}
      </label>
      {children}
      {error ? (
        <span className="text-xs text-danger">{error}</span>
      ) : hint ? (
        <span className="text-xs text-muted">{hint}</span>
      ) : null}
    </div>
  );
}

export function Input({
  label,
  hint,
  error,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}) {
  const id = useId();
  const control = (
    <input
      {...props}
      id={props.id ?? id}
      aria-invalid={error ? true : undefined}
      className={cx(CONTROL, "h-10", error && "border-danger", className)}
    />
  );
  if (!label) return control;
  return (
    <Field label={label} hint={hint} error={error} htmlFor={props.id ?? id}>
      {control}
    </Field>
  );
}

export function Select({
  label,
  hint,
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: ReactNode; hint?: ReactNode }) {
  const id = useId();
  const control = (
    <div className="relative">
      <select
        {...props}
        id={props.id ?? id}
        className={cx(CONTROL, "h-10 appearance-none pe-9", className)}
      >
        {children}
      </select>
      <Icon
        name="chevron-down"
        className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted"
      />
    </div>
  );
  if (!label) return control;
  return (
    <Field label={label} hint={hint} htmlFor={props.id ?? id}>
      {control}
    </Field>
  );
}

export function Textarea({
  label,
  hint,
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: ReactNode; hint?: ReactNode }) {
  const id = useId();
  const control = (
    <textarea {...props} id={props.id ?? id} className={cx(CONTROL, "py-2", className)} />
  );
  if (!label) return control;
  return (
    <Field label={label} hint={hint} htmlFor={props.id ?? id}>
      {control}
    </Field>
  );
}

export function SearchInput({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <Icon
        name="search"
        className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted"
      />
      <input {...props} type="search" className={cx(CONTROL, "h-10 ps-9", className)} />
    </div>
  );
}

// ── бейджі та стани ────────────────────────────────────────────────────────

type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const TONE: Record<Tone, string> = {
  neutral: "border-border bg-surface-sunken text-secondary",
  accent: "border-accent bg-accent-soft text-accent-ink",
  success: "border-success/40 text-success",
  warning: "border-warning/40 text-warning",
  danger: "border-danger/40 text-danger",
  info: "border-info/40 text-info",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
        "text-xs font-medium",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * Смужка серйозності. Колір — із токенів серйозності, не з акценту:
 * серйозність це дані, а фарбувати дані брендом означає зробити бренд
 * нечитаним.
 */
export type SeverityName = "critical" | "high" | "medium" | "low" | "info";

const SEVERITY_TEXT: Record<SeverityName, string> = {
  critical: "text-severity-critical",
  high: "text-severity-high",
  medium: "text-severity-medium",
  low: "text-severity-low",
  info: "text-severity-info",
};

const SEVERITY_BG: Record<SeverityName, string> = {
  critical: "bg-severity-critical",
  high: "bg-severity-high",
  medium: "bg-severity-medium",
  low: "bg-severity-low",
  info: "bg-severity-info",
};

export function SeverityBadge({
  severity,
  label,
}: {
  severity: SeverityName;
  label: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 text-xs font-medium",
        SEVERITY_TEXT[severity],
      )}
    >
      <span className={cx("size-1.5 rounded-full", SEVERITY_BG[severity])} />
      {label}
    </span>
  );
}

/** Крапка стану. Текст поруч обовʼязковий: колір сам по собі — не підпис. */
export function StatusDot({ tone = "neutral" }: { tone?: Tone }) {
  const fill: Record<Tone, string> = {
    neutral: "bg-muted",
    accent: "bg-accent",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    info: "bg-info",
  };
  return <span className={cx("size-2 rounded-full", fill[tone])} aria-hidden />;
}

// ── повідомлення ───────────────────────────────────────────────────────────

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  title?: ReactNode;
  children?: ReactNode;
}) {
  const icon: Record<string, IconName> = {
    info: "info",
    warning: "alert",
    danger: "alert",
    success: "check",
  };
  const color = {
    info: "text-info",
    warning: "text-warning",
    danger: "text-danger",
    success: "text-success",
  }[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className="flex gap-3 rounded-md border border-border bg-surface-sunken p-3"
    >
      <Icon name={icon[tone]} className={cx("mt-0.5 size-4", color)} />
      <div className="min-w-0 text-sm">
        {title ? <p className="font-medium text-primary">{title}</p> : null}
        {children ? <div className="text-secondary">{children}</div> : null}
      </div>
    </div>
  );
}

// ── завантаження й порожнеча ───────────────────────────────────────────────

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cx(
        "inline-block size-4 animate-spin rounded-full",
        "border-2 border-current border-e-transparent",
        className,
      )}
      aria-hidden
    />
  );
}

/**
 * Скелет — форма майбутнього вмісту, а не сірий прямокутник посеред
 * сторінки. Він має займати те саме місце, що займе текст: інакше
 * сторінка стрибне, коли дані прийдуть.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "block rounded-md bg-surface-sunken",
        "bg-[linear-gradient(90deg,transparent,rgb(0_0_0/0.04),transparent)]",
        "bg-[length:200%_100%] animate-shimmer motion-reduce:animate-none",
        className,
      )}
    />
  );
}

export function EmptyState({
  icon = "list",
  title,
  description,
  action,
}: {
  icon?: IconName;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-surface-sunken text-muted">
        <Icon name={icon} className="size-5" />
      </span>
      <div>
        <p className="font-medium text-primary">{title}</p>
        {description ? (
          <p className="mt-1 max-w-measure text-sm text-secondary">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

// ── вкладки ────────────────────────────────────────────────────────────────

export interface TabItem {
  id: string;
  label: ReactNode;
  count?: number;
}

export function Tabs({
  items,
  active,
  onChange,
}: {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    // `pb-px` тут не косметика, а лікування смуги прокрутки.
    //
    // Кнопка активної вкладки зсунута на піксель униз (`-mb-px`), щоб її
    // підкреслення накрило лінію контейнера. Але `overflow-x: auto`
    // робить контейнер прокрутним і по ВЕРТИКАЛІ теж (специфікація: інша
    // вісь перестає бути `visible`), і цей один піксель ставав вертикальною
    // смугою прокрутки — а саме підкреслення зникало під краєм.
    <div
      role="tablist"
      className="flex gap-1 overflow-x-auto border-b border-border pb-px"
    >
      {items.map((item) => {
        const selected = item.id === active;
        return (
          <button
            key={item.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(item.id)}
            className={cx(
              "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors duration-fast",
              selected
                ? "border-accent font-medium text-primary"
                : "border-transparent text-secondary hover:text-primary",
            )}
          >
            {item.label}
            {item.count !== undefined ? (
              <span className="ms-2 text-xs tabular-nums text-muted">{item.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

// ── таблиця ────────────────────────────────────────────────────────────────

/**
 * Таблиця завжди в контейнері з горизонтальним прокручуванням: широкий
 * вміст має прокручуватися сам, а не тягнути за собою сторінку.
 */
export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full min-w-[36rem] border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, numeric }: { children?: ReactNode; numeric?: boolean }) {
  return (
    <th
      scope="col"
      className={cx(
        "border-b border-border pb-2 text-xs font-medium uppercase tracking-wide text-muted",
        numeric ? "text-end" : "text-start",
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  numeric,
  className,
}: {
  children?: ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  return (
    <td
      className={cx(
        "border-b border-border py-3 align-middle text-primary",
        numeric && "text-end tabular-nums",
        className,
      )}
    >
      {children}
    </td>
  );
}

// ── розкриття ──────────────────────────────────────────────────────────────

/**
 * Поступове розкриття: суть одразу, деталі за бажанням.
 *
 * Використано `<details>`, а не власний стан: воно працює без JS, шукається
 * браузером у режимі пошуку сторінкою й не потребує ARIA — усе те, що
 * власна реалізація зазвичай губить.
 */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details open={defaultOpen} className="group">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm text-secondary hover:text-primary [&::-webkit-details-marker]:hidden">
        <Icon
          name="chevron-right"
          className="size-4 transition-transform duration-fast group-open:rotate-90 rtl:group-open:-rotate-90"
        />
        {summary}
      </summary>
      <div className="mt-3 animate-fade-in motion-reduce:animate-none">{children}</div>
    </details>
  );
}

// ── підказка ───────────────────────────────────────────────────────────────

/**
 * Підказка на наведення й на фокус. Не єдине джерело важливого: те, що
 * можна прочитати лише мишею, недоступне з клавіатури й з сенсорного
 * екрана.
 */
export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <span className="group/tip relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={cx(
          "pointer-events-none absolute bottom-full start-1/2 z-20 mb-1.5 -translate-x-1/2 rtl:translate-x-1/2",
          "whitespace-nowrap rounded-md bg-primary px-2 py-1 text-xs text-inverse",
          "opacity-0 shadow-overlay transition-opacity duration-fast",
          "group-hover/tip:opacity-100 group-focus-within/tip:opacity-100",
        )}
      >
        {text}
      </span>
    </span>
  );
}

// ── випадне меню ───────────────────────────────────────────────────────────

export function Dropdown({
  trigger,
  children,
  align = "end",
  side = "down",
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: ReactNode;
  align?: "start" | "end";
  /**
   * Куди розкривається меню.
   *
   * Статично, а не «автоматично за вільним місцем»: єдине меню, якому
   * потрібен `up`, стоїть унизу липкої бічної панелі й буде там завжди,
   * при будь-якій висоті вікна. Вимірювати те, що відоме наперед, —
   * значить додати перестрибування меню під час відкриття заради
   * випадку, якого немає.
   */
  side?: "down" | "up";
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function away(event: MouseEvent) {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      {trigger({ open, toggle: () => setOpen((was) => !was) })}
      {open ? (
        <div
          role="menu"
          className={cx(
            "absolute z-30 min-w-48 rounded-md border border-border",
            "bg-surface p-1 shadow-overlay animate-fade-in motion-reduce:animate-none",
            side === "up" ? "bottom-full mb-1" : "top-full mt-1",
            align === "end" ? "end-0" : "start-0",
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function MenuItem({
  icon,
  children,
  onClick,
  tone = "neutral",
}: {
  icon?: IconName;
  children: ReactNode;
  onClick?: () => void;
  tone?: "neutral" | "danger";
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className={cx(
        "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-start text-sm",
        "transition-colors duration-fast hover:bg-surface-sunken",
        tone === "danger" ? "text-danger" : "text-primary",
      )}
    >
      {icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}

// ── діалог ─────────────────────────────────────────────────────────────────

export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-primary/20 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={cx(
          "w-full max-w-lg rounded-lg border border-border bg-surface shadow-overlay",
          "animate-fade-in motion-reduce:animate-none",
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border p-5">
          <h2 className="text-lg font-semibold tracking-tight text-primary">{title}</h2>
          <IconButton icon="close" label="Close" onClick={onClose} />
        </div>
        <div className="p-5">{children}</div>
        {footer ? (
          <div className="flex justify-end gap-2 border-t border-border p-5">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}

// ── погортати ──────────────────────────────────────────────────────────────

export function Pagination({
  page,
  hasNext,
  onChange,
  labels,
}: {
  page: number;
  hasNext: boolean;
  onChange: (page: number) => void;
  labels: { previous: string; next: string; page: string };
}) {
  return (
    <nav className="flex items-center justify-between gap-4 pt-4" aria-label={labels.page}>
      <Button
        variant="quiet"
        size="sm"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        {labels.previous}
      </Button>
      <span className="text-xs tabular-nums text-muted">{page}</span>
      <Button variant="quiet" size="sm" disabled={!hasNext} onClick={() => onChange(page + 1)}>
        {labels.next}
      </Button>
    </nav>
  );
}
