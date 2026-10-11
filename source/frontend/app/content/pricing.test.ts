/**
 * Сторінка цін: точні заголовки й рядки власника в шести мовах, і
 * жодного числа, написаного руками.
 *
 * Тест читає ВИХІДНИЙ КОД сторінок і компонента, а не рендер: числа
 * приходять із конфігурації бекенда під час виконання, тож єдине, що
 * можна стерегти статично, — це щоб у файлах їх не було взагалі, а
 * структура й слова збігалися з погодженими.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const DIR = join(__dirname, "pricing");
const COMPONENT = join(__dirname, "..", "components", "PricingCards.tsx");
const LOCALES = ["en", "uk", "de", "es", "fr", "ru"] as const;

function code(locale: string): string {
  return readFileSync(join(DIR, `${locale}.tsx`), "utf-8")
    .replace(/\r\n/g, "\n")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const component = readFileSync(COMPONENT, "utf-8")
  .replace(/\r\n/g, "\n")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/^\s*\/\/.*$/gm, "");
const LINES = join(__dirname, "..", "lib", "pricing-lines.ts");
const lines = readFileSync(LINES, "utf-8")
  .replace(/\r\n/g, "\n")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/^\s*\/\/.*$/gm, "");

const H1: Record<string, string> = {
  en: "How much does a website analysis cost?",
  uk: "Скільки коштує перевірка сайту",
  de: "Was kostet eine Website-Analyse?",
  es: "¿Cuánto cuesta analizar un sitio web?",
  fr: "Combien coûte l’analyse d’un site ?",
  ru: "Сколько стоит проверка сайта",
};

/** Затверджене пояснення під H1 (власник, 2026-09-05). */
const LEAD: Record<string, string> = {
  en: "Every option gives you the same full report. You can pay for a single analysis, buy a pack at a lower price per site, or choose a monthly plan.",
  uk: "У всіх платних варіантах ви отримуєте однаковий повний звіт. Можна оплатити одну перевірку, придбати пакет за нижчою ціною за сайт або обрати місячний план.",
  de: "Bei allen Optionen erhalten Sie denselben vollständigen Bericht. Sie können eine einzelne Analyse bezahlen, ein Paket zu einem niedrigeren Preis pro Website kaufen oder einen Monatsplan wählen.",
  es: "Todas las opciones incluyen el mismo informe completo. Puedes pagar un análisis individual, comprar un paquete con un precio más bajo por sitio o elegir un plan mensual.",
  fr: "Toutes les formules donnent accès au même rapport complet. Vous pouvez payer une analyse unique, acheter un pack à un prix inférieur par site ou choisir un forfait mensuel.",
  ru: "Во всех вариантах вы получаете одинаковый полный отчёт. Можно оплатить одну проверку, купить пакет по более низкой цене за сайт или выбрать месячный план.",
};

// Четвертий рядок превʼю затверджено українською; для інших пʼяти мов
// затвердженого еквівалента в каталогах немає, і вигадувати його не можна.
const FREE: Record<string, [string, string[], string]> = {
  en: ["Free Preview", ["Overall website score", "Analysis coverage", "Three issues with the greatest impact"], "Check your site"],
  uk: ["Безкоштовне прев’ю", ["Загальний бал сайту", "Покриття перевірки", "Три проблеми з найбільшим впливом", "Попередній результат без повного звіту"], "Перевірити сайт"],
  de: ["Kostenlose Vorschau", ["Gesamtbewertung der Website", "Abdeckung der Prüfung", "Drei Probleme mit dem größten Einfluss"], "Website prüfen"],
  es: ["Vista previa gratuita", ["Puntuación general del sitio", "Cobertura del análisis", "Tres problemas con mayor impacto"], "Comprobar el sitio"],
  fr: ["Aperçu gratuit", ["Score global du site", "Couverture de l’analyse", "Trois problèmes ayant le plus d’impact"], "Vérifier le site"],
  ru: ["Бесплатный предварительный результат", ["Общая оценка сайта", "Охват проверки", "Три проблемы с наибольшим влиянием"], "Проверить сайт"],
};

const KINDS: Record<string, [string, string, string]> = {
  en: ["Single analysis", "Analysis pack", "Monthly plan"],
  uk: ["Разова перевірка", "Пакет перевірок", "Місячний план"],
  de: ["Einzelanalyse", "Analysepaket", "Monatsplan"],
  es: ["Análisis individual", "Paquete de análisis", "Plan mensual"],
  fr: ["Analyse unique", "Pack d’analyses", "Forfait mensuel"],
  ru: ["Разовая проверка", "Пакет проверок", "Месячный план"],
};

