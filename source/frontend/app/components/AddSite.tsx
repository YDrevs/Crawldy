"use client";

/**
 * Додати сайт — окремо від запуску перевірки.
 *
 * Сайт зʼявлявся в кабінеті лише разом із першою перевіркою його
 * адреси. Один крок замість двох виглядав економією, але змішував два
 * різні наміри: «хочу вести цей сайт» і «витрать мою перевірку зараз».
 * Тепер запис створюється сам по собі — `POST /v1/sites`, — і не
 * коштує ані повної перевірки, ані перевірки присутності.
 *
 * Неявне створення сайту разом з аудитом лишається живим: воно і далі
 * приводить у перелік сайти, перевірені гостем або куплені разово.
 */

import { useState } from "react";

import { Button } from "./primitives";
import { createSite } from "../lib/api";
import { useLocale } from "../lib/locale";
import type { Site } from "../lib/contracts";

export function AddSiteAction({ onAdded }: { onAdded: (site: Site) => void }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const target = url.trim();
    if (!target) return;
    setBusy(true);
    setFailed(false);
    try {
      const site = await createSite(target);
      setUrl("");
      setOpen(false);
      onAdded(site);
    } catch {
      // Причин відмови дві — адреса не читається (422) і такий сайт уже
      // додано (409), — і обидві людина виправляє тим самим рухом:
      // подивитись на адресу в полі.
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button icon="plus" onClick={() => setOpen(true)}>
        {t("sites.add")}
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
          aria-label={t("sites.addUrl")}
          className="h-9 w-64 rounded-md border border-border bg-surface px-3 text-sm text-primary outline-none focus:border-accent"
        />
        <Button icon="plus" disabled={busy} type="submit">
          {t("sites.addSubmit")}
        </Button>
      </div>
      {failed ? <p className="text-xs text-danger">{t("sites.addFailed")}</p> : null}
    </form>
  );
}
