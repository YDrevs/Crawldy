/**
 * Оболонка публічного сайту: підвал і верстка головної на вузькому екрані.
 *
 * Два дефекти, які тут стережуться, знайдені вимірюванням, а не оком:
 *
 * — головна давала 57px горизонтального переповнення на 320px, бо назва
 *   прикладу звіту стояла в `truncate` (`white-space: nowrap`), а
 *   мінімальна ширина flex-контейнера рахується з повної ширини
 *   нерозривного тексту незалежно від `min-width: 0`;
 * — заховати це можна було одним `overflow-x: hidden` на `body`, і саме
 *   цього тут не дозволено: переповнення має не існувати, а не бути
 *   невидимим.
 *
 * Самі числа міряє браузерна перевірка (`website-qa`); тут — те, що
 * можна стерегти статично, щоб правка не відкотилась мовчки.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..");

function read(path: string): string {
  return readFileSync(join(APP, path), "utf-8")
    .replace(/\r\n/g, "\n")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
}

describe("підвал: заголовки колонок відрізняються від посилань", () => {
  const shell = read("components/PublicShell.tsx");
  const column = shell.slice(shell.indexOf("function FooterColumn"));
  const heading = column.match(/<h2 className="([^"]+)"/)?.[1] ?? "";

  it("заголовок напівжирний, темний і без підкреслення", () => {
    expect(heading).toContain("font-semibold");
    expect(heading).toMatch(/text-primary|text-brand\b/);
    expect(heading).not.toContain("underline");
    expect(heading).not.toContain("text-muted");
  });

  it("регістр лишився великими літерами, відступ під заголовком більший за посилання", () => {
    expect(heading).toContain("uppercase");
    expect(column).toContain('<ul className="mt-4');
  });

  it("заголовок — не посилання, а посилання лишились звичайними", () => {
    expect(column).not.toMatch(/<h2[^>]*>\s*<Link/);
    expect(column).toContain('className="text-secondary hover:text-primary"');
  });

  it("колонок чотири — «Розробникам» і FAQ не повернулись", () => {
    // Четверта — «Правова інформація» (Legal Pack, §3): окрема група, а
    // не пункти всередині «Компанії». Дві перевірки, заради яких цей
    // пін і існує, лишаються ті самі.
    const rendered = shell.match(/<FooterColumn title=\{GROUP_TITLE\.(\w+)/g) ?? [];
    expect(rendered).toEqual([
      "<FooterColumn title={GROUP_TITLE.product",
      "<FooterColumn title={GROUP_TITLE.materials",
      "<FooterColumn title={GROUP_TITLE.company",
      "<FooterColumn title={GROUP_TITLE.legal",
    ]);
    expect(shell).not.toContain("GROUP_TITLE.developers[");
    expect(shell.toLowerCase()).not.toContain('href="/faq');
  });
});

describe("головна на вузькому екрані: переповнення не існує, а не сховане", () => {
  it("назва прикладу звіту переноситься до `sm`, а не стоїть у nowrap", () => {
    const preview = read("components/ScorePreview.tsx");
    const sample = preview.match(/<span className="([^"]*)">\s*\{t\.sample\}/)?.[1] ?? "";
    expect(sample).toContain("min-w-0");
    expect(sample).toContain("sm:truncate");
    expect(sample.split(/\s+/)).not.toContain("truncate");
  });

  it("бал і покриття переносяться, ряди напрямів стають у два рядки", () => {
    const preview = read("components/ScorePreview.tsx");
    expect(preview).toContain("flex flex-wrap items-start justify-between");
    expect(preview).toContain("grid-cols-[minmax(0,1fr)_2rem]");
    expect(preview).toContain("sm:grid-cols-[10rem_minmax(0,1fr)_2rem]");
  });

  it("жодного overflow-x: hidden на оболонці сторінки", () => {
    for (const path of [
      "globals.css",
      "tokens.css",
      "[[...path]]/layout.tsx",
      "components/PublicShell.tsx",
      "components/sections.tsx",
    ]) {
      const source = read(path);
      expect(source, path).not.toMatch(/overflow-x\s*:\s*(hidden|clip)/);
      expect(source, path).not.toMatch(/\boverflow-x-(hidden|clip)\b/);
    }
    // `overflow-hidden` на картці заради заокруглених кутів — законне
    // обрізання самого елемента; заборонене — на html, body чи main.
    for (const path of ["globals.css", "[[...path]]/layout.tsx"]) {
      const source = read(path);
      expect(source, path).not.toMatch(/(html|body|main)[^{]*\{[^}]*overflow(-x)?\s*:\s*(hidden|clip)/);
      expect(source, path).not.toMatch(/<(html|body|main)[^>]*overflow-(x-)?(hidden|clip)/);
    }
  });

  it("сітка героя не ховає вміст колонки", () => {
    const sections = read("components/sections.tsx");
    const hero = sections.slice(sections.indexOf("export function Hero"), sections.indexOf("export function Heading"));
    expect(hero).not.toContain("overflow");
    expect(hero).not.toContain("min-w-0");
  });
});
