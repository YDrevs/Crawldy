/**
 * Рядки чотирьох карток цін — чиста логіка, без React і без мережі.
 *
 * ## Склад пропозиції і комерційні значення — різні речі
 *
 * Рішення власника 2026-09-05: відсутність роздрібної ціни не сміє ховати
 * те, що входить у пропозицію. Відсутнє динамічне значення ховає лише САМЕ
 * значення; підпис про склад лишається. Раніше картка без налаштованої
 * ціни втрачала цілі рядки — «1 повна перевірка», «Actual AI Presence»,
 * «ціна за одну перевірку», — і читалась як пропозиція без вмісту.
 *
 * ## Що фіксоване, а що динамічне
 *
 * - **Разова** — завжди 1 повна перевірка і 1 перевірка Actual AI Presence.
 *   Динамічні лише ціна й валюта.
 * - **Пакет** — набір разових перевірок з ОДНИМ числом N: N повних
 *   перевірок і N перевірок Actual AI Presence. Окремої кількості Presence
 *   для пакета не існує; ціна однієї перевірки = загальна ціна / N і не
 *   зберігається окремо. Динамічні: загальна ціна, валюта, N.
 * - **Місячний план** — необмежені повні перевірки й місячний період за
 *   означенням; окремо налаштовується лише кількість перевірок Actual AI
 *   Presence на місяць. Динамічні: ціна, валюта, кількість Presence.
 *
 * ## Підписи без числа
 *
 * Коли N чи кількості Presence ще немає, рядок рендериться затвердженим
 * підписом без числа («Повні перевірки сайтів», «Actual AI Presence»,
 * «Ціна за одну перевірку», «Actual AI Presence щомісяця»). Підписи
 * необовʼязкові в типі: мова, для якої затвердженого підпису ще немає, не
 * може його вигадати — такий рядок у ній пропускається, і це прогалина
 * перекладу, записана в журналі, а не правило продукту. Щойно
 * конфігурація дає число, ті самі рядки стають числовими формами —
 * без релізу.
 */

import { perAuditAmount, pluralize, type PluralForms } from "./pricing";

/** Рядки віддає сторінка своєї мови: тексти живуть у вмісті, не тут. */
export interface PricingStrings {
  /** Безкоштовне превʼю: заголовок, перелік, одна дія. */
  free: { heading: string; bullets: string[]; cta: string };
  single: {
    kind: string;
    /** «{n} повна перевірка сайту» — рендериться з n = 1 завжди. */
    analyses: PluralForms;
    scores: string;
    issues: string;
    pages: string;
    order: string;
    download: string;
    /** «Actual AI Presence: {n} перевірка» — рендериться з n = 1 завжди. */
    presence: PluralForms;
    /** Дрібний підпис під переліком: «Без реєстрації». Умова доступу до
     *  формату, а не його складова, тому стоїть поза переліком. */
    note?: string;
    cta: string;
  };
  pack: {
    kind: string;
    /** «{n} повних перевірок сайтів» — N із конфігурації. */
    analyses: PluralForms;
    /** Той самий рядок без числа, поки N не налаштовано. */
    analysesLabel?: string;
    /** «Усе, що входить у разову перевірку». */
    includesSingle: string;
    /** «Actual AI Presence: {n} перевірок» — те саме N, що й у перевірок. */
    presence: PluralForms;
    presenceLabel?: string;
    /** «{unit_price} за одну перевірку» — обчислена ціна однієї перевірки. */
    unitPrice: string;
    unitPriceLabel?: string;
    noExpiry: string;
    /** «Керування перевірками та залишком через кабінет» — пункт переліку. */
    manage?: string;
    /** Дрібний підпис під переліком: «Потрібен акаунт Crawldy». */
    note?: string;
    cta: string;
  };
  monthly: {
    /** Нейтральна позначка: «для регулярної роботи», не «найпопулярніший». */
    badge: string;
    kind: string;
    /** «Необмежена кількість повних перевірок» — за означенням, завжди. */
    unlimited: string;
    includesSingle: string;
    /** «Actual AI Presence: {n} перевірок щомісяця» — число з конфігурації. */
    presencePerMonth: PluralForms;
    presenceLabel?: string;
    renews: string;
    /** «Керування перевірками та залишком через кабінет» — пункт переліку. */
    manage?: string;
    /** Дрібний підпис під переліком: «Потрібен акаунт Crawldy». */
    note?: string;
    cta: string;
    /**
     * Застаріле: «{n} перевірок на місяць». Кількість повних перевірок
     * місячного плану не є параметром цін — вони необмежені за означенням
     * (рішення власника 2026-09-05), і рендер цього рядка не читає. Поле
     * лишається необовʼязковим, поки його не прибрано з решти пʼяти мов:
     * українську сторінку виправлено окремо за проханням власника.
     */
    analysesPerMonth?: PluralForms;
  };
  perMonth: string;
  /** Формат є, ціни ще немає. Стан конфігурації, а не відсутність блока. */
  priceOnRequest: string;
  /** Каталог не відповів — єдиний стан, який потребує пояснення текстом. */
  loadFailed: string;
}

/** Ціна з каталогу: сума в мінімальних одиницях, порядок, валюта. */
export interface CatalogPrice {
  display_amount_minor: number | null;
  exponent: number;
  currency: string;
}

/** Пакет: ціна і одне число N. Кількість Presence НЕ читається окремо. */
export interface PackOffer extends CatalogPrice {
  audit_credits: number;
  /**
   * Кількість перевірок присутності в пакеті — окреме число, а не копія
   * `audit_credits` (рішення власника 2026-09-06). Клієнт витрачає ці
   * дві величини окремо, і продавати їх як одну означало б обіцяти те,
   * чого в пакеті може не бути.
   */
  presence_credits: number;
}

