/**
 * Блок «фактична присутність» називає моделі даними, а не текстом.
 *
 * Назва моделі, зашита в копію, розійшлася б із продуктом мовчки й
 * одразу в шести мовах: саме так на сторінці могло б лишитися «GPT-5.1»,
 * виведений із ChatGPT ще в березні. Тому тут стережеться рівно це —
 * жодної назви моделі в локалізованому тексті, а самі назви приходять
 * із того самого джерела, що виконує прогін.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PUBLIC_SITE_LOCALES } from "../lib/i18n";

const DIR = join(process.cwd(), "app", "content", "ai-visibility");

function content(locale: string): string {
  return readFileSync(join(DIR, `${locale}.tsx`), "utf8");
}

/** Назви моделей, які НЕ сміють зʼявитися в копії жодної мови. */
const MODEL_NAMES =
  /sonnet|haiku|opus|gpt-\d|luna|terra|\bsol\b|gemini-\d|sonar|claude-\d/i;

describe("Actual AI Presence: моделі — дані, а не копія", () => {
  it("блок присутній у всіх шести мовах і рендерить моделі компонентом", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const src = content(locale);
      expect(src, `${locale}: немає <PresenceModels>`).toContain(
        "<PresenceModels",
      );
      expect(src, `${locale}: компонент не імпортовано`).toContain(
        'from "../../components/PresenceModels"',
      );
    }
  });

  it("кожна мова має обидва пояснювальні абзаци", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const src = content(locale);
      expect(src, `${locale}: немає intro`).toMatch(/intro=\{"[^"]{40,}"\}/);
      expect(src, `${locale}: немає note`).toMatch(/note=\{"[^"]{60,}"\}/);
    }
  });

  it("жодна назва моделі не зашита в локалізовану копію", () => {
    for (const locale of PUBLIC_SITE_LOCALES) {
      const src = content(locale);
      expect(
        MODEL_NAMES.test(src),
        `${locale}: у копії зашита назва моделі`,
      ).toBe(false);
    }
  });

  it("назви беруться з конфігурації прогону, без кешу", () => {
    const component = readFileSync(
      join(process.cwd(), "app", "components", "PresenceModels.tsx"),
      "utf8",
    );
    // Той самий ендпойнт, що проєктує політику присутності.
    expect(component).toContain("/v1/presence/models");
    // Без кешу — інакше зміна моделі не доїхала б до сторінки.
    expect(component).toContain('cache: "no-store"');
    // Публічні назви платформ фіксовані, назви моделей — ні.
    expect(component).toContain('label: "Claude"');
    expect(component).toContain('label: "ChatGPT"');
    expect(component).toContain('label: "Gemini"');
    expect(component).toContain('label: "Perplexity"');
    expect(
      MODEL_NAMES.test(component.replace(/\/\*[\s\S]*?\*\//g, "")),
      "у компоненті зашита назва моделі",
    ).toBe(false);
  });
});
