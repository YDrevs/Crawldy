/**
 * Ідентичність провайдерів присутності: що показуємо і чого не робимо.
 *
 * Головні твердження: всі чотири провайдери названі офіційними назвами;
 * жоден не малюється згенерованим/трасованим логотипом; графічний асет
 * можливий лише для провайдера з отриманим дозволом і покладеним
 * ОФІЦІЙНИМ файлом; знак незалежності присутній обома мовами кабінету;
 * «Coming soon» не існує — всі чотири реалізовані.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  APPROVED_ASSETS,
  PROVIDER_API_LABELS,
  PROVIDER_LABELS,
} from "./ProviderMark";
import { COMPLETE_LOCALES } from "../lib/i18n";

const ROOT = join(__dirname, "..");

describe("ідентичність провайдерів", () => {
  it("усі чотири провайдери мають офіційні назви", () => {
    expect(Object.keys(PROVIDER_LABELS).sort()).toEqual(
      ["anthropic", "google", "openai", "perplexity"],
    );
    expect(PROVIDER_LABELS.openai).toContain("OpenAI");
    expect(PROVIDER_LABELS.anthropic).toContain("Claude");
    expect(PROVIDER_LABELS.perplexity).toContain("Perplexity");
    expect(PROVIDER_LABELS.google).toContain("Gemini");
  });

  it("підпис каже, що викликається API-продукт, а не споживчий застосунок", () => {
    for (const label of Object.values(PROVIDER_API_LABELS)) {
      expect(label).toMatch(/API/);
    }
  });

  it("жодного вбудованого чи згенерованого логотипа в компоненті", () => {
    const source = readFileSync(
      join(ROOT, "components", "ProviderMark.tsx"), "utf8",
    );
    // Згенерований логотип жив би inline: <svg> з path-даними.
    expect(source).not.toMatch(/<svg[\s>]/);
    expect(source).not.toMatch(/ d="M[\d.]/);
    // Асети підхоплюються лише з official-теки public/providers.
    expect(source).toContain("/providers/");
  });

  it("асети вимкнені, поки дозволи не отримані", () => {
    // Perplexity й Anthropic вимагають попередньої письмової згоди,
    // Google — дозволу Brand Resource Center; OpenAI-бейдж чекає на
    // завантаження власником з openai.com/brand. Порожньо — правильно.
    expect(APPROVED_ASSETS.size).toBe(0);
  });

  it("знак незалежності присутній КОЖНОЮ мовою кабінету", () => {
    // Раніше тут стояло `toBe(2)` — число мов кабінету на той момент.
    // Кабінет тепер шестимовний, і зашите число ловило б розширення
    // мов замість того, заради чого тест існує: знак незалежності не
    // сміє зникнути в жодній мові.
    const i18n = readFileSync(join(ROOT, "lib", "i18n.ts"), "utf8");
    const hits = i18n.match(/"presence\.marks"/g) ?? [];
    expect(hits.length).toBe(COMPLETE_LOCALES.length);
    expect(i18n).toContain("not affiliated with or endorsed");
    expect(i18n).toContain("не афілійований");
  });

  it("сторінка присутності показує знак і не обіцяє «coming soon»", () => {
    const page = readFileSync(
      join(ROOT, "(product)", "app", "presence", "page.tsx"), "utf8",
    );
    expect(page).toContain('t("presence.marks")');
    expect(page).toContain("ProviderMark");
    expect(page.toLowerCase()).not.toContain("coming soon");
    expect(page).not.toContain("незабаром");
  });
});
