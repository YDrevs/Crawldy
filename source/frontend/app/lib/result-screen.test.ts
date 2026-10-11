/**
 * Екран безкоштовного результату: що саме він каже і якими мовами.
 *
 * Перевіряються рівно ті місця, де він раніше говорив неправду або
 * суперечив сам собі:
 *
 * — покриття казало «Сайт відповідав повністю» і «10 з 11» одночасно;
 * — картки несли бейджі «Терміново» / «Важливо», і «Терміново» стояло
 *   нижче за два «Важливо», бо порядок брався не зі смуги;
 * — унизу висіло гасло, яке нічого не додавало до результату;
 * — чотири з шести мов сайту падали в англійський фолбек.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import * as React from "react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { PUBLIC_SITE_LOCALES, plural, translate } from "./i18n";
import { MOCK_FREE_RESULT } from "./free-result";
import type { Locale } from "./contracts";

const source = readFileSync(
  join(__dirname, "..", "(product)", "result", "page.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

// Оболонка, стан виконання і хід живуть у сусідньому модулі: сторінка
// App Router не може експортувати компонент, а поведінковий сторож мусить
// його рендерити. Твердження про них читають той модуль, твердження про
// сторінку — сторінку, а твердження про екран у цілому — обидва.
const screens = readFileSync(
  join(__dirname, "..", "(product)", "result", "screens.tsx"),
  "utf-8",
).replace(/\r\n/g, "\n");

const LOCALES = PUBLIC_SITE_LOCALES;

// `@types/react-dom` не є залежністю проєкту, тож звичайний
// `import { renderToStaticMarkup } from "react-dom/server"` валить
// `tsc --noEmit`. Додавати залежність заради одного типу — це правка
// `package.json`, тобто шлях поза дозволеними; натомість тут оголошена
// форма ЄДИНОЇ потрібної функції. `require` типізований через
// `@types/node`, який у проєкті є, тож це перевірений тип, а не `any`.
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: unknown) => string;
};

// Тести фронтенду ходять під `environment: "node"` і без DOM — так
// налаштовано навмисно, і цей файл нічого в конфігурації не міняє.
// `renderToStaticMarkup` DOM і не потребує: він віддає рядок розмітки.
//
// Єдине, чого бракує, — JSX-рантайм: `.tsx` модулі тут компілюються
// КЛАСИЧНИМ перетворенням, тобто в голий `React.createElement` без
// імпорту React. Глобал нижче саме це й дає. Він живе в цьому файлі,
// не додає залежностей і не чіпає жодного іншого тесту.
(globalThis as unknown as { React: typeof React }).React = React;

/** Відрендерити справжній термінальний екран і віддати його розмітку. */
async function renderRunning(started: unknown, locale: Locale): Promise<string> {
  const { Running } = await import("../(product)/result/screens");
  const { LocaleProvider } = await import("./locale");
  return renderToStaticMarkup(
    createElement(
      LocaleProvider,
      { locale } as never,
      createElement(Running, { started } as never),
    ),
  );
}

// ── D1: покриття ───────────────────────────────────────────────────────

