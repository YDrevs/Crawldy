/**
 * Знак Crawldy веде на сайт із кожного екрана, де він є.
 *
 * У кабінеті він вів на `/app`, тобто на ту саму сторінку, з якої на
 * нього тиснуть, а на службовій — теж у кабінет: дороги назад на
 * публічний сайт не було взагалі. Мова береться з САЙТУ (остання
 * публічна сторінка), а не з профілю: профіль знає лише дві мови
 * кабінету, тож німець із /de повертався на англійську головну. Зашите
 * «/» — той самий клас помилки, що вже ловили на формі входу.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..");

function source(...parts: string[]): string {
  return readFileSync(join(APP, ...parts), "utf-8").replace(/\r\n/g, "\n");
}

describe("знак веде на сайт, а не всередину застосунку", () => {
  it("кабінет: посилання знака — мовна головна сайту", () => {
    const shell = source("components", "AppShell.tsx");
    expect(shell).toContain("publicHomeHref(site)");
    expect(shell).toContain("useSiteLocale(profileLocale)");
    // Знак більше не веде на головну кабінету: для неї є пункт «Огляд».
    expect(shell).not.toContain('<Link href="/app" className="rounded-md">');
    expect(shell).toContain('aria-label="Crawldy"');
  });

  it("службова сторінка: те саме, і мова сайту", () => {
    const layout = source("(product)", "admin", "layout.tsx");
    expect(layout).toContain("publicHomeHref(site)");
    expect(layout).toContain("useSiteLocale(me?.user?.locale)");
    // Дорога в кабінет лишилася окремим посиланням.
    expect(layout).toContain('href="/app"');
  });

  it("гостьові екрани вже вели на сайт — і ведуть далі", () => {
    // Вимога — про ГОСТЬОВИЙ ЕКРАН, а не про файл: оболонка технічних
    // станів переїхала в сусідній модуль, і знак у ній лишився тим самим
    // посиланням. Тому джерело екрана — обидва модулі, а поріг той самий.
    const result =
      source("(product)", "result", "page.tsx") +
      source("(product)", "result", "screens.tsx");
    expect((result.match(/publicHomeHref\(locale\)/g) ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it("жодна з цих сторінок не зашиває «/» замість мовної головної", () => {
    for (const file of [
      ["components", "AppShell.tsx"],
      ["(product)", "admin", "layout.tsx"],
    ]) {
      const text = source(...file);
      expect(text, file.join("/")).not.toMatch(/<Link\s+href="\/"[^>]*aria-label="Crawldy"/);
    }
  });
});
