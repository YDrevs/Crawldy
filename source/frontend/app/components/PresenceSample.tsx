/**
 * Зразок результату Actual AI Presence на маркетинговій сторінці.
 *
 * ## Це ілюстрація формату, і вона це каже вголос
 *
 * Числа тут детерміновані й однакові всіма мовами: вони показують,
 * ЯК виглядає відповідь вимірювання, а не міряють чийсь сайт. Плашка
 * «зразок» стоїть першою, а підпис унизу повторює це словами — рівно
 * той самий принцип, за яким гостьовий екран підписує демо-звіт.
 *
 * Серверний компонент без запитів: справжні числа присутності живуть
 * у кабінеті за платною перевіркою, і жоден маркетинговий рендер по
 * них не ходить.
 */

/** Детерміновані значення зразка — формат відповіді, не вимірювання. */
const SAMPLE = {
  asked: 20,
  mentioned: 3,
  cited: 1,
  competitors: 5,
} as const;

export interface PresenceSampleStrings {
  /** Плашка «ЗРАЗОК» — перша, до будь-якого числа. */
  badge: string;
  title: string;
  /** «{asked} запитань про нішу — без назви бренду в більшості». */
  asked: string;
  /** «Згадано у {mentioned} з {asked} відповідей». */
  mentioned: string;
  /** «Процитовано з посиланням: {cited}». */
  cited: string;
  /** «Замість вас названо {competitors} інших доменів». */
  competitors: string;
  /** Підпис: числа — ілюстрація формату, не вимірювання. */
  note: string;
}

function fill(template: string): string {
  return template
    .replace("{asked}", String(SAMPLE.asked))
    .replace("{mentioned}", String(SAMPLE.mentioned))
    .replace("{cited}", String(SAMPLE.cited))
    .replace("{competitors}", String(SAMPLE.competitors));
}

export function PresenceSample({ strings }: { strings: PresenceSampleStrings }) {
  const rows = [
    fill(strings.asked),
    fill(strings.mentioned),
    fill(strings.cited),
    fill(strings.competitors),
  ];
  return (
    <div className="mt-6 max-w-xl rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center gap-2">
        <span className="rounded bg-surface-sunken px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-muted">
          {strings.badge}
        </span>
        <span className="text-sm font-medium text-primary">{strings.title}</span>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5 text-sm text-secondary">
        <li className="text-primary">ChatGPT · Claude · Perplexity · Gemini</li>
        {rows.map((row) => (
          <li key={row}>{row}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">{strings.note}</p>
    </div>
  );
}
