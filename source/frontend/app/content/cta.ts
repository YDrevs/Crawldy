/**
 * Спільний нижній CTA шістьма мовами — один текст на шість сторінок.
 *
 * Живе поруч із вмістом, а не в компоненті: слова належать сторінці, а
 * не верстці. Шість сторінок беруть той самий обʼєкт, тож розійтися між
 * собою вони не можуть — а це рівно те, що сталося б із шістьма
 * копіями одного абзацу.
 */

import type { Locale } from "../lib/contracts";

export interface CtaStrings {
  title: string;
  text: string;
  cta: string;
  href: string;
}

/**
 * Гостьовий екран існує всіма шістьма мовами сайту, і мову він бере з
 * адреси. Без `?lang=` німець із німецької сторінки потрапляв на
 * англійський результат — це була наша межа, а не межа даних.
 */
function resultHref(locale: Locale): string {
  return locale === "en" ? "/result" : `/result?lang=${locale}`;
}

const COPY: Record<string, Omit<CtaStrings, "href">> = {
  en: {
    title: "Check your site",
    text: "Free: the overall score, coverage and the three main problems. The full analysis and the AI mentions check are in the full report.",
    cta: "Check your site",
  },
  uk: {
    title: "Перевірте свій сайт",
    text: "Безкоштовно побачите загальний бал, покриття та три головні проблеми. Повна аналітика й перевірка згадок у ШІ доступні у повному звіті.",
    cta: "Перевірити сайт",
  },
  de: {
    title: "Prüfen Sie Ihre Website",
    text: "Kostenlos sehen Sie den Gesamtwert, die Abdeckung und die drei wichtigsten Probleme. Die vollständige Analyse und die Prüfung der KI-Erwähnungen sind im vollständigen Bericht enthalten.",
    cta: "Website prüfen",
  },
  es: {
    title: "Comprueba tu sitio",
    text: "Gratis verás la puntuación general, la cobertura y los tres problemas principales. El análisis completo y la comprobación de menciones en la IA están en el informe completo.",
    cta: "Comprobar el sitio",
  },
  fr: {
    title: "Vérifiez votre site",
    text: "Gratuitement, vous verrez le score global, la couverture et les trois problèmes principaux. L'analyse complète et la vérification des mentions dans l'IA figurent dans le rapport complet.",
    cta: "Vérifier le site",
  },
  ru: {
    title: "Проверьте свой сайт",
    text: "Бесплатно увидите общий балл, охват и три главные проблемы. Полная аналитика и проверка упоминаний в ИИ доступны в полном отчёте.",
    cta: "Проверить сайт",
  },
};

export function ctaOf(locale: Locale): CtaStrings {
  const copy = COPY[locale] ?? COPY.en;
  return { ...copy, href: resultHref(locale) };
}
