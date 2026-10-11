"use client";

/**
 * Ідентичність AI-провайдера на поверхнях присутності.
 *
 * Сьогодні — офіційна текстова назва (номінативне використання, дозволене
 * завжди). Графічні знаки всіх чотирьох вимагають окремих дій власника:
 * Perplexity й Anthropic — попередньої письмової згоди (API ToS /
 * commercial terms), Google — дозволу через Brand Resource Center,
 * OpenAI дозволяє бейдж «Powered by OpenAI» для API-клієнтів, але сам
 * файл живе на openai.com/brand і має бути завантажений людиною.
 *
 * Коли власник покладе ОФІЦІЙНИЙ немодифікований асет у
 * `public/providers/<provider>.svg` (світла тема) і, за наявності,
 * `<provider>-dark.svg`, компонент підхопить його без редизайну: макет
 * уже тримає місце під знак. Жодних згенерованих, перемальованих чи
 * трасованих логотипів тут не буде ніколи.
 */

import { useState } from "react";

/** Офіційні назви. Торгові назви не перекладаються. Точні продукти:
 *  ми викликаємо API-продукти, не споживчі застосунки. */
export const PROVIDER_LABELS: Record<string, string> = {
  openai: "ChatGPT / OpenAI",
  anthropic: "Claude / Anthropic",
  perplexity: "Perplexity",
  google: "Gemini / Google",
};

/** Підпис для доступності й тултіпа: що саме викликається. */
export const PROVIDER_API_LABELS: Record<string, string> = {
  openai: "OpenAI API (web search)",
  anthropic: "Anthropic Claude API (web search)",
  perplexity: "Perplexity Agent API (web search)",
  google: "Google Gemini API (Google Search grounding)",
};

/** Провайдери, чий офіційний асет уже покладено власником. Порожньо,
 *  поки дозволи/файли не отримані — див. коментар модуля. */
export const APPROVED_ASSETS: ReadonlySet<string> = new Set();

export function ProviderMark({
  provider,
  muted = false,
}: {
  provider: string;
  /** Недоступний/збійний провайдер: ідентичність лишається видимою,
   *  але стан помітний. */
  muted?: boolean;
}) {
  const [assetFailed, setAssetFailed] = useState(false);
  const label = PROVIDER_LABELS[provider] ?? provider;
  const title = PROVIDER_API_LABELS[provider] ?? label;
  const showAsset = APPROVED_ASSETS.has(provider) && !assetFailed;

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${muted ? "opacity-55" : ""}`}
      title={title}
    >
      {showAsset ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`/providers/${provider}.svg`}
          alt={label}
          className="h-4 w-auto dark:hidden"
          onError={() => setAssetFailed(true)}
        />
      ) : null}
      {showAsset ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`/providers/${provider}-dark.svg`}
          alt=""
          aria-hidden
          className="hidden h-4 w-auto dark:inline"
          onError={() => setAssetFailed(true)}
        />
      ) : null}
      <span className="font-medium">{label}</span>
    </span>
  );
}