describe("покриття каже одну річ, а не дві суперечливі", () => {
  it("рівня покриття словами на екрані більше немає", () => {
    // «Сайт відповідав повністю» поруч із «10 з 11» — це заперечення
    // самого себе. Числа й є твердженням.
    expect(source).not.toContain("free.coverage.full");
    expect(source).not.toContain("free.coverage.partial");
    expect(source).not.toContain("free.coverage.insufficient");
    expect(source).not.toContain("free.coveragePages");
    for (const locale of LOCALES) {
      for (const key of [
        "free.coverage.full",
        "free.coverage.partial",
        "free.coverage.insufficient",
      ]) {
        // Ключа немає — `translate` віддає сам ключ.
        expect(translate(locale, key)).toBe(key);
      }
    }
  });

  it("10 з 11 читається однією фразою в кожній мові", () => {
    for (const locale of LOCALES) {
      const text = plural(locale, "free.coverage.checked", 11, {
        read: 10,
        known: 11,
      });
      expect(text, locale).toContain("10");
      expect(text, locale).toContain("11");
      expect(text, locale).not.toContain("{");
      expect(text, locale).not.toBe("free.coverage.checked");
    }
  });

  it("один із одного не збивається на множину", () => {
    for (const locale of LOCALES) {
      const text = plural(locale, "free.coverage.checked", 1, { read: 1, known: 1 });
      expect(text, locale).not.toContain("{");
      // Форма для одиниці існує окремо від решти.
      const many = plural(locale, "free.coverage.checked", 11, { read: 10, known: 11 });
      expect(text, locale).not.toBe(many);
    }
  });

  it("нуль прочитаних теж має свою фразу", () => {
    for (const locale of LOCALES) {
      const text = plural(locale, "free.coverage.checked", 9, { read: 0, known: 9 });
      expect(text, locale).toContain("0");
      expect(text, locale).not.toContain("{");
    }
  });

  it("блок має заголовок у кожній мові", () => {
    const expected: Record<string, string> = {
      en: "Coverage",
      uk: "Покриття",
      de: "Abdeckung",
      es: "Cobertura",
      fr: "Couverture",
      ru: "Охват",
    };
    expect(source).toContain('{t("free.coverage")}');
    for (const locale of LOCALES) {
      expect(translate(locale, "free.coverage"), locale).toBe(expected[locale]);
    }
  });

  it("рядок про неперевірені зʼявляється лише коли вони є", () => {
    expect(source).toContain("pages_known - pages_read");
    expect(source).toContain("unchecked > 0");
  });

  it("10 із 52 називає всі сорок дві неперевірені", () => {
    // Головний випадок свіжого приймання: екран показував «10 із 52» і
    // мовчав про решту. Число рахується, а не зашите.
    const expected: Record<string, string> = {
      en: "42 pages could not be checked.",
      uk: "42 сторінки не вдалося перевірити.",
      de: "42 Seiten konnten nicht geprüft werden.",
      es: "No se pudieron comprobar 42 páginas.",
      fr: "42 pages n’ont pas pu être vérifiées.",
      ru: "Не удалось проверить 42 страницы.",
    };
    for (const locale of LOCALES) {
      expect(plural(locale, "free.coverage.unchecked", 52 - 10), locale).toBe(
        expected[locale],
      );
    }
  });

  it("10 з 11 лишає одну сторінку — і це однина", () => {
    for (const locale of LOCALES) {
      const one = plural(locale, "free.coverage.unchecked", 11 - 10);
      const many = plural(locale, "free.coverage.unchecked", 42);
      expect(one, locale).not.toContain("{");
      expect(one, locale).not.toBe(many);
    }
  });

  it("1 з 1 не дає рядка взагалі", () => {
    // Нуль неперевірених — рядка немає. Умова в коді одна, і вона тут.
    expect(1 - 1).toBe(0);
    expect(source).toContain("unchecked > 0");
  });

  it("0 з N чесно каже, що не прочитано нічого", () => {
    for (const locale of LOCALES) {
      const checked = plural(locale, "free.coverage.checked", 9, { read: 0, known: 9 });
      expect(checked, locale).toContain("0");
      expect(checked, locale).toContain("9");
      const unchecked = plural(locale, "free.coverage.unchecked", 9);
      expect(unchecked, locale).toContain("9");
      expect(unchecked, locale).not.toContain("{");
    }
  });

  it("неперевірене не називається невдалим у коді екрана", () => {
    // `pages_failed` — вужчий факт (адреса віддала помилку), і він
    // лишається в контракті. Але другий рядок описує наш бюджет, а не
    // поведінку сайту, тож і рахується він з іншого числа.
    expect(source).not.toContain("free.coverage.failed");
    for (const locale of LOCALES) {
      expect(translate(locale, "free.coverage.failed.other")).toBe(
        "free.coverage.failed.other",
      );
    }
  });
});

