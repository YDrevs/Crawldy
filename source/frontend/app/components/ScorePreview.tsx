/**
 * Демонстраційний результат для першого екрана.
 *
 * Не знімок і не картинка: справжні компоненти з тими самими токенами.
 * Через це він не старіє окремо від продукту — вигляд бала на головній і
 * в кабінеті міняється однією правкою.
 *
 * ## Те, що це демо, має бути видно з першого погляду
 *
 * Дрібний підпис під карткою цього не робив: людина бачила бал і адресу
 * й на секунду думала, що це про її сайт. Тому позначка тепер **у самій
 * картці**, зверху, разом із вигаданим доменом — а не під нею.
 *
 * Числа вигадані навмисно. Показувати чийсь справжній бал означало б
 * публікувати чужі проблеми; показувати власний — хвалитися там, де
 * читач хоче побачити свій.
 */

import { Icon } from "./Icon";
import { Score, ScoreBar } from "./Score";
import type { Locale } from "../lib/contracts";

interface Row {
  label: string;
  score: number;
}

/**
 * Приклад звіту теж говорить мовою сторінки.
 *
 * Спокуса лишити його англійським велика: це «просто картинка».
 * Насправді це найпомітніший блок першого екрана, і англійський текст
 * під німецькою адресою — не прогалина перекладу, а англійський вміст
 * на неанглійській сторінці. Саме те, чого ми не дозволяємо клієнтам.
 *
 * Назви вимірів тут ті самі, що в кабінеті: людина, яка побачила
 * «Sichtbarkeit in der Suche» на головній, має знайти той самий рядок у
 * своєму звіті.
 */
interface Copy {
  example: string;
  sample: string;
  overall: string;
  band: string;
  coverage: string;
  pages: string;
  critical: string;
  points: string;
  title: string;
  text: string;
  seen: string;
  modules: string[];
}

/**
 * Порядок навмисний: спершу те, чим Crawldy відрізняється (пошук і AI),
 * потім допоміжні виміри. Той самий порядок, що й у розділі про виміри
 * нижче на сторінці.
 */
const SCORES = [61, 38, 45, 74, 82, 69];

const COPY: Record<Locale, Copy> | Partial<Record<Locale, Copy>> = {
  en: {
    example: "Example", sample: "Sample audit of example-shop.com",
    overall: "Overall score", band: "Fair", coverage: "Coverage",
    pages: "24 of 31 pages", critical: "Critical", points: "+9 points",
    title: "Product pages carry no structured data",
    text: "There is nothing structured here for an AI system to use as a source.",
    seen: "Seen on 18 pages",
    modules: ["Search visibility", "AI readiness", "AI citability", "Speed & UX",
              "Security basics", "Accessibility"],
  },
  de: {
    example: "Beispiel", sample: "Beispielbericht für example-shop.com",
    overall: "Gesamtbewertung", band: "Befriedigend", coverage: "Abdeckung",
    pages: "24 von 31 Seiten", critical: "Kritisch", points: "+9 Punkte",
    title: "Produktseiten ohne strukturierte Daten",
    text: "Hier gibt es nichts Strukturiertes, das ein KI-System als Quelle nutzen könnte.",
    seen: "Auf 18 Seiten gesehen",
    modules: ["Sichtbarkeit in der Suche", "KI-Bereitschaft", "Als Quelle nutzbar",
              "Tempo & Bedienung", "Sicherheitsgrundlagen", "Barrierefreiheit"],
  },
  es: {
    example: "Ejemplo", sample: "Informe de ejemplo de example-shop.com",
    overall: "Nota global", band: "Aceptable", coverage: "Cobertura",
    pages: "24 de 31 páginas", critical: "Crítico", points: "+9 puntos",
    title: "Las páginas de producto no llevan datos estructurados",
    text: "Aquí no hay nada estructurado que un sistema de IA pueda usar como fuente.",
    seen: "Visto en 18 páginas",
    modules: ["Visibilidad en buscadores", "Preparación para la IA", "Utilizable como fuente",
              "Velocidad y uso", "Seguridad básica", "Accesibilidad"],
  },
  fr: {
    example: "Exemple", sample: "Rapport type pour example-shop.com",
    overall: "Note globale", band: "Correct", coverage: "Couverture",
    pages: "24 pages sur 31", critical: "Critique", points: "+9 points",
    title: "Les pages produit n'ont aucune donnée structurée",
    text: "Rien ici n'est structuré pour qu'un système d'IA puisse s'en servir comme source.",
    seen: "Vu sur 18 pages",
    modules: ["Visibilité dans la recherche", "Préparation à l'IA", "Exploitable comme source",
              "Vitesse et confort", "Bases de sécurité", "Accessibilité"],
  },
  ru: {
    example: "Пример", sample: "Пример отчёта по example-shop.com",
    overall: "Общая оценка", band: "Средне", coverage: "Охват",
    pages: "24 из 31 страницы", critical: "Критично", points: "+9 баллов",
    title: "На страницах товаров нет структурированных данных",
    text: "Здесь нет ничего структурированного, что нейросеть могла бы взять как источник.",
    seen: "Замечено на 18 страницах",
    modules: ["Видимость в поиске", "Готовность к ИИ", "Пригодность как источник",
              "Скорость и удобство", "Базовая защита", "Доступность"],
  },
  uk: {
    example: "Приклад", sample: "Приклад звіту для example-shop.com",
    overall: "Загальний бал", band: "Посередньо", coverage: "Покриття",
    pages: "24 з 31 сторінки", critical: "Критично", points: "+9 балів",
    title: "На сторінках товарів немає структурованих даних",
    text: "Тут немає нічого структурованого, що ШІ-система могла б узяти як джерело.",
    seen: "Помічено на 18 сторінках",
    modules: ["Видимість у пошуку", "Готовність до ШІ", "Придатність як джерело",
              "Швидкість і зручність", "Базовий захист", "Доступність"],
  },
};

