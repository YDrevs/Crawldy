"use client";

/**
 * Запуск нової перевірки з кабінету.
 *
 * Одна дія на весь кабінет: кнопка розкриває поле адреси, сабміт ставить
 * аудит через `POST /v1/audits` і веде на сторінку звіту, яка сама
 * дочікується результату. Сайт створюється бекендом неявно
 * (`ensure_site_for`) — окремого кроку «додати сайт» не існує, бо він
 * додав би екран між наміром і результатом.
 *
 * Відмова 402 — не помилка коду, а стан акаунта: перевірок немає. Тому
 * в неї власний текст із дорогою до «Тариф і використання», а не сирий
 * рядок бекенда.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "./primitives";
import { ApiError, createAudit } from "../lib/api";
import { useLocale } from "../lib/locale";

export function NewAuditAction({ initialUrl = "" }: { initialUrl?: string }) {
  const { t } = useLocale();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(initialUrl);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const target = url.trim();
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      const started = await createAudit({ urls: [target] });
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

  if (!open) {
    return (
      <Button icon="plus" onClick={() => setOpen(true)}>
        {t("action.newAnalysis")}
      </Button>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <input
          type="text"
          inputMode="url"
          autoComplete="url"
          required
          autoFocus
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://example.com"
          aria-label={t("newAudit.label")}
          className="h-9 w-64 rounded-md border border-border bg-surface px-3 text-sm text-primary outline-none focus:border-accent"
        />
        <Button icon="plus" disabled={busy} type="submit">
          {t("newAudit.start")}
        </Button>
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </form>
  );
}