/** Місячний план: ціна й кількість Presence на місяць. Безліміт і період — не поля. */
export interface MonthlyPlan {
  presence_checks_per_month: number;
  prices: { amount_minor: number | null; exponent: number; currency: string }[];
}

/** Склад разової перевірки — фіксований, не конфігурація. */
export const SINGLE_ANALYSES = 1;
export const SINGLE_PRESENCE = 1;

export function money(amount: number, exponent: number, currency: string): string {
  return `${(amount / 10 ** exponent).toFixed(exponent)} ${currency}`;
}

/** Головна ціна картки або запасний підпис («…» поки їде, «ціна за запитом» без ціни). */
export function priceText(offer: CatalogPrice | null, pending: string): string {
  return offer === null || offer.display_amount_minor === null
    ? pending
    : money(offer.display_amount_minor, offer.exponent, offer.currency);
}

/** Разова: сім рядків, жодного динамічного значення. */
export function singleLines(locale: string, s: PricingStrings): string[] {
  return [
    pluralize(locale, SINGLE_ANALYSES, s.single.analyses),
    s.single.scores,
    s.single.issues,
    s.single.pages,
    s.single.order,
    s.single.download,
    pluralize(locale, SINGLE_PRESENCE, s.single.presence),
  ];
}

/** N пакета з конфігурації — або нічого. Нуль і менше — не налаштовано. */
export function packCount(pack: PackOffer | null): number | null {
  return pack !== null && pack.audit_credits > 0 ? pack.audit_credits : null;
}

/** Скільки перевірок присутності в пакеті. Нуль — рядка про них немає. */
export function packPresenceCount(pack: PackOffer | null): number | null {
  return pack !== null && pack.presence_credits > 0 ? pack.presence_credits : null;
}

/**
 * Обчислена ціна однієї перевірки — та сама реалізація, що працювала до
 * 5 вересня: загальна ціна / N із точністю валюти, і лише коли N ≥ 2.
 * При N = 1 ціна за одну дорівнює загальній, і рядок лише повторював би
 * її іншими словами.
 */
export function packUnitPrice(pack: PackOffer | null): string | null {
  const n = packCount(pack);
  if (pack === null || n === null || n < 2 || pack.display_amount_minor === null) {
    return null;
  }
  return `${perAuditAmount(pack.display_amount_minor, n, pack.exponent)} ${pack.currency}`;
}

/**
 * Пакет: пʼять значень — кількість, склад, Presence, ціна за одну, строк.
 * Число в рядку є, коли є N; інакше — затверджений підпис без числа.
 */
export function packLines(locale: string, s: PricingStrings, pack: PackOffer | null): string[] {
  const n = packCount(pack);
  // Кількість присутності — своє число з каталогу. Поки воно дорівнювало
  // N, рядок був правдою випадково; тепер він читає те, що задав власник.
  const presence = packPresenceCount(pack);
  const rows: (string | undefined)[] = [
    n !== null ? pluralize(locale, n, s.pack.analyses) : s.pack.analysesLabel,
    s.pack.includesSingle,
    presence !== null ? pluralize(locale, presence, s.pack.presence) : s.pack.presenceLabel,
    s.pack.noExpiry,
    s.pack.manage,
  ];
  return rows.filter((row): row is string => typeof row === "string" && row.length > 0);
}

/**
 * Ціна за одну перевірку — підпис ПІД самою ціною пакета, а не рядок
 * переліку (рішення власника 2026-09-05, як було до 5 вересня): вона
 * пояснює число, що стоїть поруч, і серед переліку того, що входить,
 * читалася як ще одна складова пропозиції.
 *
 * Немає обчисленого значення — лишається затверджений підпис без числа:
 * відсутнє значення ховає значення, а не інформацію.
 */
export function packUnitNote(s: PricingStrings, pack: PackOffer | null): string | null {
  const unit = packUnitPrice(pack);
  if (unit !== null) return s.pack.unitPrice.replace("{unit_price}", unit);
  return s.pack.unitPriceLabel ?? null;
}

/** Кількість Presence на місяць із конфігурації — або нічого. */
export function monthlyPresenceCount(plan: MonthlyPlan | null): number | null {
  return plan !== null && plan.presence_checks_per_month > 0 ? plan.presence_checks_per_month : null;
}

/**
 * Місячний план: чотири рядки — безліміт, склад, Presence, поновлення.
 * Безліміт і поновлення — за означенням; Presence — число або підпис.
 */
export function monthlyLines(locale: string, s: PricingStrings, plan: MonthlyPlan | null): string[] {
  const n = monthlyPresenceCount(plan);
  const rows: (string | undefined)[] = [
    s.monthly.unlimited,
    s.monthly.includesSingle,
    n !== null ? pluralize(locale, n, s.monthly.presencePerMonth) : s.monthly.presenceLabel,
    s.monthly.renews,
    s.monthly.manage,
  ];
  return rows.filter((row): row is string => typeof row === "string" && row.length > 0);
}

/** Місячна ціна з одиницею періоду — або запасний підпис. */
export function monthlyPriceText(plan: MonthlyPlan | null, s: PricingStrings, pending: string): string {
  const price = plan?.prices[0];
  if (!price || price.amount_minor === null) return pending;
  return `${money(price.amount_minor, price.exponent, price.currency)} ${s.perMonth}`;
}