export function ScorePreview({ locale = "en" }: { locale?: Locale }) {
  const t = COPY[locale] ?? (COPY.en as Copy);
  const rows: Row[] = t.modules.map((label, i) => ({ label, score: SCORES[i] }));
  return (
    <figure className="m-0">
      <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-raised">
        {/* Позначка демо — частина картки, а не підпис під нею.

            Назва прикладу переноситься на вузькому екрані й обрізається
            лише від `sm`. Саме цей рядок тримав головну на 357px при
            вікні 320: `truncate` — це `white-space: nowrap`, а мінімальна
            ширина flex-контейнера рахується з ПОВНОЇ ширини нерозривного
            тексту незалежно від `min-width: 0` чи `flex-basis: 0` на
            самому тексті. Картка не стискалась, колонка сітки героя
            ставала ширшою за вікно, і сторінка отримувала горизонтальний
            скрол — 57px українською, 35px англійською. */}
        <div className="flex items-center gap-2 border-b border-border bg-surface-sunken px-5 py-2.5">
          <span className="shrink-0 rounded-full bg-brand px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-brand-ink">
            {t.example}
          </span>
          {/* На вузькому екрані — 14px: це пʼять слів пояснювального
              тексту, а не підпис блока, і ворота захоплення міряють його
              як абзац. Від `sm` повертається кегль підпису. */}
          <span className="min-w-0 text-sm text-secondary sm:truncate sm:text-xs">
            {t.sample}
          </span>
        </div>

        <div className="p-5" aria-hidden>
          {/* Бал і покриття поруч: число без покриття подається
              впевненіше, ніж заслуговує. На вузькому екрані покриття
              переходить під бал, а не тисне картку вшир. */}
          <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">{t.overall}</p>
              <div className="mt-1">
                <Score value={62} size="lg" bandLabel={t.band} />
              </div>
            </div>
            <div className="text-end">
              <p className="text-xs uppercase tracking-wide text-muted">{t.coverage}</p>
              <p className="mt-2 text-sm tabular-nums text-secondary">{t.pages}</p>
            </div>
          </div>

          {/* Напрями. Смуга читається швидше за число в ряду.

              До `sm` ряд стає двома рядками: назва й число зверху, смуга
              на всю ширину під ними. Колонка назви в 10rem на вікні 320
              лишала б смузі два десятки пікселів — за такої ширини вона
              нічого не показує. */}
          <ul className="mt-5 flex flex-col gap-3">
            {rows.map((row) => (
              <li
                key={row.label}
                className="grid grid-cols-[minmax(0,1fr)_2rem] items-center gap-x-3 gap-y-1.5 sm:grid-cols-[10rem_minmax(0,1fr)_2rem] sm:gap-3"
              >
                <span className="truncate text-sm text-secondary">{row.label}</span>
                <span className="col-span-2 sm:col-span-1 sm:col-start-2 sm:row-start-1">
                  <ScoreBar value={row.score} />
                </span>
                <span className="col-start-2 row-start-1 text-end text-sm tabular-nums text-primary sm:col-start-3">
                  {row.score}
                </span>
              </li>
            ))}
          </ul>

          {/* Одна знахідка — щоб було видно, що продукт віддає дію, а не бал.
              Підписи знахідки на вузькому екрані беруть 14px: у долоні
              13px читається гірше, ніж на моніторі, — та сама причина, з
              якої шкала токенів піднімає `text-sm` нижче за 480px. */}
          <div className="mt-5 rounded-md border border-border bg-surface-sunken p-4">
            <div className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-severity-critical" />
              <span className="text-sm font-medium text-severity-critical sm:text-xs">{t.critical}</span>
              <span className="ms-auto text-sm text-muted sm:text-xs">{t.points}</span>
            </div>
            <p className="mt-2 text-sm font-medium text-primary">
              {t.title}
            </p>
            <p className="mt-1 text-sm text-secondary">
              {t.text}
            </p>
            <p className="mt-3 inline-flex items-center gap-1 text-sm text-accent-text sm:text-xs">
              {t.seen}
              <Icon name="chevron-right" className="size-3" />
            </p>
          </div>
        </div>
      </div>
    </figure>
  );
}
