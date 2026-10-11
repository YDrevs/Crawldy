/**
 * Присутність із самої лише адреси: ланка від покупки до прогону.
 *
 * Рішення власника 2026-09-06: бренд, категорія й місто виводяться з
 * аудиту й показуються з можливістю змінити. Тут перевіряється, що обидва
 * входи — гостьовий екран після оплати й форма кабінету — справді
 * користуються підстановкою, а рядки блоку існують усіма шістьма мовами
 * гостьового екрана.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { translate } from "./i18n";

const APP = join(__dirname, "..");

function source(...parts: string[]): string {
  return readFileSync(join(APP, ...parts), "utf-8").replace(/\r\n/g, "\n");
}

const LOCALES = ["en", "uk", "de", "es", "fr", "ru"] as const;
const KEYS = [
  "free.presence.title",
  "free.presence.lead",
  "free.presence.brand",
  "free.presence.aliases",
  "free.presence.category",
  "free.presence.location",
  "free.presence.run",
  "free.presence.running",
  "free.presence.noCredit",
  "free.presence.failed",
  "free.presence.source.schema",
  "free.presence.source.title",
  "free.presence.source.domain",
  "free.presence.source.site",
];

describe("гостьовий екран після оплати", () => {
  it("оплачений звіт показує блок присутності саме для цього аудиту", () => {
    const page = source("(product)", "result", "page.tsx");
    expect(page).toContain("<GuestPresence auditId={result.audit_id} />");
  });

  it("блок бере факти з сервера й дозволяє їх змінити перед запуском", () => {
    const block = source("components", "GuestPresence.tsx");
    expect(block).toContain("readGuestPresence(auditId)");
    expect(block).toContain("startGuestPresence(auditId");
    for (const field of ["brand", "aliases", "category", "location"]) {
      expect(block, field).toContain(`update("${field}", e.target.value)`);
    }
    // Змінене людиною не перезаписується підстановкою.
    expect(block).toContain("if (!touched)");
    // Джерело кожного факту показується підписом.
    expect(block).toContain("free.presence.source.");
  });

  it("рядки блоку є всіма шістьма мовами і не падають в англійську", () => {
    for (const locale of LOCALES) {
      for (const key of KEYS) {
        const text = translate(locale, key);
        expect(text, `${locale}/${key}`).not.toBe(key);
        if (locale !== "en" && key !== "free.presence.title") {
          expect(text, `${locale}/${key}`).not.toBe(translate("en", key));
        }
      }
    }
  });
});

describe("форма кабінету", () => {
  const page = source("(product)", "app", "presence", "page.tsx");

  it("просить місто й варіанти написання, а не лише бренд і категорію", () => {
    for (const field of ["brand", "aliases", "category", "location"]) {
      expect(page, field).toContain(`["${field}", "presence.form.${field}"]`);
    }
    expect(page).toContain("location: form.location.trim() || null");
    expect(page).toContain("brand_aliases: form.aliases");
  });

  it("підставляє факти з аудиту, щойно введена адреса, і лише в порожні поля", () => {
    expect(page).toContain("suggestPresence(url)");
    expect(page).toContain('onBlur={field === "url" ? () => void prefill(form.url) : undefined}');
    expect(page).toContain("brand: prev.brand || facts.brand");
    expect(page).toContain('location: prev.location || (facts.location ?? "")');
  });

  it("підписи форми є обома мовами кабінету", () => {
    for (const key of ["presence.form.location", "presence.form.aliases", "presence.prefilled"]) {
      expect(translate("uk", key)).not.toBe(translate("en", key));
      expect(translate("en", key)).not.toBe(key);
    }
  });
});