const CTAS: Record<string, [string, string, string]> = {
  en: ["Get the report", "Buy the pack", "Subscribe"],
  uk: ["Отримати звіт", "Придбати пакет", "Підписатися"],
  de: ["Bericht erhalten", "Paket kaufen", "Abonnieren"],
  es: ["Obtener el informe", "Comprar el paquete", "Suscribirse"],
  fr: ["Obtenir le rapport", "Acheter le pack", "S’abonner"],
  ru: ["Получить отчёт", "Купить пакет", "Подписаться"],
};

const BADGE: Record<string, string> = {
  en: "For regular use",
  uk: "Для регулярної роботи",
  de: "Für regelmäßige Nutzung",
  es: "Para uso habitual",
  fr: "Pour une utilisation régulière",
  ru: "Для регулярной работы",
};

// Українська — канонічний перелік власника (2026-09-05); інші мови — вже
// затверджені еквіваленти з каталогів (рядки пейволу `free.unlocks.*`,
// поточні рядки цін). Порядок у картці: кількість → оцінки → проблеми →
// сторінки → пріоритети → звіт → Presence.
const BULLETS: Record<string, string[]> = {
  en: [
    "Scores for each audited area", "All detected issues with evidence", "Pages affected by each issue",
    "What to fix and in what order", "Downloadable full report", "The same full report for every analysis",
    "{unit_price} per analysis", "Does not expire",
    "Unlimited full website analyses", "Allowances renew monthly",
  ],
  uk: [
    "Оцінки за всіма напрямами", "Усі знайдені проблеми з доказами", "Сторінки, яких стосується кожна проблема",
    "Пріоритети та порядок виправлення", "Повний звіт для завантаження", "Усе, що входить у разову перевірку",
    "{unit_price} за одну перевірку", "Пакет не має строку дії",
    "Необмежена кількість повних перевірок", "Ліміти поновлюються щомісяця",
    // Затверджені підписи без числа (власник, 2026-09-05).
    "Повні перевірки сайтів", "Actual AI Presence", "Ціна за одну перевірку", "Actual AI Presence щомісяця",
  ],
  de: [
    "Bewertungen für jeden geprüften Bereich", "Alle gefundenen Probleme mit Nachweisen", "Betroffene Seiten für jedes Problem",
    "Was in welcher Reihenfolge zu beheben ist", "Vollständiger Bericht zum Herunterladen", "Derselbe vollständige Bericht für jede Analyse",
    "{unit_price} pro Analyse", "Kein Ablaufdatum",
    "Unbegrenzte vollständige Website-Analysen", "Kontingente werden monatlich erneuert",
  ],
  es: [
    "Puntuación de cada área analizada", "Todos los problemas detectados con pruebas", "Páginas afectadas por cada problema",
    "Qué corregir y en qué orden", "Informe completo descargable", "El mismo informe completo para cada análisis",
    "{unit_price} por análisis", "No caduca",
    "Análisis completos de sitios ilimitados", "Los límites se renuevan cada mes",
  ],
  fr: [
    "Un score pour chaque domaine analysé", "Tous les problèmes détectés avec leurs preuves", "Pages concernées par chaque problème",
    "Les corrections à effectuer et leur ordre", "Rapport complet à télécharger", "Le même rapport complet pour chaque analyse",
    "{unit_price} par analyse", "Sans date d’expiration",
    "Analyses complètes de sites illimitées", "Les quotas sont renouvelés chaque mois",
  ],
  ru: [
    "Оценки по каждому направлению проверки", "Все найденные проблемы с доказательствами", "Страницы, которых касается каждая проблема",
    "Что исправлять и в каком порядке", "Полный отчёт для скачивания", "Одинаковый полный отчёт для каждой проверки",
    "{unit_price} за одну проверку", "Без срока действия",
    "Неограниченное количество полных проверок", "Лимиты обновляются ежемесячно",
  ],
};