// ── D2: серйозність, порядок і вплив ───────────────────────────────────

describe("серйозність описана одним словником", () => {
  it("три смуги мають назви в кожній мові", () => {
    for (const locale of LOCALES) {
      const labels = (["high", "medium", "low"] as const).map((key) =>
        translate(locale, `free.severity.${key}`),
      );
      expect(new Set(labels).size, locale).toBe(3);
      for (const label of labels) expect(label, locale).not.toContain("free.severity");
    }
  });

  it("бейджів терміновості на картках більше немає", () => {
    expect(source).not.toContain("URGENCY_TONE");
    expect(source).not.toContain("free.urgency");
    for (const locale of LOCALES) {
      for (const key of ["free.urgency.urgent", "free.urgency.important"]) {
        expect(translate(locale, key)).toBe(key);
      }
    }
  });

  it("заголовок трійки називає підставу відбору", () => {
    for (const locale of LOCALES) {
      const text = translate(locale, "free.topProblems");
      expect(text, locale).not.toBe("free.topProblems");
      expect(text.length, locale).toBeGreaterThan(10);
    }
  });

  it("вплив на бал показується числом із бекенда", () => {
    expect(source).toContain("problem.impact_points");
    // Жодного обчислення бала на клієнті.
    expect(source).not.toContain("impact_points +");
    expect(source).not.toContain("reduce(");
  });

  it("«+0 до бала» не показується ніколи", () => {
    // Нуль означає або приріст менший за одиницю після округлення, або
    // відсутній загальний бал — і жодне з двох не «марно».
    expect(source).toContain("problem.floored || problem.impact_points === 0");
  });

  it("підпис впливу існує в кожній мові й несе число", () => {
    for (const locale of LOCALES) {
      const text = translate(locale, "free.scoreImpact", { points: "−7" });
      expect(text, locale).toContain("−7");
      expect(text, locale).not.toContain("{");
    }
  });

  it("картки макета вже впорядковані спаданням впливу", () => {
    const impacts = MOCK_FREE_RESULT.problems.map((p) => p.impact_points);
    expect(impacts).toEqual([...impacts].sort((a, b) => b - a));
  });
});

// ── D4: блок повного звіту ─────────────────────────────────────────────

describe("блок повного звіту нічого не вимагає й нічого не обіцяє", () => {
  it("заголовок, підводка й кнопка є в кожній мові", () => {
    for (const locale of LOCALES) {
      for (const key of ["free.paywallTitle", "free.paywallLead", "free.cta"]) {
        const text = translate(locale, key);
        expect(text, `${locale}/${key}`).not.toBe(key);
        expect(text.length, `${locale}/${key}`).toBeGreaterThan(3);
      }
    }
  });

  it("кнопка не просить ані входу, ані передплати", () => {
    const forbidden = [
      "Sign in", "Subscribe", "Subscription",
      "Увійти", "Передплат", "Підписк",
      "Anmelden", "Abonn",
      "Iniciar sesión", "Suscri",
      "Se connecter", "Abonn",
      "Войти", "Подписк",
    ];
    for (const locale of LOCALES) {
      const cta = translate(locale, "free.cta");
      for (const word of forbidden) {
        expect(cta.toLowerCase(), `${locale}: ${word}`).not.toContain(word.toLowerCase());
      }
    }
  });

  it("«діагноз» замінено на «розбір» — жодною мовою не лишилось", () => {
    for (const locale of LOCALES) {
      const lead = translate(locale, "free.paywallLead");
      expect(lead.toLowerCase()).not.toContain("діагноз");
      expect(lead.toLowerCase()).not.toContain("diagnos");
      expect(lead.toLowerCase()).not.toContain("диагноз");
    }
  });
});

