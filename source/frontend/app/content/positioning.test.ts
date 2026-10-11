/**
 * Позиціонування публічного сайту: що він сміє казати і чого не сміє.
 *
 * Головні твердження:
 * - жодна мова більше не називає Actual AI Presence майбутньою роботою
 *   («не робимо», «збираємось», «у беті») — перевірка завершена, і сайт
 *   каже це;
 * - сторінка «Про нас» не рекламує заплановані аудити: їх немає в
 *   затвердженому першому випуску;
 * - сторінка цін існує обома мовами кабінету і НЕ містить жодної
 *   вписаної ціни: числа приходять із живої комерційної конфігурації;
 * - головна дія шапки веде на безкоштовний аудит, а не на форму входу;
 * - EN і UK каталоги кабінету повні один відносно одного.
 *
 * Тексти скануються як файли навмисно: рендерити серверні компоненти в
 * node-середовищі дорого, а заборонена фраза однаково живе в рядку.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PAGES } from "./registry";
import { missingKeys } from "../lib/i18n";

const CONTENT = __dirname;
const APP = join(__dirname, "..");

function contentFiles(): { name: string; text: string }[] {
  const out: { name: string; text: string }[] = [];
  for (const dir of readdirSync(CONTENT, { withFileTypes: true })) {
    if (!dir.isDirectory()) continue;
    for (const file of readdirSync(join(CONTENT, dir.name))) {
      if (!file.endsWith(".tsx")) continue;
      out.push({
        name: `${dir.name}/${file}`,
        text: readFileSync(join(CONTENT, dir.name, file), "utf-8"),
      });
    }
  }
  return out;
}

describe("присутність більше не «майбутня робота»", () => {
  // Точні фрази, які стояли на сайті до завершення Presence. Поява
  // будь-якої з них знову — відкат позиціонування, а не стиль.
  const FORBIDDEN = [
    "Crawldy does not do it today",
    "we intend to build",
    "We are building it",
    "Crawldy tut das heute nicht",
    "Crawldy no lo hace por ahora",
    "Crawldy ne le fait pas aujourd'hui",
    "Crawldy ne la fait pas aujourd’hui",
    "Crawldy зараз цього не робить",
    "Crawldy сейчас этого не делает",
    "Ми поки цього не робимо",
    "Мы пока этого не делаем",
    "Todavía no lo hacemos",
    "que nous ne proposons pas encore",
    "die wir noch nicht anbieten",
    "que aún no ofrecemos",
    "Coming soon",
    // Presence ВКЛЮЧЕНО в платні покупки — рішення проходу 2026-09-02.
    // Будь-яке «окремо і платно» — відкат позиціонування, всіма мовами.
    "priced separately",
    "separate paid check",
    "separate paid measurement",
    "Separate and paid",
    "Окремо і платно",
    "окрема платна перевірка",
    "отдельная платная проверка",
    "vérification payante distincte",
    "comprobación de pago aparte",
    "eigene kostenpflichtige Prüfung",
    "sold as what it is",
    // Мікрокопія запевнень під кнопками — знята всіма мовами.
    "No card. One site",
    "Без картки. Один сайт",
    "Без карты. Один сайт",
    "Sans carte bancaire. Un site",
    "Sin tarjeta. La primera",
    "Ohne Karte. Eine Website",
    // Механіка прав і повернень — внутрішня мова, не клієнтська.
    "entitlement is returned",
    "pay for measurements, not for attempts",
    // Товар без каси на вітрину не потрапляє — жодною з шести мов.
    "Not on sale yet",
    "Ще не продається",
    "Noch nicht erhältlich",
    "Aún no está a la venta",
    "Pas encore en vente",
    "Пока не продаётся",
    // Службові написи внутрішнього огляду не є клієнтським текстом
    // (журнал правок, екран 07): QA-дані живуть у конфігурації
    // контрольованого середовища, а не в словах на сторінці.
    "QA-зразок",
    "QA sample",
    "Тимчасовий зразок для огляду",
    "не справжня ціна",
    "not a real price",
    "тестові значення",
  ];

  it("заборонені фрази відсутні в усіх мовах вмісту", () => {
    for (const { name, text } of contentFiles()) {
      for (const phrase of FORBIDDEN) {
        expect(text.includes(phrase), `${name}: «${phrase}»`).toBe(false);
      }
    }
  });

  it("кабінет присутності не носить позначки «бета»", () => {
    const page = readFileSync(
      join(APP, "(product)", "app", "presence", "page.tsx"),
      "utf-8",
    );
    expect(page.includes("presence.beta")).toBe(false);
  });
});

describe("про нас не рекламує заплановані аудити", () => {
  const MARKETED = [
    "scheduled audits",
    "заплановані аудити",
    "запланированные аудиты",
    "geplante Prüfungen",
    "audits programmés",
    "auditorías programadas",
  ];

  it("жодна мова «Про нас» не називає їх серед можливостей", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("about/")) continue;
      for (const phrase of MARKETED) {
        expect(text.includes(phrase), `${name}: «${phrase}»`).toBe(false);
      }
    }
  });

  it("тариф у кабінеті не показує межу запланованих аудитів", () => {
    const plan = readFileSync(
      join(APP, "(product)", "app", "plan", "page.tsx"),
      "utf-8",
    );
    expect(/"scheduled_audits",/.test(plan)).toBe(false);
  });
});

describe("сторінка цін", () => {
  const PUBLIC_LOCALES = ["de", "en", "es", "fr", "ru", "uk"] as const;

  it("існує всіма шістьма мовами публічного сайту і стоїть у шапці", () => {
    const pricing = PAGES.pricing;
    expect(pricing).toBeDefined();
    expect(Object.keys(pricing!.locales).sort()).toEqual([...PUBLIC_LOCALES]);
    expect(pricing!.inHeader).toBe(true);
    // Слаги — пошуковий намір мовою читача, і всі різні.
    const slugs = PUBLIC_LOCALES.map(
      (locale) => pricing!.locales[locale]!.slug,
    );
    expect(slugs).toEqual([
      "preise", "pricing", "precios", "tarifs", "tseny", "tsiny",
    ]);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("кожна мова повна: заголовок, опис, H1, підпис меню", () => {
    for (const locale of PUBLIC_LOCALES) {
      const page = PAGES.pricing!.locales[locale]!;
      for (const field of ["title", "h1", "description", "navLabel"] as const) {
        expect(page[field].length, `${locale}.${field}`).toBeGreaterThan(3);
      }
    }
  });

  it("de/es/fr/ru не падають в англійський текст непомітно", () => {
    // Маркери англійської версії: заголовок, назви форматів і написи
    // кнопок. Їхня поява в іншій мові означала б не фолбек, а копіпасту.
    const ENGLISH_MARKERS = [
      "How much does a website analysis cost?",
      "Price on request",
      "Get the report",
      "Buy the pack",
      "Free Preview",
      "Single analysis",
      "Analysis pack",
      "For regular use",
    ];
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("pricing/")) continue;
      if (name.endsWith("en.tsx")) continue;
      for (const marker of ENGLISH_MARKERS) {
        expect(text.includes(marker), `${name}: «${marker}»`).toBe(false);
      }
      // Кожна мова несе ВЛАСНІ рядки живого блока, включно з формами
      // множини: «1 перевірок» очима клієнта — неохайність.
      for (const key of [
        "free: {",
        "single: {",
        "pack: {",
        "monthly: {",
        "badge:",
        "unlimited:",
        "noExpiry:",
        "unitPrice:",
        "includesSingle:",
        "renews:",
        "loadFailed:",
        "priceOnRequest:",
        "one:",
      ]) {
        expect(text.includes(key), `${name}: ${key}`).toBe(true);
      }
    }
  });

  it("канонічні адреси й hreflang охоплюють усі шість мов", async () => {
    const { alternatesOf, canonicalOf } = await import("../lib/pages");
    const alternates = alternatesOf("pricing");
    // Шість мов + x-default на кореневу англійську — так само, як у
    // решти сторінок реєстру.
    expect(Object.keys(alternates).sort()).toEqual(
      [...PUBLIC_LOCALES, "x-default"].sort(),
    );
    expect(alternates["x-default"]).toBe("https://crawldy.ai/pricing");
    expect(canonicalOf("pricing", "en")).toBe("https://crawldy.ai/pricing");
    expect(canonicalOf("pricing", "de")).toBe("https://crawldy.ai/de/preise");
    expect(canonicalOf("pricing", "fr")).toBe("https://crawldy.ai/fr/tarifs");
    expect(canonicalOf("pricing", "es")).toBe(
      "https://crawldy.ai/es/precios",
    );
    expect(canonicalOf("pricing", "ru")).toBe("https://crawldy.ai/ru/tseny");
    expect(canonicalOf("pricing", "uk")).toBe("https://crawldy.ai/uk/tsiny");
  });

  it("кабінет говорить тими самими шістьма мовами, що й сайт", async () => {
    // До 8 вересня 2026 тут стояло `["en", "uk"]`: словники de/es/fr/ru
    // були неповні, і кабінет чесно не пропонував мов, якими не вміє
    // говорити. Тепер бракує нуля ключів — див. `lib/cabinet-locales.test.ts`,
    // який стереже саме повноту, а не цей перелік.
    const { COMPLETE_LOCALES, PUBLIC_SITE_LOCALES } = await import("../lib/i18n");
    expect([...COMPLETE_LOCALES].sort()).toEqual([...PUBLIC_SITE_LOCALES].sort());
  });

  it("не містить жодної вписаної ціни — числа лише з живого API", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("pricing/")) continue;
      // Коментарі не рендеряться — цінові згадки конкурентів у них
      // законні. Сканується лише те, що може дійти до відвідувача.
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Грошові патерни: $9, 9 USD, USD 9, €9, 9 грн…
      const moneyLike =
        /\$\s?\d|\d\s?(USD|EUR|UAH|грн)|(USD|EUR|UAH)\s?\d|€\s?\d/;
      expect(moneyLike.test(rendered), name).toBe(false);
    }
  });

  it("живий блок: чотири рівні картки в ряд, три дороги до каси", () => {
    const cards = readFileSync(
      join(APP, "components", "PricingCards.tsx"),
      "utf-8",
    ).replace(/\r\n/g, "\n");
    expect(cards.includes("strings.loadFailed")).toBe(true);
    // Стану «пропозицій немає» не існує: блоки стоять завжди, і з
    // конфігурації приходять лише числа та умови.
    expect(cards.includes("strings.empty")).toBe(false);
    // Чотири рівні блоки в ряд — композиція `164a74d`, повернута
    // рішенням власника 2026-09-05: перебудова «смуга превʼю на всю
    // ширину + три картки» була пропозицією без затвердження.
    expect(cards.includes("lg:grid-cols-4")).toBe(true);
    expect(cards.includes("sm:grid-cols-2")).toBe(true);
    expect(cards.includes('aria-labelledby="pricing-free"')).toBe(false);
    expect(cards.includes("md:grid-cols-3")).toBe(false);
    // Превʼю — анонімний шлях: перевірка свого сайту без входу.
    expect(cards.includes("cta={{ href: resultHref, label: strings.free.cta }}")).toBe(true);
    // Разова теж анонімна (рішення власника 2026-09-06): спершу оплата,
    // сайт питаємо після неї, на `/buy`, і реєстрації немає ніде.
    expect(cards.includes("cta={{ href: buyHref, label: strings.single.cta }}")).toBe(true);
    expect(cards.includes("/login?lang=${locale}&next=")).toBe(true);
    // Pack і Monthly — просто в касу. Вхід, якщо він потрібен, влаштовує
    // сама сторінка оплати; кабінету на шляху до неї немає (рішення
    // власника 2026-09-06: кнопка вела на «Тариф і використання», і той,
    // хто вже увійшов, бачив зайвий екран замість оплати).
    expect(cards.includes('checkoutHref({ kind: "offer", code: pack.code }, locale)')).toBe(true);
    expect(cards.includes('checkoutHref({ kind: "plan", code: monthly.code }, locale)')).toBe(true);
    expect(cards.includes("/app/plan?buy=")).toBe(false);
    expect(cards.includes("/app/plan?subscribe=")).toBe(false);
    // Мова їде в ОБИДВА запити.
    expect(cards.includes("/v1/offers?lang=${locale}")).toBe(true);
    expect(cards.includes("/v1/plans?lang=${locale}")).toBe(true);
    // Пакет і Місячний план — усе, що входить у разову перевірку:
    // різниця в кількості й ціні, а не у функціях. Рядки будує чиста
    // логіка `lib/pricing-lines.ts`.
    const lines = readFileSync(join(APP, "lib", "pricing-lines.ts"), "utf-8");
    expect(lines.includes("s.pack.includesSingle")).toBe(true);
    expect(lines.includes("s.monthly.includesSingle")).toBe(true);
    expect(cards.includes("features")).toBe(false);
    // Ціна однієї перевірки пакета ОБЧИСЛЮЄТЬСЯ з конфігурації.
    expect(lines.includes("perAuditAmount(")).toBe(true);
    // Monthly — з конфігурації через monthlyToShow, без жодного
    // жорсткого прапорця в коді (lib/pricing.test.ts тримає сам гейт).
    expect(cards.includes("monthlyToShow(")).toBe(true);
    expect(cards.includes("MONTHLY_CHECKOUT_READY")).toBe(false);
    expect(cards.includes("notAvailableYet")).toBe(false);
  });

  it("структура сторінки: H1 і одне пояснення, живий блок, БЕЗ надзаголовка й FAQ", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("pricing/")) continue;
      expect(text.includes("PricingCards"), `${name}: PricingCards`).toBe(true);
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Під заголовком — рівно одне затверджене пояснення (власник,
      // 2026-09-05), без надзаголовка й без другої підводки.
      expect(rendered.includes("lead="), `${name}: пояснення`).toBe(true);
      expect((rendered.match(/lead=/g) ?? []).length, `${name}: одне пояснення`).toBe(1);
      expect(rendered.includes("eyebrow="), `${name}: надзаголовок`).toBe(false);
      // Пояснювальних карток поруч із живими немає.
      expect(text.includes("CardGrid"), `${name}: CardGrid`).toBe(false);
      // FAQ знято разом із розміткою FAQPage: невидимої структурованої
      // розмітки, що не відповідає видимому вмісту, не існує.
      expect(rendered.includes("question:"), `${name}: FAQ`).toBe(false);
      expect(rendered.includes("JsonLd"), `${name}: FAQPage-розмітка`).toBe(false);
      expect(rendered.includes("FAQPage"), `${name}: FAQPage`).toBe(false);
    }
  });

  it("сітка не щезає: чотири картки рендеряться безумовно", () => {
    const cards = readFileSync(
      join(APP, "components", "PricingCards.tsx"),
      "utf-8",
    ).replace(/\r\n/g, "\n");
    // Рішення власника 2026-09-03 діє далі: формати оплати — структура
    // продукту, і від наявності рядка в базі вона не залежить.
    const rendered = cards.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(/\{monthly \? \(/.test(rendered)).toBe(false);
    expect(/sortedOffers\.map/.test(rendered)).toBe(false);
    expect(/\{loading \? \(/.test(rendered)).toBe(false);
    expect((rendered.match(/<Card\n/g) ?? []).length).toBe(4);
    // Ціна за одну перевірку — підпис під ціною, а не рядок переліку.
    expect(rendered.includes("packUnitNote(strings, pack)")).toBe(true);
    // Без ціни картка каже «ціна за запитом», а не зникає.
    expect(rendered.includes("strings.priceOnRequest")).toBe(true);
    // Назва формату — зі сторінки; налаштована назва пропозиції не
    // дублює перший рядок переліку.
    expect(rendered.includes("display_name")).toBe(false);
  });

  it("картка превʼю: погоджений заголовок і перелік, без ціни й обіцянок", () => {
    const expected: Record<string, string> = {
      en: "Free Preview",
      uk: "Безкоштовне прев’ю",
      de: "Kostenlose Vorschau",
      es: "Vista previa gratuita",
      fr: "Aperçu gratuit",
      ru: "Бесплатный предварительный результат",
    };
    for (const [locale, heading] of Object.entries(expected)) {
      const text = readFileSync(join(CONTENT, "pricing", `${locale}.tsx`), "utf-8");
      expect(text.includes(`heading: ${JSON.stringify(heading)}`), `${locale}: заголовок`).toBe(true);
      // Ціни у превʼю немає — ані «Безкоштовно», ані нуля: воно безкоштовне
      // за означенням, і окремий рядок ціни лише повторював би заголовок.
      expect(/price:\s*"/.test(text), `${locale}: ціна у превʼю`).toBe(false);
      expect(/kindFree/.test(text), `${locale}: старий підпис`).toBe(false);
    }
  });

  it("ієрархія картки (164a74d): заголовок, перелік, ціна по центру, кнопка внизу", () => {
    const cards = readFileSync(
      join(APP, "components", "PricingCards.tsx"),
      "utf-8",
    ).replace(/\r\n/g, "\n");
    const rendered = cards.replace(/\/\*[\s\S]*?\*\//g, "");
    // Заголовок → перелік → ціна між переліком і кнопкою, по центру, а
    // під нею — ціна за одну перевірку (як у 164a74d).
    const heading = rendered.indexOf("{heading}</h2>");
    const list = rendered.indexOf("{lines.map(");
    const price = rendered.indexOf("{price}");
    const note = rendered.indexOf("{priceNote}");
    expect(heading).toBeGreaterThan(-1);
    expect(list).toBeGreaterThan(heading);
    expect(price).toBeGreaterThan(list);
    expect(note).toBeGreaterThan(price);
    expect(rendered.includes('<div className="text-center">')).toBe(true);
    expect(rendered.includes("break-words")).toBe(true);
    // Кнопка притиснута до низу, на всю ширину картки.
    expect(rendered.includes("flex flex-1 flex-col justify-end")).toBe(true);
    expect(rendered.includes("block w-full rounded-lg bg-brand")).toBe(true);
  });

  it("позначка «для регулярної роботи» не виглядає кнопкою", () => {
    const cards = readFileSync(
      join(APP, "components", "PricingCards.tsx"),
      "utf-8",
    ).replace(/\r\n/g, "\n");
    const rendered = cards.replace(/\/\*[\s\S]*?\*\//g, "");
    // Заливка бренду — мова кнопок. Позначка носить світлий акцентний
    // чип із рамкою: помітно, але без натяку на клік.
    expect(rendered.includes("border border-accent bg-accent-soft")).toBe(true);
    expect(/badge[\s\S]{0,200}bg-brand\b/.test(rendered)).toBe(false);
  });

  it("гасло знято, заголовок — точне питання власника, під ним затверджене пояснення", () => {
    const headings: Record<string, string> = {
      en: "How much does a website analysis cost?",
      uk: "Скільки коштує перевірка сайту",
      de: "Was kostet eine Website-Analyse?",
      es: "¿Cuánto cuesta analizar un sitio web?",
      fr: "Combien coûte l’analyse d’un site ?",
      ru: "Сколько стоит проверка сайта",
    };
    for (const [locale, heading] of Object.entries(headings)) {
      const text = readFileSync(join(CONTENT, "pricing", `${locale}.tsx`), "utf-8");
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      expect(rendered.includes(`<Hero title=${JSON.stringify(heading)} compact lead=`), `${locale}: H1`).toBe(true);
      expect(text.includes(`  h1: ${JSON.stringify(heading)},`), `${locale}: h1`).toBe(true);
    }
    // Саме гасло зникло з видимого тексту всіх шести мов.
    const SLOGANS = [
      "One product. Three ways to pay.",
      "Один продукт. Три варіанти оплати.",
      "Ein Produkt. Drei Zahlungsoptionen.",
      "Un producto. Tres formas de pago.",
      "Un produit. Trois modes de paiement.",
      "Один продукт. Три варианта оплаты.",
      "The only difference",
      "Відрізняється лише",
    ];
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("pricing/")) continue;
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      for (const slogan of SLOGANS) {
        // Метазаголовок сторінки (<title> для видачі) — інша поверхня;
        // сканується лише те, що бачить відвідувач на сторінці.
        const body = rendered.split("export const")[0];
        expect(body.includes(slogan), `${name}: «${slogan}»`).toBe(false);
      }
    }
  });

  it("український CTA разової — «Отримати звіт», не «Купити перевірку»", () => {
    const uk = readFileSync(join(CONTENT, "pricing", "uk.tsx"), "utf-8");
    expect(uk.includes('cta: "Отримати звіт"')).toBe(true);
    expect(uk.includes("Купити перевірку")).toBe(false);
    expect(uk.includes("Увійти й купити")).toBe(false);
  });
});

describe("кабінет: компактний підсумок і чесний безкоштовний стан", () => {
  it("тариф і використання — один контейнер, без панелей-пояснень", () => {
    const plan = readFileSync(
      join(APP, "(product)", "app", "plan", "page.tsx"),
      "utf-8",
    );
    expect(plan.includes('data-testid="usage-summary"')).toBe(true);
    // Пояснювальні абзаци механіки обліку зникли разом зі своїми
    // ключами; «не згоряє» — коротка позначка біля числа.
    for (const gone of [
      "plan.oneOffWhat",
      "plan.oneOffWhen",
      "plan.included",
      "plan.presenceRemaining",
    ]) {
      expect(plan.includes(gone), gone).toBe(false);
    }
    // Підпису «Не згоряє» біля числа немає й далі. Речення про те, що
    // куплене не згорає, стоїть під таблицею й лише коли куплене є:
    // §7.1 просить сказати це там, де показані баланси.
    expect(plan.includes('t("plan.noExpiry")')).toBe(true);
    expect(
      plan.includes("usage.presence_credits_available > 0"),
      "речення про безстроковість — лише при куплених одиницях",
    ).toBe(true);
    // Безкоштовний стан — «активного тарифу немає», а не тариф із нулями.
    expect(plan.includes('t("plan.none")')).toBe(true);
    // Підписка — справжня каса. Наміру з адреси тут більше немає: до
    // каси ведуть кнопки цієї ж сторінки, а зі сторінки цін — `/checkout`.
    expect(plan.includes("openPlanCheckout(")).toBe(true);
    expect(plan.includes('params.get("subscribe")')).toBe(false);
    expect(plan.includes('params.get("buy")')).toBe(false);
  });

  it("чинному підписнику Monthly у «Докупити» не пропонується", () => {
    const plan = readFileSync(
      join(APP, "(product)", "app", "plan", "page.tsx"),
      "utf-8",
    );
    // Друга каса поруч із незавершеною підпискою — запрошення до
    // подвійного наділу; картка ховається цілком, без вимкнених кнопок.
    expect(plan.includes("hasSubscription ? null : monthlyToShow(")).toBe(true);
    // Single і Pack лишаються: вони додають окремо куплені перевірки,
    // тож перелік пропозицій НЕ гейтиться підпискою.
    expect(plan.includes("hasSubscription ? [] : ")).toBe(false);
    expect(/\(offers \?\? \[\]\)\.map\(/.test(plan)).toBe(true);
  });

  it("панель огляду без вигаданого «1 of 1» на безкоштовному стані", () => {
    const dash = readFileSync(
      join(APP, "(product)", "app", "page.tsx"),
      "utf-8",
    );
    expect(dash.includes('t("plan.none")')).toBe(true);
  });
});

describe("мова не губиться на переходах", () => {
  it("логотип сторінки входу веде на головну мовою відвідувача", () => {
    const login = readFileSync(
      join(APP, "(product)", "login", "page.tsx"),
      "utf-8",
    );
    // Підтверджений баг: зашитий «/» перемикав українця на англійську.
    expect(login.includes('href="/"')).toBe(false);
    expect(login.includes("publicHomeHref(")).toBe(true);
    // Мова САЙТУ (шість) окремо від мови форми (en/uk): німець бачить
    // англійську форму, але повертається на /de.
    expect(login.includes("asSiteLocale(")).toBe(true);
    // Обрана мова їде в порожній профіль після входу/реєстрації.
    expect(login.includes("saveMyLocale(")).toBe(true);
  });

  it("гостьова пропозиція акаунта несе мову на форму входу", () => {
    const guest = readFileSync(
      join(APP, "components", "GuestReport.tsx"),
      "utf-8",
    );
    expect(guest.includes("/login?lang=")).toBe(true);
    expect(guest.includes('href="/login"')).toBe(false);
  });

  it("вихід із кабінету відкриває вхід тією самою мовою", () => {
    const layout = readFileSync(
      join(APP, "(product)", "app", "layout.tsx"),
      "utf-8",
    );
    // Мова САЙТУ, а не кабінету: кабінет говорить двома мовами, форма
    // входу — шістьма, і людина з /de має побачити німецьку.
    expect(layout.includes("/login?lang=${site}")).toBe(true);
    expect(layout.includes("useSiteLocale(")).toBe(true);
  });

  it("шапка публічного сайту передає мову на вхід — обидва входи", () => {
    const header = readFileSync(
      join(APP, "components", "PublicHeader.tsx"),
      "utf-8",
    );
    // Обидва входи — широкий екран і меню вузького — тепер малює той
    // самий компонент облікового запису, тож посилання на вхід у ньому
    // одне. Це і є правило: два місця з тією самою адресою розійшлися б.
    const account = readFileSync(
      join(APP, "components", "PublicAccount.tsx"),
      "utf-8",
    );
    expect((header.match(/<PublicAccount/g) ?? []).length).toBe(2);
    expect(account.includes("/login?lang=${locale}")).toBe(true);
    expect(account.includes('href="/login"')).toBe(false);
    expect(header.includes('href="/login"')).toBe(false);
  });

  it("гостьовий результат тримає мову крізь запуск і повернення з каси", () => {
    const result = readFileSync(
      join(APP, "(product)", "result", "page.tsx"),
      "utf-8",
    );
    // Перехід на ?audit= несе мову в адресі…
    expect(result.includes("&lang=${locale}")).toBe(true);
    // …а повернення з каси Paddle (без параметра) відновлює її зі
    // сховища сесії.
    expect(result.includes("recallLocale()")).toBe(true);
    expect(result.includes("rememberLocale(")).toBe(true);
  });

  it("сторінка каси Paddle згадує мову гостя", () => {
    const checkout = readFileSync(
      join(APP, "(product)", "checkout", "page.tsx"),
      "utf-8",
    );
    expect(checkout.includes("recallLocale()")).toBe(true);
    expect(checkout.includes('useState<Locale>("en")')).toBe(true);
  });
});

describe("гостьове превʼю без запевнень", () => {
  it("пейвол і вхід превʼю не повторюють «без картки/акаунта/підписки»", async () => {
    const { translate } = await import("../lib/i18n");
    for (const locale of ["en", "uk"] as const) {
      for (const key of ["free.paywallLead", "free.invalidUrl"]) {
        const text = translate(locale, key).toLowerCase();
        for (const phrase of [
          "no subscription",
          "no account",
          "no card",
          "без підписки",
          "без акаунта",
          "без картки",
        ]) {
          expect(text.includes(phrase), `${locale}:${key}: «${phrase}»`).toBe(
            false,
          );
        }
      }
    }
  });
});

describe("шапка й футер за погодженою архітектурою", () => {
  it("шапка повторює колонку «Продукт»: Що перевіряємо → Методологія → Ціни", () => {
    const inHeader = Object.values(PAGES)
      .filter((page) => page.inHeader)
      .map((page) => page.key)
      .sort();
    expect(inHeader).toEqual(["methodology", "pricing", "website_audit"]);
    expect(PAGES.website_audit!.navOrder).toBe(1);
    expect(PAGES.methodology!.navOrder).toBe(2);
    expect(PAGES.pricing!.navOrder).toBe(3);
    expect(PAGES.methodology!.group).toBe("product");
  });

  it("пункт перейменовано: «Що перевіряємо» всіма шістьма мовами", () => {
    const labels = PAGES.website_audit!.locales;
    expect(labels.uk!.navLabel).toBe("Що перевіряємо");
    expect(labels.en!.navLabel).toBe("What we check");
    expect(labels.de!.navLabel).toBe("Was wir prüfen");
    expect(labels.es!.navLabel).toBe("Qué comprobamos");
    expect(labels.fr!.navLabel).toBe("Ce que nous vérifions");
    expect(labels.ru!.navLabel).toBe("Что проверяем");
  });

  it("матеріали — окрема колонка: пояснення частин однієї перевірки", () => {
    for (const key of [
      "ai_visibility",
      "seo_audit",
      "technical_seo_audit",
    ] as const) {
      expect(PAGES[key]!.group, key).toBe("materials");
      expect(PAGES[key]!.inHeader ?? false, key).toBe(false);
    }
    expect(PAGES.ai_visibility!.navOrder).toBe(1);
    expect(PAGES.seo_audit!.navOrder).toBe(2);
    expect(PAGES.technical_seo_audit!.navOrder).toBe(3);
  });

  it("футер: три колонки, без «Розробникам», без мертвого FAQ", () => {
    const shell = readFileSync(
      join(APP, "components", "PublicShell.tsx"),
      "utf-8",
    );
    expect(shell.includes('navOf("product", locale)')).toBe(true);
    expect(shell.includes('navOf("materials", locale)')).toBe(true);
    expect(shell.includes('navOf("company", locale)')).toBe(true);
    // Колонки розробників у футері немає (рішення власника).
    expect(shell.includes('navOf("developers"')).toBe(false);
    // FAQ-сторінки ще не існує — активного посилання на неї теж.
    expect(shell.includes("FAQ</")).toBe(false);
    expect(shell.includes('"/faq"')).toBe(false);
  });

  it("речення футера — погоджене формулювання власника", () => {
    const shell = readFileSync(
      join(APP, "components", "PublicShell.tsx"),
      "utf-8",
    );
    expect(
      shell.includes(
        "Crawldy показує, що заважає вашому сайту бути видимим у пошуку та ШІ, і що варто виправити насамперед.",
      ),
    ).toBe(true);
    expect(shell.includes("Crawldy перевіряє сайт так, як його читають")).toBe(
      false,
    );
  });
});

describe("шапка без другого CTA після прокручування", () => {
  it("кнопка «Перевірити сайт» при скролі прибрана, вхід лишився", () => {
    const header = readFileSync(
      join(APP, "components", "PublicHeader.tsx"),
      "utf-8",
    );
    // Зайвий повторний CTA (рішення власника): ні стану прокручування,
    // ні кнопки. Головна дія живе біля поля адреси на сторінці.
    expect(header.includes("scrolled")).toBe(false);
    expect(header.includes("HERO_PASSED")).toBe(false);
    expect(header.includes("ctaHref")).toBe(false);
    // Спокійне посилання на вхід — на місці, з мовою. Живе воно в
    // компоненті облікового запису: той, хто вже увійшов, бачить на
    // тому самому місці своє імʼя.
    const account = readFileSync(
      join(APP, "components", "PublicAccount.tsx"),
      "utf-8",
    );
    expect(header.includes("<PublicAccount")).toBe(true);
    expect(account.includes("/login?lang=${locale}")).toBe(true);
    const shell = readFileSync(
      join(APP, "components", "PublicShell.tsx"),
      "utf-8",
    );
    expect(shell.includes("ctaHref")).toBe(false);
  });

  it("справжня дія запуску перевірки лишилась у вмісті сторінок", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("home/")) continue;
      expect(text.includes("HeroAuditForm"), name).toBe(true);
    }
  });
});

describe("головна за журналом правок (екран 01)", () => {
  it("усі шість мов: питання і форма, без надзаголовка й пояснення", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("home/")) continue;
      expect(text.includes("HeroAuditForm"), name).toBe(true);
      // Валідація адреси контрольована застосунком і локалізована.
      expect(text.includes("invalid="), name).toBe(true);
      // Коментарі законно згадують зняте — сканується лише те, що може
      // дійти до відвідувача.
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Надзаголовка на першому екрані немає — питання головне.
      expect(rendered.includes("eyebrow="), `${name}: eyebrow`).toBe(false);
      // Внутрішня термінологія і умови оплати з головної зняті.
      expect(rendered.includes("Actual AI Presence"), name).toBe(false);
    }
  });

  it("«Один продукт. Три відповіді.» замінено одним реченням", () => {
    const OLD_HEADINGS = [
      "Один продукт. Три відповіді.",
      "One product. Three answers.",
      "Ein Produkt. Drei Antworten.",
      "Un producto. Tres respuestas.",
      "Un produit. Trois réponses.",
      "Один продукт. Три ответа.",
    ];
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("home/")) continue;
      for (const heading of OLD_HEADINGS) {
        expect(text.includes(heading), `${name}: «${heading}»`).toBe(false);
      }
    }
  });

  it("українська головна — точні формулювання власника", () => {
    const uk = readFileSync(join(CONTENT, "home", "uk.tsx"), "utf-8");
    for (const approved of [
      "Чи справді пошук і ШІ бачать ваш сайт?",
      "Одна перевірка сайту відповідає на три ключові питання про вашу видимість у пошуку та ШІ.",
      "Чи знаходить вас пошук?",
      "Чи розуміє ШІ ваш сайт?",
      "Чи згадує ШІ ваш бренд?",
      "Усі складові перевірки",
      "Прозора оцінка сайту",
      "Ви бачите, які сторінки перевірено, що вдалося виміряти та на чому ґрунтується підсумковий бал.",
      "Як влаштоване вимірювання",
    ]) {
      expect(uk.includes(approved), `«${approved}»`).toBe(true);
    }
    for (const removed of [
      "Аудит видимості в пошуку та ШІ",
      "Введіть адресу й отримайте безкоштовний попередній результат",
      "Та сама перевірка міряє й швидкість",
      "Бал, який можна перевірити",
      "Входить у платні перевірки",
    ]) {
      expect(uk.includes(removed), `«${removed}»`).toBe(false);
    }
  });

  it("форма веде в канонічний гостьовий шлях і нормалізує адресу", () => {
    const form = readFileSync(
      join(APP, "components", "HeroAuditForm.tsx"),
      "utf-8",
    );
    expect(form.includes("/result?")).toBe(true);
    // Голий домен — валідний вхід; браузерні підказки вимкнено, бо вони
    // приходять мовою браузера, а не мовою сторінки.
    expect(form.includes("normalizeSiteUrl(")).toBe(true);
    expect(form.includes("noValidate")).toBe(true);
    expect(form.includes('type="url"')).toBe(false);
    const result = readFileSync(
      join(APP, "(product)", "result", "page.tsx"),
      "utf-8",
    );
    expect(result.includes('params.get("url")')).toBe(true);
    expect(result.includes("normalizeSiteUrl(")).toBe(true);
    expect(result.includes("noValidate")).toBe(true);
    // Заголовок і пояснення екрана запуску зняті, не замінені іншими.
    expect(result.includes("free.startTitle")).toBe(false);
    expect(result.includes("free.startLead")).toBe(false);
  });
});

describe("що перевіряємо — за журналом правок (екран 02)", () => {
  it("усі шість мов: без запуску, прикладу, посилань і «Читайте також»", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("website-audit/")) continue;
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Шість карток — звичайний неінтерактивний текстовий блок; CTA,
      // приклад звіту і перехресні посилання з цієї сторінки зняті.
      // Літеральна адреса у вмісті — саме те, що знято; `href={cta.href}`
      // затвердженого нижнього CTA під це не підпадає.
      expect(/href[:=]\s*"/.test(rendered), `${name}: посилання у вмісті`).toBe(
        false,
      );
      expect(rendered.includes("ScorePreview"), `${name}: ScorePreview`).toBe(
        false,
      );
      expect(rendered.includes("primary="), `${name}: primary CTA`).toBe(false);
      expect(rendered.includes("Related"), `${name}: Related`).toBe(false);
    }
  });

  it("українська — точні формулювання власника", () => {
    const uk = readFileSync(join(CONTENT, "website-audit", "uk.tsx"), "utf-8");
    for (const approved of [
      "Шість напрямів перевірки",
      "Crawldy перевіряє видимість сайту в пошуку та ШІ, його швидкість, базовий захист і доступність.",
      "Як формується оцінка сайту",
      "Покриття видно одразу",
      "Невиміряне не знижує оцінку",
      "Якщо даних недостатньо, бала немає",
      "Кожен висновок можна перевірити",
      "Що виправляти насамперед",
      "Crawldy впорядковує проблеми за пріоритетом, враховуючи їхню серйозність, очікуваний ефект, складність виправлення та важливість сторінки.",
    ]) {
      expect(uk.includes(approved), `«${approved}»`).toBe(true);
    }
    // Коментарі файла законно ЗГАДУЮТЬ зняті блоки — сканується лише
    // те, що може дійти до відвідувача.
    const rendered = uk.replace(/\/\*[\s\S]*?\*\//g, "");
    for (const removed of [
      "Шість напрямів, і важать вони по-різному",
      "Технічні подробиці з боку пошуку",
      "Упорядковано за тим, що робити першим",
      "Читайте також",
    ]) {
      expect(rendered.includes(removed), `«${removed}»`).toBe(false);
    }
  });
});

describe("методологія — за журналом правок (екран 06)", () => {
  it("усі шість мов: послідовність і точні правила, без CTA і посилань", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("methodology/")) continue;
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      expect(rendered.includes("ScoringRules"), `${name}: ScoringRules`).toBe(
        true,
      );
      // Без повторного переліку шести напрямів, без CTA, без
      // перехресних посилань і без «Читайте також».
      expect(rendered.includes("CardGrid"), `${name}: CardGrid`).toBe(false);
      expect(rendered.includes("Related"), `${name}: Related`).toBe(false);
      expect(rendered.includes("More"), `${name}: More`).toBe(false);
      expect(rendered.includes("primary="), `${name}: primary CTA`).toBe(false);
      expect(/href[:=]\s*"/.test(rendered), `${name}: посилання у вмісті`).toBe(
        false,
      );
    }
  });

  it("українська — точна погоджена послідовність", () => {
    const uk = readFileSync(join(CONTENT, "methodology", "uk.tsx"), "utf-8");
    for (const approved of [
      "Як Crawldy формує результати перевірки",
      "Crawldy формує висновки лише на основі того, що вдалося фактично перевірити. Для кожної виявленої проблеми у звіті показуються докази, контекст і логіка визначення її пріоритету.",
      "Спочатку визначаємо покриття",
      "Враховуємо лише перевірені дані",
      "Підтверджуємо кожну проблему",
      "Формуємо оцінку",
      "Визначаємо, що виправляти першим",
      "Точні правила розрахунку",
    ]) {
      expect(uk.includes(approved), `«${approved}»`).toBe(true);
    }
    // Коментарі файла законно ЗГАДУЮТЬ зняті блоки — сканується лише
    // те, що може дійти до відвідувача.
    const rendered = uk.replace(/\/\*[\s\S]*?\*\//g, "");
    for (const removed of [
      "Що входить в аудит",
      "Читайте також",
      "думка з версткою",
      "дешева косметика",
      "тринадцять тверджень",
      "гіперболічна",
    ]) {
      expect(rendered.includes(removed), `«${removed}»`).toBe(false);
    }
  });

  it("числа таблиці — зі знімка реального скорингу, і він повний", async () => {
    const facts = (await import("./methodology/scoring-facts.json")).default as {
      weights: Record<string, number>;
      severity_multipliers: Record<string, number>;
      repetition: Record<string, number>;
      coverage: Record<string, number>;
    };
    // Повнота і несуперечність знімка; збіг із бекендом тримає
    // backend/tests/test_methodology_page_facts.py.
    expect(Object.keys(facts.weights)).toHaveLength(6);
    const total = Object.values(facts.weights).reduce((a, b) => a + b, 0);
    expect(Math.abs(total - 1)).toBeLessThan(1e-9);
    expect(Object.keys(facts.severity_multipliers)).toHaveLength(5);
    expect(facts.coverage.min_words_for_a_site).toBeGreaterThan(0);
    expect(facts.repetition.max_penalty_per_key).toBeGreaterThan(1);
    expect(facts.repetition.max_penalty_share_of_half).toBeLessThanOrEqual(1);
  });
});

describe("кабінет живий, без макетних даних і розкладів", () => {
  const CABINET = join(APP, "(product)", "app");

  function cabinetFiles(dir = CABINET): { name: string; text: string }[] {
    const out: { name: string; text: string }[] = [];
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        out.push(...cabinetFiles(full));
        continue;
      }
      if (!entry.name.endsWith(".tsx")) continue;
      out.push({ name: full.slice(APP.length), text: readFileSync(full, "utf-8") });
    }
    return out;
  }

  it("жодного імпорту макетів на екранах кабінету", () => {
    for (const { name, text } of cabinetFiles()) {
      expect(text.includes("lib/mock"), `${name}: lib/mock`).toBe(false);
      expect(/\bMOCK_/.test(text), `${name}: MOCK_`).toBe(false);
    }
    // Куплений звіт теж живий: /r/{token}?format=web, без фікстур.
    const durable = readFileSync(
      join(APP, "(product)", "report", "[token]", "page.tsx"),
      "utf-8",
    );
    expect(durable.includes("mock")).toBe(false);
    expect(durable.includes("readSharedReport")).toBe(true);
  });

  it("клієнтських елементів розкладу немає", () => {
    for (const { name, text } of cabinetFiles()) {
      expect(/schedule/i.test(text), `${name}: schedule`).toBe(false);
    }
  });

  it("меню кабінету не веде на неіснуючі налаштування", () => {
    const shell = readFileSync(join(APP, "components", "AppShell.tsx"), "utf-8");
    expect(shell.includes("/app/settings")).toBe(false);
  });
});

describe("матеріали: три сторінки, кожна про своє (екрани 08–10)", () => {
  const MATERIALS = ["ai-visibility/", "seo-audit/", "technical-seo-audit/"];
  const PUBLIC_LOCALES = ["de", "en", "es", "fr", "ru", "uk"] as const;

  function materialFiles() {
    return contentFiles().filter((file) =>
      MATERIALS.some((prefix) => file.name.startsWith(prefix)),
    );
  }

  it("усі три сторінки існують шістьма мовами", () => {
    for (const key of ["ai_visibility", "seo_audit", "technical_seo_audit"] as const) {
      expect(Object.keys(PAGES[key]!.locales).sort(), key).toEqual([
        ...PUBLIC_LOCALES,
      ]);
    }
    expect(materialFiles()).toHaveLength(18);
  });

  it("без «Читайте також», перехресних карток і верхніх CTA", () => {
    for (const { name, text } of materialFiles()) {
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Навігація між матеріалами живе у футері — на сторінках її немає.
      expect(rendered.includes("Related"), `${name}: Related`).toBe(false);
      expect(rendered.includes("<More"), `${name}: More`).toBe(false);
      expect(rendered.includes("primary="), `${name}: верхній CTA`).toBe(false);
      expect(rendered.includes("secondary="), `${name}: другий CTA`).toBe(false);
      // Жодного перехресного посилання між трьома сторінками.
      expect(/href:\s*"/.test(rendered), `${name}: href у вмісті`).toBe(false);
    }
  });

  it("рівно один CTA на сторінку — спільний, унизу", () => {
    for (const { name, text } of materialFiles()) {
      expect(text.split("<SiteCta").length - 1, `${name}: SiteCta`).toBe(1);
      expect(text.includes("ctaOf("), name).toBe(true);
    }
  });

  it("шість напрямів і методологія не повторюються на матеріалах", () => {
    for (const { name, text } of materialFiles()) {
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Перелік усіх шести напрямів належить сторінці «Що перевіряємо».
      expect(rendered.includes("CardGrid"), `${name}: CardGrid`).toBe(false);
      // Пояснення ваг і півшкали — сторінці «Методологія».
      expect(rendered.includes("ScoringRules"), `${name}: ScoringRules`).toBe(false);
      for (const forbidden of [
        "півшкал", "half-scale", "Halbskala", "media escala",
        "demi-échelle", "полушкал",
      ]) {
        expect(rendered.includes(forbidden), `${name}: «${forbidden}»`).toBe(false);
      }
    }
  });

  it("SEO-аудит більше не пояснює відрендерену версію — це технічна сторінка", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("seo-audit/")) continue;
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      for (const forbidden of ["JavaScript", "рендер", "rendered", "gerendert"]) {
        expect(rendered.includes(forbidden), `${name}: «${forbidden}»`).toBe(false);
      }
    }
    // …а на технічній вона є, і саме там.
    const tech = readFileSync(
      join(CONTENT, "technical-seo-audit", "uk.tsx"),
      "utf-8",
    );
    expect(tech.includes("Відповідь сервера проти відрендереного DOM")).toBe(true);
  });

  it("українські формулювання — точно ті, що погоджено", () => {
    const ai = readFileSync(join(CONTENT, "ai-visibility", "uk.tsx"), "utf-8");
    for (const approved of [
      "Чи бачать і згадують вас ШІ-системи?",
      "Доступність для ШІ",
      "Розуміння вашого бізнесу",
      "Придатність бути джерелом",
      "Фактична присутність у відповідях",
      // «Це результат конкретного запуску, а не постійний рейтинг.» —
      // прибрано 2026-09-08 разом із тілом блока: власник замінив його
      // на перелік моделей і два абзаци про те, що моделі змінюються, а
      // результат стосується показаних. Заголовок блока лишився той самий.
      "Що ви побачите у звіті",
    ]) {
      expect(ai.includes(approved), `ai: «${approved}»`).toBe(true);
    }

    const seo = readFileSync(join(CONTENT, "seo-audit", "uk.tsx"), "utf-8");
    // Затверджена структура E2 (2026-09-05): три пронумеровані етапи й
    // блок про звіт; «Чи можуть сторінки потрапити до індексу» став
    // питанням про сигнали, бо фактичної індексації ми не бачимо.
    for (const approved of [
      "Чи можуть пошукові системи знайти й зрозуміти ваш сайт?",
      "1. Чи може пошук дістатися до сторінок",
      "2. Чи є сигнали, що заважають індексації",
      "3. Чи зрозуміло, про що сторінка",
      "Чи проіндексована сторінка фактично, Crawldy не визначає",
      "Що дає звіт",
    ]) {
      expect(seo.includes(approved), `seo: «${approved}»`).toBe(true);
    }

    const tech = readFileSync(
      join(CONTENT, "technical-seo-audit", "uk.tsx"),
      "utf-8",
    );
    for (const approved of [
      "Що технічно заважає сайту працювати правильно",
      "1. Швидкість і стабільність",
      "2. HTTPS, редиректи й базовий захист",
      "3. Відповідь сервера проти відрендереного DOM",
      "4. Форми й обробка помилок",
      "5. Доступність і зручність",
      "Докази й рекомендації у звіті",
      "Це автоматична технічна перевірка, а не тест на проникнення, пошук вразливостей чи сертифікація доступності.",
    ]) {
      expect(tech.includes(approved), `tech: «${approved}»`).toBe(true);
    }
  });

  it("технічна сторінка обіцяє рівно видимі ознаки захисту форм", () => {
    const tech = readFileSync(
      join(CONTENT, "technical-seo-audit", "uk.tsx"),
      "utf-8",
    );
    // Точне погоджене формулювання — не ширше за реалізацію детектора.
    expect(
      tech.includes("чи видно в них ознаки захисту від автоматичного спаму"),
    ).toBe(true);
    // Механіка GET/POST прибрана з публічної сторінки (§7.2): це
    // пояснення детектора, а не те, що клієнт прийшов сюди читати.
    // Сам детектор і його ціна не змінились.
    expect(tech.includes("методом GET")).toBe(false);
    expect(tech.includes("небезпечн")).toBe(false);
    // Жодного натяку на перевірку невидимих серверних механізмів.
    for (const overclaim of [
      "перевіряємо серверний захист",
      "пентест форм",
      "гарантуємо захист",
    ]) {
      expect(tech.includes(overclaim), overclaim).toBe(false);
    }
  });
});

describe("спільний нижній CTA (журнал, пункт 8)", () => {
  const WITH_CTA = [
    "website-audit/",
    "methodology/",
    "ai-visibility/",
    "seo-audit/",
    "technical-seo-audit/",
    "about/",
  ];

  it("стоїть на шести сторінках у всіх мовах — і рівно один раз", () => {
    let seen = 0;
    for (const { name, text } of contentFiles()) {
      if (!WITH_CTA.some((prefix) => name.startsWith(prefix))) continue;
      expect(text.split("<SiteCta").length - 1, `${name}`).toBe(1);
      seen += 1;
    }
    // 5 сторінок × 6 мов + methodology × 6 = 36; geo-audit має лише 2 мови.
    expect(seen).toBeGreaterThanOrEqual(34);
  });

  it("на «Контактах» CTA перевірки сайту немає", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("contact/")) continue;
      expect(text.includes("SiteCta"), name).toBe(false);
      expect(text.includes("/result"), name).toBe(false);
    }
  });

  it("текст CTA не називає превʼю повним звітом і нічого не обіцяє зайвого", async () => {
    const { ctaOf } = await import("./cta");
    for (const locale of ["en", "uk", "de", "es", "fr", "ru"] as const) {
      const cta = ctaOf(locale);
      expect(cta.title.length).toBeGreaterThan(3);
      expect(cta.text.length).toBeGreaterThan(30);
      const lower = cta.text.toLowerCase();
      for (const phrase of [
        "no card", "without registration", "без картки", "без реєстрації",
        "перший аудит безкоштовно", "free full report", "повний звіт безкоштовно",
      ]) {
        expect(lower.includes(phrase), `${locale}: «${phrase}»`).toBe(false);
      }
      expect(cta.href.startsWith("/result")).toBe(true);
    }
    expect(ctaOf("uk").href).toBe("/result?lang=uk");
  });
});

describe("про нас: без вигаданого масштабу (екран 11)", () => {
  it("прибрано все, що назвав власник", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("about/")) continue;
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      for (const gone of [
        "Ми зробили аудит, який самі хотіли б отримувати",
        "Помилка, яка визначила продукт",
        "Де ми зараз",
        "Читайте також",
        "Спробувати Crawldy",
        "Related",
      ]) {
        expect(rendered.includes(gone), `${name}: «${gone}»`).toBe(false);
      }
    }
  });

  it("жодних вигаданих людей, офісів, клієнтів і досягнень", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("about/")) continue;
      // Коментарі не рендеряться — і саме в них законно згадано те, чого
      // на сторінці немає (стокові люди, офіси). Скануємо лише видиме.
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      // Стокових фото немає за побудовою: сторінка не імпортує зображень.
      expect(/<img|next\/image|unsplash|pexels/i.test(rendered), name).toBe(false);
      for (const invented of [
        "our team of", "наша команда з", "клієнтів по всьому світу",
        "офіс", "співробітник", "нагород",
      ]) {
        expect(
          rendered.toLowerCase().includes(invented.toLowerCase()),
          `${name}: «${invented}»`,
        ).toBe(false);
      }
    }
  });

  it("українська — точні погоджені формулювання", () => {
    const about = readFileSync(join(CONTENT, "about", "uk.tsx"), "utf-8");
    for (const approved of [
      "ПРО НАС",
      "Допомагаємо зрозуміти, як пошук і ШІ бачать ваш сайт",
      "Crawldy — сервіс аналізу сайтів, який обʼєднує видимість у пошуку, готовність до ШІ, технічний стан сайту та фактичні згадки в ШІ-асистентах в одному зрозумілому звіті.",
      "Чому створено Crawldy",
      "Наша мета",
      "Для кого створено Crawldy",
      "Власникам сайтів",
      "Маркетологам",
      "Вебагенціям",
    ]) {
      expect(about.includes(approved), `«${approved}»`).toBe(true);
    }
    // Перелік аудиторій зі вступу знято: він стоїть нижче окремим
    // розділом, і в першому реченні лише розтягував його.
    expect(
      about.includes("для власників бізнесу, маркетологів і вебагенцій"),
    ).toBe(false);
  });

  it("вступ — одне речення про те, що Crawldy зводить в один звіт", () => {
    // Однакове твердження шістьма мовами: жодна не лишилась зі старим
    // переліком аудиторій і жодна не отримала англійського вступу.
    const opening: Record<string, string> = {
      en: "Crawldy is a website analysis service that brings search visibility",
      uk: "Crawldy — сервіс аналізу сайтів, який обʼєднує видимість у пошуку",
      de: "Crawldy ist ein Analysedienst für Websites, der Sichtbarkeit in der Suche",
      es: "Crawldy es un servicio de análisis de sitios web que reúne la visibilidad",
      fr: "Crawldy est un service d'analyse de sites web qui réunit la visibilité",
      ru: "Crawldy — сервис анализа сайтов, который объединяет видимость в поиске",
    };
    for (const [locale, starts] of Object.entries(opening)) {
      const text = readFileSync(join(CONTENT, "about", `${locale}.tsx`), "utf-8");
      expect(text.includes(starts), `${locale}: вступ`).toBe(true);
    }
  });
});

describe("контакти: одна дія й жодної відкритої пошти (екран 12)", () => {
  it("прибрано все, що назвав власник", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("contact/")) continue;
      const rendered = text.replace(/\/\*[\s\S]*?\*\//g, "");
      for (const gone of [
        "Одна адреса, і за нею людина",
        "Що варто додати",
        "Юридичні реквізити",
        "Читайте також",
        "mailto:",
        "support@crawldy.com",
        "@crawldy",
      ]) {
        expect(rendered.includes(gone), `${name}: «${gone}»`).toBe(false);
      }
    }
  });

  it("відкритої адреси пошти немає й у футері сайту", () => {
    const shell = readFileSync(
      join(APP, "components", "PublicShell.tsx"),
      "utf-8",
    );
    const rendered = shell.replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
    expect(rendered.includes("mailto:")).toBe(false);
    expect(rendered.includes("CONTACT_EMAIL")).toBe(false);
  });

  it("копірайт: знак і напис разом праворуч, із застереженням про права", () => {
    const shell = readFileSync(
      join(APP, "components", "PublicShell.tsx"),
      "utf-8",
    );
    // Знак і напис — одна пара: `justify-end` рухає обидва. `ms-auto`
    // на самому написі лишав значок біля лівого краю.
    expect(shell.includes("items-center justify-end")).toBe(true);
    expect(shell.includes('<span className="ms-auto">©')).toBe(false);
    // Застереження про права — шістьма мовами, кожна власними словами.
    const rights: Record<string, string> = {
      en: "All rights reserved.",
      uk: "Усі права захищено.",
      de: "Alle Rechte vorbehalten.",
      es: "Todos los derechos reservados.",
      fr: "Tous droits réservés.",
      ru: "Все права защищены.",
    };
    for (const [locale, line] of Object.entries(rights)) {
      expect(shell.includes(`${locale}: "${line}"`), locale).toBe(true);
    }
  });

  it("сторінка несе робочу форму, а не посилання", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("contact/")) continue;
      expect(text.includes("<ContactForm"), name).toBe(true);
    }
    const form = readFileSync(
      join(APP, "components", "ContactForm.tsx"),
      "utf-8",
    );
    // Успіх — лише після відповіді сервера.
    expect(form.includes('setPhase("sent")')).toBe(true);
    expect(form.includes("if (!response.ok)")).toBe(true);
    // Приманка, челендж і власна валідація.
    expect(form.includes("contact-company")).toBe(true);
    expect(form.includes("turnstile")).toBe(true);
    expect(form.includes("noValidate")).toBe(true);
    // Доступність: фокус, Escape, повернення фокуса.
    expect(form.includes('event.key === "Escape"')).toBe(true);
    expect(form.includes("openButton.current?.focus()")).toBe(true);
    expect(form.includes('role="alert"')).toBe(true);
    // Форма ховається КЛАСОМ, а не самим атрибутом `hidden`: клас
    // `flex` перебиває стиль браузера для [hidden], і форма стояла на
    // екрані разом із кнопкою — при цьому челендж у ній ще не існував,
    // бо ініціалізується він лише на відкриття.
    expect(form.includes('opened ? "flex" : "hidden"')).toBe(true);
    // Готовність провайдера — за наявністю самого обʼєкта, а не тега
    // скрипта: тег зʼявляється раніше, і на повторному відкритті
    // віджет мовчки не малювався.
    expect(form.includes("if (window.turnstile)")).toBe(true);
    // Секретів і адреси одержувача в клієнті немає.
    expect(form.includes("secret")).toBe(false);
    expect(/@crawldy/.test(form)).toBe(false);
  });

  it("усі шість мов несуть власні стани форми", () => {
    for (const { name, text } of contentFiles()) {
      if (!name.startsWith("contact/")) continue;
      for (const key of [
        "open:", "name:", "email:", "site:", "message:", "submit:",
        "success:", "failure:", "invalidEmail:", "rejected:", "tooMany:",
      ]) {
        expect(text.includes(key), `${name}: ${key}`).toBe(true);
      }
    }
  });
});

describe("паритет каталогів кабінету", () => {
  it("українська повна відносно англійської", () => {
    expect(missingKeys("uk")).toEqual([]);
  });
});
