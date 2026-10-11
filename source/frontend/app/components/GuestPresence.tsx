"use client";

/**
 * Actual AI Presence для гостя після оплати — ланка, якої не було.
 *
 * Разова покупка дає одиницю присутності, але форма запуску жила за
 * входом і вимагала бренд та категорію, яких гість не вводив. Тепер
 * факти виводяться з того самого аудиту й показуються тут — із
 * можливістю змінити (рішення власника 2026-09-06). Прогін іде
 * оплаченою одиницею тієї самої гостьової організації.
 *
 * Поля не ховаються за підтвердженням «усе правильно?»: людина бачить
 * бренд, варіанти написання, категорію й місто разом із джерелом кожного
 * і править те, що ми взяли неправильно. Порожнє поле означає, що
 * джерела не було, — і його треба заповнити, а не вгадати за клієнта.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Field, Input, Panel, Spinner } from "./primitives";
import {
  type GuestPresence as GuestPresenceState,
  type GuestPresenceRun,
  auditIsRunning,
  downloadGuestPresenceReport,
  readGuestPresence,
  readGuestPresenceRun,
  startGuestPresence,
} from "../lib/guest-payment";
import { useLocale } from "../lib/locale";
import { problemKey } from "../lib/problem";

export function GuestPresence({ auditId }: { auditId: string }) {
  const { t } = useLocale();
  const [state, setState] = useState<GuestPresenceState | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [form, setForm] = useState({ brand: "", aliases: "", category: "", location: "" });
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<GuestPresenceRun | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await readGuestPresence(auditId);
      setState(next);
      setFailed(null);
      // Останній прогін цього сайту, якщо вже є: людина повернулася
      // на сторінку й бачить стан, а не порожню форму.
      setRun(next.runs[0] ?? null);
      if (!touched) {
        setForm({
          brand: next.suggestion.brand,
          aliases: next.suggestion.brand_aliases
            .filter((a) => a !== next.suggestion.brand)
            .join(", "),
          category: next.suggestion.category,
          location: next.suggestion.location ?? "",
        });
      }
    } catch (err) {
      setFailed(problemKey(err));
    }
  }, [auditId, touched]);

  useEffect(() => {
    void load();
  }, [load]);

  // Поки прогін іде, стан оновлюється сам.
  useEffect(() => {
    if (run === null || !auditIsRunning(run.status)) return;
    const timer = setInterval(() => {
      void readGuestPresenceRun(run.id).then(setRun).catch(() => undefined);
    }, 6000);
    return () => clearInterval(timer);
  }, [run]);

  const idempotencyKey = useMemo(
    () => crypto.randomUUID(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [form.brand, form.category, form.location, form.aliases],
  );

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const started = await startGuestPresence(auditId, {
        brand: form.brand.trim(),
        brand_aliases: form.aliases
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        category: form.category.trim(),
        location: form.location.trim() || null,
        language: state?.suggestion.language ?? "en",
        idempotency_key: idempotencyKey,
      });
      setRun(started);
    } catch (err) {
      setError(problemKey(err, { 402: "free.presence.noCredit" }));
    } finally {
      setSubmitting(false);
    }
  };

  if (failed) return null; // 402/404 — присутності в цій покупці немає, і блок не існує
  if (state === null) {
    return (
      <div className="flex justify-center py-6 text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const update = (field: keyof typeof form, value: string) => {
    setTouched(true);
    setForm((prev) => ({ ...prev, [field]: value }));
  };
  const sourceOf = (field: "brand" | "category" | "location") => {
    const source = state.suggestion.sources[field];
    return source ? t(`free.presence.source.${source}`) : undefined;
  };
  const canStart =
    state.can_start && run === null && form.brand.trim() && form.category.trim();

  return (
    <Panel className="mt-8 p-5">
      <h2 className="text-base font-semibold text-primary">{t("free.presence.title")}</h2>
      <p className="mt-1 max-w-measure text-sm text-secondary">{t("free.presence.lead")}</p>

      {run ? (
        <RunState run={run} />
      ) : (
        <>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label={t("free.presence.brand")} hint={sourceOf("brand")}>
              <Input value={form.brand} onChange={(e) => update("brand", e.target.value)} />
            </Field>
            <Field label={t("free.presence.aliases")} hint={t("free.presence.aliasesHint")}>
              <Input value={form.aliases} onChange={(e) => update("aliases", e.target.value)} />
            </Field>
            <Field label={t("free.presence.category")} hint={sourceOf("category")}>
              <Input
                value={form.category}
                onChange={(e) => update("category", e.target.value)}
              />
            </Field>
            <Field label={t("free.presence.location")} hint={sourceOf("location")}>
              <Input
                value={form.location}
                onChange={(e) => update("location", e.target.value)}
              />
            </Field>
          </div>
          {error ? (
            <div className="mt-4">
              <Alert tone="danger">{t(error)}</Alert>
            </div>
          ) : null}
          {!state.can_start ? (
            <p className="mt-4 text-sm text-muted">{t("free.presence.noCredit")}</p>
          ) : null}
          <div className="mt-4">
            <Button loading={submitting} disabled={!canStart} onClick={() => void submit()}>
              {t("free.presence.run")}
            </Button>
          </div>
        </>
      )}
    </Panel>
  );
}

function RunState({ run }: { run: GuestPresenceRun }) {
  const { t, locale } = useLocale();
  if (auditIsRunning(run.status)) {
    return (
      <div className="mt-4 flex items-center gap-2 text-sm text-secondary">
        <Spinner className="size-4" />
        {t("free.presence.running")}
      </div>
    );
  }
  if (run.status === "failed") {
    return (
      <div className="mt-4">
        <Alert tone="danger">{t("free.presence.failed")}</Alert>
      </div>
    );
  }
  return (
    <div className="mt-4 text-sm text-secondary">
      <p>
        {t("free.presence.done")}{" "}
        <span className="tabular-nums text-primary">
          {run.observations_ok}/{run.observations_total}
        </span>{" "}
        {t("free.presence.observations")}
      </p>
      {/* Присутність продається разом із аудитом, тож її документи гість
          отримує так само — двома видами й без акаунта. */}
      <div className="mt-3 flex flex-wrap gap-2">
        {(["general", "technical"] as const).map((kind) => (
          <Button
            key={kind}
            variant="quiet"
            onClick={() =>
              void downloadGuestPresenceReport(run.id, locale, kind).catch(
                () => undefined,
              )
            }
          >
            {t(kind === "general" ? "free.presence.general" : "free.presence.technical")}
          </Button>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">{t("free.presence.seeInCabinet")}</p>
    </div>
  );
}