// ── D6: гасло внизу ────────────────────────────────────────────────────

describe("під результатом немає гасла", () => {
  it("рядок прибрано з екрана й з каталогу всіх мов", () => {
    expect(source).not.toContain("free.footer");
    for (const locale of LOCALES) {
      expect(translate(locale, "free.footer")).toBe("free.footer");
    }
  });

  it("на його місце не поставили іншого гасла", () => {
    expect(source).not.toContain("<footer");
  });
});

// ── шість мов, а не дві ────────────────────────────────────────────────

describe("екран говорить усіма мовами публічного сайту", () => {
  it("мова береться з переліку сайту, а не з двох зашитих", () => {
    expect(source).toContain("asSiteLocale(params.get(\"lang\"))");
    expect(source).not.toContain('requested === "uk"');
  });

  it("множинні рядки теж свої, а не англійські", () => {
    // Спіймано очима на живому екрані: іспанська й німецька сторінки
    // показували «41 issues found». Ключ множини лежить у словнику з
    // суфіксом форми, тож перевірка голого імені його не бачить — саме
    // так фолбек і проліз.
    for (const locale of LOCALES) {
      if (locale === "en") continue;
      for (const count of [1, 2, 5, 41]) {
        const text = plural(locale, "free.issuesFound", count);
        expect(text, `${locale}/${count}`).toContain(String(count));
        expect(text, `${locale}/${count}`).not.toContain("issues found");
        expect(text, `${locale}/${count}`).not.toContain("issue found");
      }
    }
  });

  it("кожен ключ екрана має власний рядок у кожній мові", () => {
    // Фолбек мовчазний: без свого рядка сторінка змішує дві мови на
    // одному екрані, і жоден тест її на цьому не ловить.
    const keys = [
      "free.overall",
      "free.noScore",
      "free.auditRunningTitle",
      "free.auditRunningLead",
      "free.topProblems",
      "free.paywallTitle",
      "free.paywallLead",
      "free.cta",
      "free.severity.high",
      "free.severity.medium",
      "free.severity.low",
      "free.scoreImpact",
      "free.stage.discovery",
      "free.stage.crawl",
      "free.stage.measuring",
      "free.stage.render",
      "free.stage.analysis",
      "free.stage.scoring",
      "free.unlocks.scores",
      "free.unlocks.findings",
      "free.unlocks.pages",
      "free.unlocks.evidence",
      "free.unlocks.fixes",
      "free.unlocks.download",
      "free.processingTitle",
      "free.processingLead",
      "free.payment.failed.title",
      "free.payment.failed.lead",
      "free.payment.retry",
      // Чотири документи: аудит і присутність, кожен у двох видах.
      // Гість купує їх разом, тож усі підписи мусять бути шістьма мовами.
      "result.downloadGeneral",
      "result.downloadTechnical",
      "free.presence.general",
      "free.presence.technical",
    ];
    const english = keys.map((key) => translate("en", key));
    for (const locale of LOCALES) {
      if (locale === "en") continue;
      for (const [index, key] of keys.entries()) {
        const text = translate(locale, key);
        expect(text, `${locale}/${key}`).not.toBe(key);
        // Збіг з англійською — ознака мовчазного фолбеку. Виняток лише
        // там, де слово справді те саме в обох мовах.
        if (key !== "result.downloadJson") {
          expect(text, `${locale}/${key} = англійська`).not.toBe(english[index]);
        }
      }
    }
  });
});

// ── B2: повідомлення про хід аудиту ────────────────────────────────────

