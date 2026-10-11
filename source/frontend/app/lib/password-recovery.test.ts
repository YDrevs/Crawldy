/**
 * Відновлення й зміна пароля: інваріанти інтерфейсу.
 *
 * Найдорожчий із них — четвертий. Обробник кнопки «змінити пароль»
 * спершу робив перехід сам, і перехід не виживав: `clear()` обнуляє
 * профіль, сторож кабінету спрацьовує наступним і перекриває адресу
 * своєю, а разом із нею зникає підпис про успіх. Зовні це виглядало як
 * «підпис не працює» при цілком правильному коді обробника. Та сама
 * халепа вже з'їдала мову при виході, і саме тому тут не текст на
 * екрані, а правило: хто гасить сесію, той переходу не робить.
 *
 * Решта — межі, які легко зрушити випадково: правило мови в адресі,
 * перелік дозволених новин, розмір сітки нижньої смуги.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { AUTH_PAGE_KEYS, PUBLIC_SITE_LOCALES, productHref, withNotice } from "./i18n";
import { MIN_PASSWORD_LENGTH } from "./password-policy";
import type { Locale } from "./contracts";

const APP = join(process.cwd(), "app");

function read(...parts: string[]): string {
  return readFileSync(join(APP, ...parts), "utf-8");
}

const LAYOUT = read("(product)", "app", "layout.tsx");
const LOGIN = read("(product)", "login", "page.tsx");
const FORGOT = read("(product)", "forgot", "page.tsx");
const RESET = read("(product)", "reset", "page.tsx");
const SHELL = read("components", "AppShell.tsx");
const DIALOG = read("components", "ChangePasswordDialog.tsx");

describe("адреса несе мову", () => {
  it("англійська без параметра, решта з ним", () => {
    expect(productHref("/forgot", "en")).toBe("/forgot");
    for (const locale of PUBLIC_SITE_LOCALES) {
      if (locale === "en") continue;
      expect(productHref("/forgot", locale)).toBe(`/forgot?lang=${locale}`);
    }
  });

  it("підпис про подію не ламає вже наявний параметр", () => {
    // `/login?lang=uk?notice=reset` — це один параметр із дивним
    // значенням, а не два. Склеювати через «?» наосліп не можна.
    expect(withNotice("/login", "reset")).toBe("/login?notice=reset");
    expect(withNotice("/login?lang=uk", "reset")).toBe("/login?lang=uk&notice=reset");
  });

  it("усі три екрани будують дорогу назад одним правилом", () => {
    for (const source of [LOGIN, FORGOT, RESET]) {
      expect(source).toContain("productHref(");
    }
  });
});

describe("сторож кабінету несе все, що має нести", () => {
  it("обробник зміни пароля НЕ робить переходу сам", () => {
    // Інакше `clear()` обнуляє профіль, сторож спрацьовує наступним і
    // перекриває адресу своєю — підпис про успіх зникає.
    const handler = LAYOUT.slice(
      LAYOUT.indexOf("onPasswordChanged={"),
      LAYOUT.indexOf("      >", LAYOUT.indexOf("onPasswordChanged={")),
    );
    expect(handler.length, "обробника onPasswordChanged немає").toBeGreaterThan(0);
    expect(handler).not.toContain("router.replace");
    expect(handler).toContain("setNotice");
    expect(handler).toContain("clear()");
  });

  it("перехід сторожа несе і мову, і новину", () => {
    expect(LAYOUT).toContain("withNotice(back, notice)");
    expect(LAYOUT).toMatch(/const back = `\/login\?lang=\$\{site\}`/);
  });

  it("обидва переходи на форму входу несуть мову", () => {
    // Те саме, що стереже `cabinet-locales.test.ts`; повторено тут, бо
    // саме ця правка рухала цей рядок.
    const carried = LAYOUT.match(/\/login\?lang=\$\{site\}/g) ?? [];
    expect(carried.length).toBeGreaterThanOrEqual(2);
  });
});

describe("форма входу", () => {
  it("«забули пароль» стоїть у формі, одразу після кнопки входу", () => {
    const form = LOGIN.slice(LOGIN.indexOf("<form"), LOGIN.indexOf("</form>"));
    const submit = form.indexOf('type="submit"');
    const forgot = form.indexOf('t("auth.forgot")');
    expect(submit, "кнопки входу у формі немає").toBeGreaterThan(0);
    expect(forgot, "посилання «забули пароль» у формі немає").toBeGreaterThan(submit);
  });

  it("посилання не показується тому, хто створює акаунт", () => {
    // Пароля в нього ще немає, відновлювати нічого.
    expect(LOGIN).toContain("creating ? null : (");
  });

  it("посилання немає в жодній навігації", () => {
    expect(SHELL).not.toContain("/forgot");
    expect(read("components", "PublicShell.tsx")).not.toContain("/forgot");
  });

  it("приймаються лише перелічені значення ?notice=", () => {
    // Підстановка довільного рядка з адреси зробила б ключем каталогу
    // будь-що, і сторонній міг би підібрати посилання, яке показує на
    // формі входу чуже повідомлення.
    expect(LOGIN).toContain("const NOTICE_KEYS: Record<string, string> = {");
    expect(LOGIN).toMatch(/NOTICE_KEYS\[params\.get\("notice"\) \?\? ""\] \?\? null/);
  });
});

describe("нижня смуга кабінету не виросла", () => {
  it("розділів лишилось п'ять, сітка — та сама", () => {
    expect(SHELL).toContain("grid grid-cols-5");
    const items = SHELL.slice(SHELL.indexOf("const NAV: NavItem[] = ["), SHELL.indexOf("];"));
    expect((items.match(/href: "/g) ?? []).length).toBe(5);
  });

  it("зміна пароля живе в меню акаунта, а не в навігації", () => {
    expect(SHELL).toContain('<MenuItem icon="settings" onClick={onChangePassword}>');
    const nav = SHELL.slice(SHELL.indexOf("const NAV: NavItem[] = ["), SHELL.indexOf("];"));
    expect(nav).not.toContain("password");
  });
});

describe("правило пароля однакове на всіх екранах", () => {
  it("число живе в одному місці, а не в трьох копіях", () => {
    // Раніше кожен екран оголошував власну константу, і всі три
    // випадково збігалися. Збіг — не механізм: копії розходяться, і
    // питання лише коли. Тепер джерело одне, і кожен екран його
    // ІМПОРТУЄ, а не переписує.
    for (const source of [LOGIN, RESET, DIALOG]) {
      expect(source).toContain("MIN_PASSWORD_LENGTH");
      expect(source).toContain("password-policy");
      expect(source, "екран знову оголосив власне число").not.toMatch(
        /const MIN_PASSWORD/,
      );
    }
  });

  it("жоден екран не порівнює довжину з літералом", () => {
    // Саме так це число й розмножувалося: не константою, а числом
    // усередині умови.
    for (const source of [LOGIN, RESET, DIALOG]) {
      expect(source).not.toMatch(/\.length\s*<\s*\d+/);
    }
  });

  it("мінімум — дванадцять, і текст правила каже те саме", () => {
    // Сторона бекенда звіряється окремо, тестом
    // `test_password_policy.py`: він читає цей самий модуль і
    // валиться, якщо сторони розминулися.
    expect(MIN_PASSWORD_LENGTH).toBe(12);
    const catalog = readFileSync(join(APP, "lib", "i18n.ts"), "utf8");
    const hints = catalog.match(/^ {2}"auth\.passwordHint": "[^"]+",$/gm) ?? [];
    expect(hints.length, "правило пароля не в усіх шести мовах").toBe(6);
    for (const hint of hints) {
      expect(hint, `у правилі немає числа ${MIN_PASSWORD_LENGTH}`).toContain(
        String(MIN_PASSWORD_LENGTH),
      );
    }
  });

  it("обидва екрани звіряють повтор", () => {
    expect(RESET).toContain('return "recovery.mismatch"');
    expect(DIALOG).toContain('return "recovery.mismatch"');
  });

  it("поточний пароль обовʼязковий і при зміні в кабінеті", () => {
    // Інакше вкрадена сесія перетворюється на вкрадений акаунт.
    expect(DIALOG).toContain('autoComplete="current-password"');
    expect(DIALOG).toContain('if (!current) return "auth.passwordRequired"');
  });
});

describe("екран скидання", () => {
  it("питає про чинність посилання ДО того, як щось вводити", () => {
    // Інакше людина набирає новий пароль двічі, тисне «зберегти» і аж
    // тоді дізнається, що посилання застаріло.
    expect(RESET).toContain("checkPasswordResetToken(token)");
    expect(RESET).toContain('setLink("dead")');
  });

  it("порожній токен — теж мертве посилання, без запиту", () => {
    expect(RESET).toMatch(/if \(!token\) \{\s*setLink\("dead"\);/);
  });

  it("після успіху веде на вхід із підписом", () => {
    expect(RESET).toContain('withNotice(productHref("/login", locale), "reset")');
  });
});

describe("екран запиту не розкриває, чи є акаунт", () => {
  it("підтвердження умовне, а не «лист надіслано»", () => {
    expect(FORGOT).toContain('t("recovery.sentBody")');
    expect(FORGOT).toContain('t("recovery.sentTitle")');
  });

  it("екран не знає й не питає, чи є такий акаунт", () => {
    // Бекенд віддає однаковий 202 обом випадкам, тож розрізняти нема за
    // чим — а перевірка тут зловить спробу це «покращити».
    expect(FORGOT).not.toContain("exists");
    expect(FORGOT).not.toContain("404");
  });

  it("недоступна черга має власний текст", () => {
    // 503 означає, що листа нікому передати. Мовчазний успіх лишив би
    // людину чекати на те, чого не буде.
    expect(FORGOT).toContain('503: "recovery.unavailable"');
  });
});

describe("рядки існують шістьма мовами", () => {
  it("нові ключі форм входу додані до переліку повноти", () => {
    for (const key of [
      "auth.forgot",
      "auth.noticeReset",
      "auth.noticeChanged",
      "recovery.title",
      "recovery.sentBody",
      "recovery.linkDead",
      "recovery.mismatch",
    ]) {
      expect(AUTH_PAGE_KEYS, `${key} не в AUTH_PAGE_KEYS`).toContain(key);
    }
  });

  it("жодна мова сайту не лишилась без них", () => {
    // Повноту всіх ключів стереже `cabinet-locales.test.ts`; тут —
    // саме ті, що рендерять три екрани відновлення.
    const source = readFileSync(join(APP, "lib", "i18n.ts"), "utf8");
    const names: Locale[] = ["en", "uk", "de", "es", "fr", "ru"];
    const marks = names
      .map((n) => ({ n, i: source.indexOf(`const ${n}: Dict = {`) }))
      .sort((a, b) => a.i - b.i);
    marks.forEach((m, k) => {
      const end = k + 1 < marks.length ? marks[k + 1]!.i : source.indexOf("const DICTS");
      const block = source.slice(m.i, end);
      for (const key of AUTH_PAGE_KEYS) {
        expect(block.includes(`"${key}":`), `${m.n}: немає ${key}`).toBe(true);
      }
    });
  });
});
