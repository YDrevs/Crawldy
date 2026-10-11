"use client";

/**
 * Якими моделями зараз міряється Actual AI Presence — на публічній
 * сторінці «Видимість у ШІ».
 *
 * ## Назви моделей — дані, а не текст
 *
 * Копія сторінки шістьма мовами не містить жодної назви моделі: вони
 * приходять з `/v1/presence/models`, тобто з ТІЄЇ САМОЇ політики, яка
 * виконує прогін. Зашита назва розійшлася б із продуктом мовчки й
 * одразу в шести мовах — саме так на цій сторінці могло б зʼявитися
 * «GPT-5.1», виведений із ChatGPT ще в березні.
 *
 * Запит іде без кешу, як у `PricingCards` для цін: зміна моделі в
 * конфігурації видна на сторінці без перезбірки.
 *
 * ## Вигаданих назв не буває в жодному стані
 *
 * Поки дані не прийшли або запит упав, рядок показує лише назву
 * платформи без моделі. Фолбека з «типовою» моделлю тут немає й бути не
 * може: сторінка називає те, чим МІРЯЮТЬ, і помилка тут — це обіцянка
 * вимірювання, якого не було.
 *
 * Провайдер, вимкнений у політиці, не приходить у відповіді й не
 * показується: ми його не питаємо.
 */

import { useEffect, useState } from "react";

import { API_URL } from "../lib/api";

/** Публічні назви платформ і порядок показу — незмінні. */
const PROVIDERS: { key: string; label: string }[] = [
  { key: "anthropic", label: "Claude" },
  { key: "openai", label: "ChatGPT" },
  { key: "google", label: "Gemini" },
  { key: "perplexity", label: "Perplexity" },
];

type PresenceModel = { provider: string; model: string };

export function PresenceModels({
  intro,
  note,
}: {
  /** Абзац перед переліком. */
  intro: string;
  /** Абзац після переліку: моделі змінюються, результат — про показані. */
  note: string;
}) {
  const [models, setModels] = useState<PresenceModel[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(`${API_URL}/v1/presence/models`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error("http");
        const body = (await res.json()) as PresenceModel[];
        if (!cancelled) setModels(body);
      } catch {
        // Мовчазна поразка: рядки лишаються без назв моделей.
        if (!cancelled) setModels([]);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const shown = PROVIDERS.map((p) => ({
    label: p.label,
    model: models?.find((m) => m.provider === p.key)?.model ?? null,
  })).filter((row) => models === null || row.model !== null);

  return (
    <>
      <p className="mt-4 max-w-measure text-sm text-muted">{intro}</p>
      <ul className="mt-4 flex flex-col gap-1">
        {shown.map((row) => (
          <li key={row.label} className="text-sm text-foreground">
            <span className="font-medium">{row.label}</span>
            {row.model === null ? null : (
              <>
                {" — "}
                <span className="font-mono text-muted">{row.model}</span>
              </>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-4 max-w-measure text-sm text-muted">{note}</p>
    </>
  );
}
