"use client";

/**
 * Дрібні складники службових сторінок: стан, джерело значення, секрет.
 *
 * Живуть окремо від сторінок, бо їх три штуки на дві сторінки, і кожна
 * інакше показувала б те саме. Головне тут — поводження з секретом:
 * значення НЕ приходить із сервера, тож поле не редагується як звичайне.
 * Воно має рівно три стани — «налаштовано», «вводимо нове», «прибрати».
 */

import { useState } from "react";

import { Button, Field, Input } from "../../components/primitives";
import { cx } from "../../lib/cx";
import type { SettingField } from "../../lib/admin-api";

type Tone = "success" | "warning" | "danger" | "neutral";

// Лише наявні токени теми: «м'яких» тлів у палітрі рівно одне
// (`accent-soft`), решта станів позначається рамкою й кольором тексту.
const TONES: Record<Tone, string> = {
  success: "border-success bg-surface text-success",
  warning: "border-accent bg-accent-soft text-accent-ink",
  danger: "border-danger bg-surface text-danger",
  neutral: "border-border bg-surface-sunken text-secondary",
};

export function StatusPill({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
      )}
    >
      {label}
    </span>
  );
}

/**
 * Підпис під полем — лише коли є що сказати.
 *
 * Рядка «налаштовано · з оточення» під кожним полем більше немає
 * (рішення власника): стан і так видно з самого поля — заповненого,
 * порожнього чи з крапками замість секрету, — а однаковий підпис під
 * кожним рядком форми перестає читатися вже на третьому.
 *
 * Лишається один випадок, і він не про джерело, а про поломку: секрет
 * збережено іншим ключем шифрування, ніж чинний. Без цього рядка поле
 * виглядало б просто ненастроєним, і причина була б невідомою.
 */
export function configProblem(
  field: SettingField,
  t: (key: string) => string,
): string | undefined {
  if (field.undecryptable) return t("field.undecryptable");
  return undefined;
}

export interface Draft {
  value: (field: SettingField) => string | undefined;
  set: (key: string, value: string) => void;
  remove: (key: string) => void;
  removed: (key: string) => boolean;
  touched: (key: string) => boolean;
  payload: () => Record<string, string | null>;
  clear: () => void;
}

/**
 * Незбережені зміни форми. `null` у payload означає «прибрати збережене»,
 * і це не те саме, що порожній рядок у полі: перше повертає значення з
 * оточення, друге просто нічого не змінює.
 */
export function useDraft(): Draft {
  const [values, setValues] = useState<Record<string, string | null>>({});
  return {
    value: (field) => {
      const draft = values[field.key];
      return draft === undefined ? undefined : (draft ?? "");
    },
    set: (key, value) => setValues((prev) => ({ ...prev, [key]: value })),
    remove: (key) => setValues((prev) => ({ ...prev, [key]: null })),
    removed: (key) => values[key] === null,
    touched: (key) => key in values,
    payload: () => values,
    clear: () => setValues({}),
  };
}

/**
 * Поле секрету: значення сюди не приходить, тому редагування — це
 * завжди заміна. Поки нове не введено, показується стан і хвіст.
 */
export function SecretField({
  field,
  draft,
  t,
}: {
  field: SettingField;
  draft: Draft;
  t: (key: string) => string;
}) {
  const [editing, setEditing] = useState(false);
  const label = t(`field.${field.key}`);
  const pending = draft.value(field);
  const removing = draft.removed(field.key);

  if (editing || pending !== undefined) {
    return (
      <Field label={label} hint={configProblem(field, t)}>
        <div className="flex gap-2">
          <Input
            autoFocus
            type="password"
            autoComplete="off"
            value={removing ? "" : (pending ?? "")}
            placeholder="••••••••"
            onChange={(e) => draft.set(field.key, e.target.value)}
          />
          <Button
            variant="ghost"
            onClick={() => {
              draft.set(field.key, "");
              setEditing(false);
            }}
          >
            {t("common.cancel")}
          </Button>
        </div>
      </Field>
    );
  }

  return (
    <Field label={label} hint={configProblem(field, t)}>
      <div className="flex items-center gap-2">
        <span className="flex-1 rounded-md border border-border bg-surface-sunken px-3 py-2 font-mono text-sm text-muted">
          {field.configured ? `••••••••${field.hint ? ` ${field.hint}` : ""}` : "—"}
        </span>
        <Button
          variant="quiet"
          disabled={field.secret && !field.storage_available}
          onClick={() => setEditing(true)}
        >
          {t("common.replace")}
        </Button>
        {field.source === "admin" ? (
          <Button variant="ghost" onClick={() => draft.remove(field.key)}>
            {t("common.remove")}
          </Button>
        ) : null}
      </div>
    </Field>
  );
}

/**
 * Відстань між колонками службових таблиць.
 *
 * Саме правило живе в `globals.css` (`.admin-table`), бо довільний
 * варіант Tailwind із двокрапкою всередині дужок не потрапляє у
 * збірку — це виміряно, а не припущено. Клас накладається на обгортку
 * службової таблиці, тож кабінет клієнта лишається незмінним.
 */
export const TABLE_SPACING = "admin-table";

/** Число з підписом. Уся аналітика складається з них. */
export function Kpi({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-primary">{value}</p>
      {note ? <p className="mt-0.5 text-xs text-muted">{note}</p> : null}
    </div>
  );
}
