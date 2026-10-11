/**
 * Порядок хуків — інваріант React, а не стиль.
 *
 * Умовний `return` перед хуком робить кількість хуків залежною від
 * стану: перший рендер виходить рано, другий рендерить усе — і React
 * падає з помилкою 310. Саме так зламалися кнопки «Придбати пакет» і
 * «Підписатися»: сторінка тарифу падала з наміром з адреси, а без нього
 * працювала, тож дефект не було видно доти, доки хтось не прийшов зі
 * сторінки цін. Цей тест шукає той самий клас помилки в клієнтських
 * компонентах статично: жоден хук тіла компонента не сміє стояти після
 * раннього `return`.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..");
const HOOK = /^\s*(?:const\s+[^=]+=\s*)?use[A-Z]\w*\(/;
const COMPONENT = /^(?:export\s+(?:default\s+)?)?function\s+([A-Z]\w*)\s*\(/;
const BRANCH = /^\s*(?:\}?\s*else\b|if\b|switch\b|for\b|while\b|try\b|catch\b|finally\b)/;
const RETURN = /\breturn\b/;
const OPENS_CALLBACK = /=>\s*\{?\s*$/;

function* files(dir: string): Generator<string> {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      yield* files(full);
    } else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) {
      yield full;
    }
  }
}

/**
 * Компоненти файлу, у яких хук на рівні тіла стоїть після раннього
 * `return`. Ранній return — це `return` у тілі компонента (глибина 1)
 * або всередині умовного блоку тіла (`if`/`else`, глибина 2). Return
 * усередині колбеків не рахується: блок, відкритий стрілкою чи
 * функцією, — не гілка компонента.
 */
export function violations(source: string): string[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const found: string[] = [];
  let component: string | null = null;
  const stack: string[] = []; // "component" | "branch" | "fn"
  let firstReturn: number | null = null;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    if (stack.length === 0) {
      const start = line.match(COMPONENT);
      if (start) {
        component = start[1]!;
        firstReturn = null;
      }
    }
    const depth = stack.length;
    if (component && depth === 1 && HOOK.test(line) && firstReturn !== null) {
      found.push(`${component}: хук у рядку ${i + 1} після return у рядку ${firstReturn}`);
    }
    const inBranch = depth === 1 || (depth === 2 && stack[1] === "branch");
    if (component && inBranch && RETURN.test(line) && !OPENS_CALLBACK.test(line)) {
      if (firstReturn === null) firstReturn = i + 1;
    }
    const kind = BRANCH.test(line) ? "branch" : depth === 0 && component ? "component" : "fn";
    for (const ch of line) {
      if (ch === "{") stack.push(kind);
      else if (ch === "}") {
        stack.pop();
        if (stack.length === 0) component = null;
      }
    }
  }
  return found;
}

describe("хуки не стоять після раннього return", () => {
  it("у жодному клієнтському компоненті", () => {
    const problems: string[] = [];
    for (const file of files(APP)) {
      const source = readFileSync(file, "utf-8");
      if (!source.includes("use client")) continue;
      for (const v of violations(source)) problems.push(`${file.replace(APP, "")} → ${v}`);
    }
    expect(problems).toEqual([]);
  });

  it("ловить саме той дефект, що зламав кнопки цін", () => {
    const broken = `
function BuyMore() {
  const [offers, setOffers] = useState(null);
  if (offers === null) return null;
  const buy = useCallback(() => {}, []);
  return <div />;
}`;
    expect(violations(broken)).toHaveLength(1);
    const fixed = `
function BuyMore() {
  const [offers, setOffers] = useState(null);
  const buy = useCallback(() => {
    if (!offers) return;
  }, [offers]);
  if (offers === null) return null;
  return <div />;
}`;
    expect(violations(fixed)).toEqual([]);
  });
});
