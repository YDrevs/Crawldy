/**
 * Поле адреси сайту приймає голий домен — усюди, без винятків.
 *
 * `smartkp.com.ua` — це те, як адресу пише людина, і саме так її
 * приймають публічні форми з самого початку: сервер підставляє схему
 * сам (`normalize_origin` для сайтів, `normalize_url` для аудиту).
 *
 * `type="url"` цього не дозволяє: браузер відхиляє значення без схеми
 * власним «Введіть URL-адресу» ще до нашого коду, і жодне
 * повідомлення продукту людині не показується. Двічі — у «Додати
 * сайт» і «Запустити перевірку» — кабінет вимагав більшого за
 * продукт, тоді як сусідня форма на головній приймала те саме
 * значення.
 *
 * Тест дивиться на розмітку, а не на поведінку, бо саме атрибут і є
 * правилом: `inputMode="url"` лишає телефону правильну клавіатуру, не
 * забороняючи голий домен.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..");

function sources(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      found.push(...sources(full));
    } else if (entry.endsWith(".tsx")) {
      found.push(full);
    }
  }
  return found;
}

describe("адресу сайту можна ввести без схеми", () => {
  it('жодне поле не має type="url"', () => {
    const guilty = sources(APP).filter((file) =>
      readFileSync(file, "utf-8").includes('type="url"'),
    );
    expect(guilty.map((f) => f.slice(APP.length + 1))).toEqual([]);
  });

  it("поля адреси підказують клавіатуру, а не забороняють значення", () => {
    for (const file of ["AddSite.tsx", "NewAudit.tsx", "HeroAuditForm.tsx"]) {
      const source = readFileSync(join(APP, "components", file), "utf-8");
      expect(source, file).toContain('inputMode="url"');
    }
  });
});

/**
 * Меню людини в шапці публічного сайту.
 *
 * Сесія кабінету була невидимою: сайт показував «Увійти» тому, хто вже
 * увійшов. Стан, від якого залежить поведінка кнопок, мусить бути на
 * екрані — і кожною з шести мов, якими говорить сайт.
 */
describe("шапка показує, хто увійшов", () => {
  const shell = readFileSync(join(APP, "components", "PublicShell.tsx"), "utf-8");
  const account = readFileSync(join(APP, "components", "PublicAccount.tsx"), "utf-8");

  it("обидва пункти написані шістьма мовами", () => {
    for (const name of ["CABINET", "SIGN_OUT"]) {
      const block = shell.slice(shell.indexOf(`const ${name}`));
      const map = block.slice(0, block.indexOf("};"));
      for (const locale of ["en", "de", "es", "fr", "ru", "uk"]) {
        expect(map, `${name}/${locale}`).toContain(`${locale}:`);
      }
    }
  });

  it("куди веде кабінет — вирішує та сама функція, що й після входу", () => {
    // Друге місце з цим правилом розійшлося б із формою входу: саме так
    // вихід із адмінки колись приводив нову людину на службовий екран.
    expect(account).toContain("landingFor(");
    expect(account).not.toContain('"/admin"');
  });

  it("невідома людина — це просто «Увійти», без повідомлень про помилку", () => {
    // 401, протухла сесія й вимкнений API виглядають однаково: публічна
    // сторінка не стає гіршою від того, що кабінет недоступний.
    expect(account).toContain(".catch(() => undefined)");
    expect(account).toContain("labels.signIn");
  });
});

/**
 * Звіт не показує клієнтові відбитків двигуна.
 *
 * `config 0f392cf56528 · scoring c6a1c3fd43d8 · detector ab21c13febe8` —
 * наш інструмент звірки двох прогонів, а не факт про сайт. Читач із
 * нього не дізнається нічого й діяти на нього не може. Порівняння
 * версій між аудитами робить звіт історії — там воно й лишається.
 */
describe("екран звіту говорить про сайт, а не про двигун", () => {
  it("рядка з відбитками версій на екрані немає", () => {
    const view = readFileSync(join(APP, "components", "AuditResultView.tsx"), "utf-8");
    expect(view).not.toContain("engine_versions");
    expect(view).not.toContain("result.versions");
  });

  it("ключа каталогу теж немає — жодною мовою", () => {
    const dictionary = readFileSync(join(APP, "lib", "i18n.ts"), "utf-8");
    expect(dictionary).not.toContain('"result.versions"');
  });
});

/**
 * Внутрішня кухня прогону не тече на екран клієнта.
 *
 * Клас, який уже двічі доводилось прибирати вручну: відбитки двигуна
 * у звіті, версія набору промптів і назви моделей на екрані
 * присутності, сирі `completed` / `natural` замість підписів каталогу.
 * Спільне в них одне — читач не дізнається з них нічого й діяти на них
 * не може, а мовою кабінету вони не говорять узагалі.
 *
 * Службові екрани команди (`/admin`) під це правило не підпадають: там
 * технічна деталь і є предметом.
 */
describe("клієнтські екрани не показують службових ідентифікаторів", () => {
  const CLIENT = [
    ["присутність", join(APP, "(product)", "app", "presence", "page.tsx")],
    ["звіт", join(APP, "components", "AuditResultView.tsx")],
    ["присутність гостя", join(APP, "components", "GuestPresence.tsx")],
  ] as const;

  it("сирих значень бази в розмітці немає", () => {
    for (const [label, path] of CLIENT) {
      const source = readFileSync(path, "utf-8");
      // Стан і режим мають підписи в каталозі — саме вони й малюються.
      // `$` перед дужкою — це підстановка в ключ каталогу
      // (`status.${run.status}`), а не виведення значення на екран.
      expect(source, `${label}: сирий статус`).not.toMatch(
        /(?<!\$)\{\s*run\.status\s*\}/,
      );
      expect(source, `${label}: сирий режим`).not.toMatch(/(?<!\$)\{\s*o\.mode\s*\}/);
    }
  });

  it("відбитків версій і назв моделей на екрані немає", () => {
    for (const [label, path] of CLIENT) {
      const source = readFileSync(path, "utf-8");
      for (const leak of ["prompt_set_version", "engine_versions", "policy_snapshot"]) {
        expect(source, `${label}: ${leak}`).not.toContain(leak);
      }
      expect(source, `${label}: перелік моделей`).not.toMatch(/Array\.from\(models\)/);
    }
  });
});