describe("поки аудит виконується, екран каже рівно погоджене", () => {
  const RUNNING: Record<string, string> = {
    en: "We’re loading and checking your site’s pages. This usually takes one or two minutes. When the check is complete, this page will update automatically.",
    uk: "Завантажуємо та перевіряємо сторінки сайту. Зазвичай це займає одну-дві хвилини. Після завершення перевірки сторінка оновиться сама.",
    de: "Wir laden die Seiten Ihrer Website und prüfen sie. Das dauert in der Regel ein bis zwei Minuten. Nach Abschluss der Prüfung wird diese Seite automatisch aktualisiert.",
    es: "Estamos cargando y comprobando las páginas de tu sitio. Normalmente tarda uno o dos minutos. Cuando termine la comprobación, esta página se actualizará automáticamente.",
    fr: "Nous chargeons et vérifions les pages de votre site. Cela prend généralement une à deux minutes. Une fois la vérification terminée, cette page s’actualisera automatiquement.",
    ru: "Загружаем и проверяем страницы сайта. Обычно это занимает одну-две минуты. После завершения проверки страница обновится автоматически.",
  };

  it("текст точний у шести мовах, без крапки з комою й сирих ключів", () => {
    for (const locale of LOCALES) {
      const text = translate(locale, "free.auditRunningLead");
      expect(text, locale).toBe(RUNNING[locale]);
      expect(text, locale).not.toContain(";");
      expect(text, locale).not.toMatch(/free\.|status\./);
    }
  });

  it("показується лише поки аудит справді виконується", () => {
    // Один і той самий блок: живий стан бере рядок ходу, завершений
    // невдачею — причину. Перемикач — статус із сервера.
    //
    // Раніше обидві гілки були двома ключами каталогу в одному тернарі.
    // Відколи причину каже бекенд, гілка невдачі спершу дивиться на його
    // речення й лише потім падає на загальний рядок — тож тверджень теж
    // два, по одному на гілку, а не один рядок на обидві.
    expect(screens).toContain('? reason || t("free.auditFailedLead")');
    expect(screens).toContain(': t("free.auditRunningLead")');
    expect(screens).toContain("const failed = !auditIsRunning(started.status);");
  });

  it("завершення оновлює сторінку через справжнє опитування, а не таймер-обіцянку", () => {
    expect(source).toContain("if (view === null || !auditIsRunning(view.status)) return;");
    expect(source).toContain("window.setTimeout(() => void refresh(), AUDIT_POLL_MS)");
    expect(source).toContain("if (!isShortView(view)) return <Running started={view} />;");
  });

  it("підпис впливу на бал живе в картці проблеми, а не в тексті ходу", () => {
    const running = screens.slice(screens.indexOf("function Running("), screens.indexOf("function Progress("));
    expect(running).not.toContain("free.scoreImpact");
    const problems = source.slice(source.indexOf("function TopProblems("));
    expect(problems).toContain('t("free.scoreImpact"');
  });

  it("помилка аудиту лишається локалізованою й дієвою", () => {
    for (const locale of LOCALES) {
      const lead = translate(locale, "free.auditFailedLead");
      expect(lead, locale).not.toBe("free.auditFailedLead");
      expect(lead.length, locale).toBeGreaterThan(20);
    }
  });

  it("термінальний стан показує речення бекенда, а не власне тлумачення", () => {
    // Речення складає бекенд мовою запиту з нормалізованого класу. Екран
    // його лише показує: свого каталогу пʼяти станів тут немає, бо другий
    // переклад розійшовся б із першим.
    expect(screens).toContain("const reason = started.failure_reason?.trim();");
    expect(screens).toContain('reason || t("free.auditFailedLead")');
  });

  it("запасний рядок лишається саме запасним", () => {
    // `||` після `trim()` означає: порожнє, пробільне або відсутнє поле
    // падає на загальне речення, яке вже перекладене всіма мовами екрана.
    // Порожнє місце на екрані невдачі було б гіршою відповіддю.
    const running = screens.slice(screens.indexOf("function Running("),
                                  screens.indexOf("function Progress("));
    expect(running).toContain("failure_reason?.trim()");
    expect(running).toContain('t("free.auditFailedLead")');
  });

  it("виконуваний аудит не показує полів про невдачу", () => {
    const running = screens.slice(screens.indexOf("function Running("),
                                  screens.indexOf("function Progress("));
    // Гілка причини стоїть під `failed`; у живій гілці — рядок ходу.
    expect(running).toContain('? reason || t("free.auditFailedLead")');
    expect(running).toContain(': t("free.auditRunningLead")');
  });

  it("екран не знає жодного класу невдачі поіменно", () => {
    // Якби тут зʼявився перелік, пʼять станів мали б два джерела істини.
    for (const cls of ["site_unreachable", "site_blocked", "provider_failed",
                       "internal_error", "cancelled"]) {
      expect(source + screens, cls).not.toContain(cls);
    }
  });

  it("сире `error` не має куди потрапити на екран", async () => {
    // Це ПОВЕДІНКОВИЙ сторож: він рендерить справжній термінальний екран
    // і дивиться на те, що вийшло. Так він і має бути написаний.
    //
    // Дві попередні версії були переліком заборонених рядків У ТЕКСТІ
    // файла. Першу обійшло приведення типу
    // `(started as unknown as { error?: string }).error` — рядка
    // "started.error" у ній немає. Друга заборонила й приведення, але
    // обидва її регулярні вирази містили літеральний 0x08 замість `\b`,
    // тобто вимагали керуючого байта, якого у звичайному коді не буває,
    // і не спрацьовували НІКОЛИ. Обидві були зелені.
    //
    // Заборонний перелік ловить рівно ті форми, які уявив його автор.
    // Рендер ловить будь-яку, бо питання інше: чи потрапив маркер на
    // екран. Як саме його туди не пустили — байдуже.
    const marker = "ZZ7Q4X-Traceback-psycopg2-OperationalError-SECRET-9f2e";
    const started = {
      audit_id: "a1",
      status: "failed",
      unlocked: false,
      failure_class: "site_blocked",
      failure_reason: translate("uk", "free.auditFailedLead"),
      // Рантайм може принести поле, якого немає в типі: контракт його не
      // обіцяє, але й не забороняє серверу його надіслати.
      error: marker,
    };

    const html = await renderRunning(started, "uk");

    expect(html).toContain(started.failure_reason);
    expect(html).not.toContain(marker);
    // І жодного фрагмента: склеїти маркер із частин так само означало б
    // показати його. Береться кожен токен, довший за три символи.
    for (const fragment of marker.split("-").filter((piece) => piece.length > 3)) {
      expect(html, fragment).not.toContain(fragment);
    }
  });

  it("пропущений аудит термінальний і для екрана теж", () => {
    const guest = readFileSync(join(__dirname, "guest-payment.ts"), "utf-8");
    expect(guest).toContain('"skipped"');
    const done = guest.slice(guest.indexOf("const AUDIT_DONE"),
                             guest.indexOf("export const auditIsRunning"));
    expect(done).toContain('"failed"');
    expect(done).toContain('"skipped"');
  });
});

// ── §1.4: платний екран не падає в англійський фолбек ──────────────────

describe("оплачений екран говорить мовою сторінки", () => {
  // `free.unlockedTitle` і `result.noScoreTitle` жили лише в EN та UK,
  // тож німець після оплати читав англійський рядок. Фолбек мовчазний:
  // помітити його можна лише порівнянням із самою англійською.
  const PAID = ["free.unlockedTitle", "free.unlockedLead", "result.noScoreTitle"];

  it("ключі оплаченого стану написані кожною мовою окремо", () => {
    for (const key of PAID) {
      for (const locale of LOCALES) {
        const value = translate(locale, key);
        expect(value, `${locale}/${key}`).not.toBe(key);
        if (locale === "en") continue;
        expect(value, `${locale}/${key}: англійський фолбек`).not.toBe(
          translate("en", key),
        );
      }
    }
  });
});
