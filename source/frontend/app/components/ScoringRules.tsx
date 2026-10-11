/**
 * «Точні правила розрахунку» — компактна таблиця на сторінці методології.
 *
 * ## Числа не пишуться в тексті сторінки
 *
 * Значення приходять зі знімка `scoring-facts.json`, який звіряється з
 * реальною реалізацією скорингу бекендовим тестом
 * (`backend/tests/test_methodology_page_facts.py`). Розходження між
 * сторінкою і кодом — це впала збірка бекенда, а не тиха неправда на
 * сайті. Шість мов рендерять ОДИН набір чисел; мова постачає лише
 * підписи.
 */

import facts from "../content/methodology/scoring-facts.json";
import type { Locale } from "../lib/contracts";

/** Порядок показу — за спаданням ваги, як у самому скорингу. */
const MODULES = [
  "seo",
  "performance",
  "ai_ready",
  "tech",
  "llm_visibility",
  "accessibility",
] as const;

const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;

export interface ScoringRulesStrings {
  /**
   * Назва таблиці для зчитувача екрана.
   *
   * Обовʼязкова, і саме тому окремим полем: англійського запасного
   * значення тут немає взагалі, тож мова, яка його не подала, не
   * збереться. Таблиця без назви для зчитувача — просто «таблиця».
   */
  caption: string;
  weightsTitle: string;
  severityTitle: string;
  limitsTitle: string;
  modules: Record<(typeof MODULES)[number], string>;
  severities: Record<(typeof SEVERITIES)[number], string>;
  /** «Мінімальний обсяг тексту…» → «{n} слів на всьому сайті». */
  minCoverageLabel: string;
  minCoverageValue: string;
  /** «Повторення однієї проблеми» → «щонайбільше ×{n} від однієї знахідки». */
  repetitionLabel: string;
  repetitionValue: string;
  /** «Вплив однієї проблеми…» → «щонайбільше {p} півшкали напряму». */
  shareLabel: string;
  shareValue: string;
}

function fill(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}

export function ScoringRules({
  locale,
  strings,
}: {
  locale: Locale;
  strings: ScoringRulesStrings;
}) {
  const percent = new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 0,
  });

  const subhead = (title: string) => (
    <tr>
      <th
        colSpan={2}
        scope="colgroup"
        className="bg-surface-sunken px-4 py-2 text-start text-xs font-medium uppercase tracking-wide text-muted"
      >
        {title}
      </th>
    </tr>
  );
  const row = (label: string, value: string) => (
    <tr key={label} className="border-t border-border">
      <td className="px-4 py-2 text-sm text-secondary">{label}</td>
      <td className="px-4 py-2 text-end text-sm tabular-nums text-primary">
        {value}
      </td>
    </tr>
  );

  return (
    <div className="mt-6 max-w-2xl overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse">
        {/* Перший елемент таблиці й справжній <caption>, а не
            aria-label: назву таблиці зчитувачі беруть саме звідси.
            `sr-only` лишає її поза екраном — видимо не змінюється
            нічого, і рядок-підзаголовок нижче лишається на місці. */}
        <caption className="sr-only">{strings.caption}</caption>
        <tbody>
          {subhead(strings.weightsTitle)}
          {MODULES.map((module) =>
            row(strings.modules[module], percent.format(facts.weights[module])),
          )}
          {subhead(strings.severityTitle)}
          {SEVERITIES.map((severity) =>
            row(
              strings.severities[severity],
              `×${facts.severity_multipliers[severity]}`,
            ),
          )}
          {subhead(strings.limitsTitle)}
          {row(
            strings.minCoverageLabel,
            fill(strings.minCoverageValue, {
              n: facts.coverage.min_words_for_a_site,
            }),
          )}
          {row(
            strings.repetitionLabel,
            fill(strings.repetitionValue, {
              n: facts.repetition.max_penalty_per_key,
            }),
          )}
          {row(
            strings.shareLabel,
            fill(strings.shareValue, {
              p: percent.format(facts.repetition.max_penalty_share_of_half),
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}