describe("сторінка цін існує шістьма мовами й має погоджені заголовки", () => {
  it("файлів рівно шість", () => {
    const files = readdirSync(DIR).filter((name) => name.endsWith(".tsx"));
    expect(files.length).toBe(LOCALES.length);
  });

  for (const locale of LOCALES) {
    it(`${locale}: H1 точний і той самий у метаданих і в герої`, () => {
      const source = code(locale);
      expect(source).toContain(`h1: ${JSON.stringify(H1[locale])}`);
      // `compact` — лише поле відступів між заголовком і поясненням.
      expect(source).toContain(
        `<Hero title=${JSON.stringify(H1[locale])} compact lead=${JSON.stringify(LEAD[locale])} />`,
      );
    });

    it(`${locale}: під заголовком рівно одне затверджене пояснення, без надзаголовка`, () => {
      const source = code(locale);
      expect((source.match(/lead=/g) ?? []).length).toBe(1);
      expect(source).not.toContain("eyebrow=");
      // Попереднє загальне пояснення «відрізняється лише спосіб оплати»
      // не повернулось: пояснення одне, і воно затверджене дослівно.
      expect(source.toLowerCase()).not.toMatch(
        /only difference|відрізняється лише|unterscheiden sich nur|solo se diferencia|seule différence|отличается только/,
      );
    });
  }
});

describe("рядки — точні формулювання власника", () => {
  for (const locale of LOCALES) {
    it(`${locale}: безкоштовне превʼю — заголовок, перелік, дія`, () => {
      const source = code(locale);
      const [heading, bullets, cta] = FREE[locale];
      expect(source).toContain(JSON.stringify(heading));
      for (const line of bullets) expect(source).toContain(JSON.stringify(line));
      expect(source).toContain(JSON.stringify(cta));
      expect(bullets.length).toBe(locale === "uk" ? 4 : 3);
    });

    it(`${locale}: три платні формати, їхні дії й позначка Monthly`, () => {
      const source = code(locale);
      for (const kind of KINDS[locale]) expect(source).toContain(JSON.stringify(kind));
      for (const cta of CTAS[locale]) expect(source).toContain(JSON.stringify(cta));
      expect(source).toContain(JSON.stringify(BADGE[locale]));
    });

    it(`${locale}: усі сталі рядки переліків присутні`, () => {
      const source = code(locale);
      for (const line of BULLETS[locale]) expect(source).toContain(JSON.stringify(line));
    });

    it(`${locale}: форми множини для кожного налаштованого числа`, () => {
      const source = code(locale);
      // Кожен рядок із числом — форми, а не одне речення: `{n}` мусить
      // стояти в шаблонах, а не число в тексті.
      for (const key of ["analyses", "presence", "presencePerMonth"]) {
        expect(source, key).toContain(`${key}: {`);
      }
      // Кількість повних перевірок місячного плану більше не є параметром
      // цін: вони необмежені за означенням (власник, 2026-09-05). Виправлено
      // поки лише українську сторінку — решта мов ще несе застарілий ключ,
      // і рендер його не читає.
      if (locale === "uk") expect(source).not.toContain("analysesPerMonth");
      const forms = source.match(/\{n\}/g) ?? [];
      expect(forms.length).toBeGreaterThanOrEqual(10);
      if (locale === "uk" || locale === "ru") {
        expect(source).toContain("few:");
        expect(source).toContain("many:");
      }
    });
  }
});

describe("жодного числа й жодної забороненої обіцянки у вмісті", () => {
  for (const locale of LOCALES) {
    it(`${locale}: ціни, кількості й тарифні рівні не написані руками`, () => {
      const source = code(locale);
      // Число в тексті сторінки — зашита ціна або кількість. `{n}` і
      // `{unit_price}` — плейсхолдери, вони чисел не несуть.
      const withoutPlaceholders = source.replace(/\{n\}|\{unit_price\}/g, "");
      const textLiterals = withoutPlaceholders.match(/"[^"\n]*"/g) ?? [];
      const numeric = textLiterals.filter((literal) => /\d/.test(literal));
      expect(numeric, numeric.join("\n")).toEqual([]);
      expect(source).not.toMatch(/\b(USD|EUR|UAH|\$|€|₴)\b/);
    });

    it(`${locale}: без FAQ, таблиці рівнів, «найпопулярніший» і обіцянок «без картки»`, () => {
      const source = code(locale).toLowerCase();
      for (const forbidden of [
        "faq", "most popular", "найпопулярн", "популярн", "beliebtest", "más popular", "plus populaire",
        "starter", "agency", "агенц", "no card", "без картки", "без карты",
        "no signup", "first audit free", "перший аудит безкоштовно",
      ]) {
        expect(source, forbidden).not.toContain(forbidden);
      }
      // Тарифний рівень «Pro» — окремим словом: німецьке «pro Analyse»,
      // «pro Monat», «pro Website» (затверджене пояснення) — прийменник,
      // а не назва тарифу.
      expect(source).not.toMatch(/"pro"|\bpro\b(?! analyse| monat| website)/);
    });
  }
});

