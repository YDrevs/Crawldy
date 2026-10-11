/**
 * Помилки бекенда очима клієнта: слова, не коди.
 *
 * Захищає від регресії, спійманої наживо: гість із вичерпаною квотою
 * бачив на екрані «quota.exhausted». Правило одне — відомий код або
 * статус перекладається своїм реченням, усе невідоме падає в короткий
 * локалізований загальний текст і НІКОЛИ не показує сирого значення.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { translate } from "./i18n";
import { problemKey } from "./problem";

describe("механізму гостьової квоти більше не існує", () => {
  it("quota.exhausted не має власного перекладу — його прибрано, не перекладено", () => {
    // Превʼю необмежені: код більше не приходить із гостьового шляху,
    // а якби прийшов звідкись — упав би в загальне речення, не в сирий
    // рядок і не в запрошення створити акаунт.
    const key = problemKey(new ApiError(402, "quota.exhausted"));
    expect(key).toBe("problem.generic");
    for (const locale of ["en", "uk"] as const) {
      const text = translate(locale, key);
      expect(text).not.toContain("quota");
      expect(text.toLowerCase()).not.toContain("account");
      expect(text).not.toContain("акаунт");
    }
  });

  it("жодне речення каталогу не запрошує створити акаунт заради превʼю", () => {
    for (const locale of ["en", "uk"] as const) {
      for (const key of ["problem.generic", "problem.tooMany", "state.offline"]) {
        const text = translate(locale, key);
        expect(text).not.toContain("Create an account to run more");
        expect(text).not.toContain("Створіть акаунт, щоб запускати більше");
      }
    }
  });

  it("технічний ліміт частоти говорить про трафік", () => {
    expect(problemKey(new ApiError(429, "429"))).toBe("problem.tooMany");
    for (const locale of ["en", "uk"] as const) {
      const text = translate(locale, "problem.tooMany");
      expect(text.includes(" ")).toBe(true);
      expect(text).not.toContain("quota");
    }
  });
});

describe("невідоме не показується сирим", () => {
  it("невідомий крапковий код падає в загальний ключ", () => {
    const key = problemKey(new ApiError(400, "billing.mystery.reason"));
    expect(key).toBe("problem.generic");
    expect(key).not.toContain("mystery");
  });

  it("загальний текст обома мовами не містить сирого значення", () => {
    for (const locale of ["en", "uk"] as const) {
      const text = translate(locale, "problem.generic");
      expect(text).not.toContain("billing.mystery.reason");
      expect(text.includes(" ")).toBe(true);
    }
  });

  it("імʼя винятку теж не протікає", () => {
    expect(problemKey(new TypeError("fetch failed"))).toBe("problem.generic");
  });

  it("недосяжний бекенд не показує адресу API", () => {
    // ApiError(0, UNREACHABLE) несе URL бекенда — впасти він мусить у
    // локалізоване «сервер не відповідає», а не в рядок з адресою.
    const key = problemKey(
      new ApiError(0, "Backend is not responding (http://localhost:8000)."),
    );
    expect(key).toBe("state.offline");
    for (const locale of ["en", "uk"] as const) {
      expect(translate(locale, key)).not.toContain("localhost");
    }
  });

  it("контекстний 402 обирає своє речення", () => {
    const key = problemKey(new ApiError(402, "402"), {
      402: "presence.plan.noEntitlement",
    });
    expect(key).toBe("presence.plan.noEntitlement");
  });
});

describe("невдалий гостьовий запуск повертає керування формі", () => {
  // Закінчення рядків нормалізуються: у цього репозиторію
  // `core.autocrlf=true`, тож у робочій копії файл лежить із CRLF, а
  // збережений через редактор — із LF. Багаторядкове зіставлення без
  // нормалізації перевіряє спосіб checkout'у, а не код.
  const source = readFileSync(
    join(__dirname, "..", "(product)", "result", "page.tsx"),
    "utf-8",
  ).replace(/\r\n/g, "\n");

  it("автозапуск одноразовий: прапорець стає до старту й не скидається", () => {
    // Ефект охороняється `!autoStarted`, прапорець піднімається ДО
    // виклику — помилка не веде до другого автозапуску.
    expect(source).toContain("if (initialUrl && !autoStarted)");
    const guardAt = source.indexOf("setAutoStarted(true);");
    const startAt = source.indexOf("void start(initialUrl.trim());");
    expect(guardAt).toBeGreaterThan(-1);
    expect(startAt).toBeGreaterThan(guardAt);
    // Скидання прапорця немає ніде: одна невдача — нуль повторів.
    expect(source).not.toContain("setAutoStarted(false)");
  });

  it("помилка знімає busy і показує перекладений ключ, не message", () => {
    expect(source).toContain("setError(problemKey(problem));");
    expect(source).not.toContain("setError(problem instanceof Error");
    // Кнопка знову жива: форма повертається людині.
    expect(source.indexOf("setError(problemKey(problem));\n      setBusy(false);"))
      .toBeGreaterThan(-1);
  });
});