describe("компонент рендерить конфігурацію, а не власні числа", () => {
  it("чотири картки в ряд стоять завжди: превʼю → разова → пакет → місячний", () => {
    expect((component.match(/<Card\n/g) ?? []).length).toBe(4);
    expect(component).toContain("lg:grid-cols-4");
    // Превʼю — картка в ряду, а не смуга на всю ширину над платними.
    expect(component).not.toContain('aria-labelledby="pricing-free"');
    expect(component).not.toContain("md:grid-cols-3");
    const order = ["strings.free.heading", "strings.single.kind", "strings.pack.kind", "strings.monthly.kind"]
      .map((marker) => component.indexOf(marker));
    expect(order.every((at, i) => at > -1 && (i === 0 || at > order[i - 1]!))).toBe(true);
    // Превʼю без ціни: безкоштовне за означенням.
    const free = component.slice(component.indexOf("strings.free.heading"), component.indexOf("strings.single.kind"));
    expect(free).not.toContain("price=");
  });

  it("динамічні значення — ціна/валюта, обидві кількості пакета, Presence тарифу", () => {
    // Пакет: два незалежні числа — перевірки й присутність (власник,
    // 2026-09-06). До того їх задавало одне N, і рядок про присутність
    // був правдою випадково.
    expect(lines).toContain("audit_credits");
    expect(lines).toContain("presence_credits");
    // Місячний план: кількість Presence налаштовується окремо.
    expect(lines).toContain("presence_checks_per_month");
    // Стану безліміту й періоду оплати як полів не існує (власник,
    // 2026-09-05).
    for (const source of [component, lines]) {
      expect(source).not.toContain("analyses_unlimited");
      expect(source).not.toContain("analyses_per_month");
      expect(source).not.toContain("interval");
      expect(source).not.toMatch(/presence:\s*\d/);
    }
    // Разова: склад фіксований 1 + 1, числа не читаються з каталогу.
    expect(lines).toContain("SINGLE_ANALYSES = 1");
    expect(lines).toContain("SINGLE_PRESENCE = 1");
  });

  it("відсутнє число ховає лише число: рядок лишається підписом", () => {
    expect(lines).toContain("s.pack.analysesLabel");
    expect(lines).toContain("s.pack.presenceLabel");
    expect(lines).toContain("s.pack.unitPriceLabel");
    expect(lines).toContain("s.monthly.presenceLabel");
    expect(component).toContain("lines={singleLines(locale, strings)}");
    expect(component).toContain("lines={packLines(locale, strings, pack)}");
    expect(component).toContain("lines={monthlyLines(locale, strings, monthly)}");
  });

  it("ціна однієї перевірки обчислюється з налаштованої загальної", () => {
    expect(lines).toContain("perAuditAmount(");
    expect(lines).toContain('replace("{unit_price}"');
  });

  it("поки числа їдуть, сітка позначена зайнятою — знімок половини не існує", () => {
    expect(component).toContain("aria-busy={loading || undefined}");
  });

  it("разова — в анонімну касу, пакет і план — у касу з акаунтом", () => {
    // Разова з 6 вересня 2026 починається з оплати й БЕЗ реєстрації:
    // до того ця кнопка вела на форму превʼю, а спроба провести її
    // через `/checkout` вимагала б входу. Превʼю лишилось окремою
    // карткою й веде на ту саму форму.
    expect(component).toContain("cta={{ href: resultHref, label: strings.free.cta }}");
    expect(component).toContain("cta={{ href: buyHref, label: strings.single.cta }}");
    expect(component).toContain('const buyHref = locale === "en" ? "/buy" : `/buy?lang=${locale}`');
    expect(component).not.toContain('code: single.code }, locale)');
    expect(component).toContain('checkoutHref({ kind: "offer", code: pack.code }, locale)');
    expect(component).toContain('checkoutHref({ kind: "plan", code: monthly.code }, locale)');
    // Зупинки в кабінеті на шляху до оплати немає.
    expect(component).not.toContain("/app/plan?buy=");
    expect(component).not.toContain("/app/plan?subscribe=");
  });

  it("місячна ціна несе одиницю періоду, разова — ні", () => {
    expect(lines).toContain("${s.perMonth}");
    expect(component).toContain("price={priceText(single, pending)}");
  });
});
