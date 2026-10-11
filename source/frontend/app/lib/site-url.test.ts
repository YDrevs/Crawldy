/**
 * Форма приймає адресу так, як її пишуть люди.
 *
 * Шість рівнозначних варіантів із журналу правок мусять нормалізуватися
 * в робочий URL; сміття мусить давати `null`, а не запускати аудит
 * неіснуючої адреси.
 */

import { describe, expect, it } from "vitest";

import { normalizeSiteUrl } from "./site-url";

describe("рівнозначні варіанти однієї адреси", () => {
  it.each([
    ["smartkp.com.ua", "https://smartkp.com.ua/"],
    ["www.smartkp.com.ua", "https://www.smartkp.com.ua/"],
    ["https://smartkp.com.ua", "https://smartkp.com.ua/"],
    ["https://www.smartkp.com.ua", "https://www.smartkp.com.ua/"],
    ["http://smartkp.com.ua", "http://smartkp.com.ua/"],
    ["http://www.smartkp.com.ua", "http://www.smartkp.com.ua/"],
  ])("%s → %s", (raw, normalized) => {
    expect(normalizeSiteUrl(raw)).toBe(normalized);
  });

  it("пробіли по краях не заважають", () => {
    expect(normalizeSiteUrl("  example.com  ")).toBe("https://example.com/");
  });

  it("шлях і порт переживають нормалізацію", () => {
    expect(normalizeSiteUrl("example.com/pricing")).toBe(
      "https://example.com/pricing",
    );
    expect(normalizeSiteUrl("example.com:8443")).toBe(
      "https://example.com:8443/",
    );
  });

  it("кирилічний домен нормалізується через punycode", () => {
    const normalized = normalizeSiteUrl("укр.укр");
    expect(normalized).toMatch(/^https:\/\/xn--/);
  });
});

describe("те, що адресою не є", () => {
  it.each([
    "",
    "   ",
    "abc",
    "localhost",
    "not a url",
    "http://",
    "https://",
    "ftp://example.com",
    "mailto:hi@example.com",
    "http://exa mple.com",
    "example..com",
    "-example.com",
  ])("«%s» → null", (raw) => {
    expect(normalizeSiteUrl(raw)).toBeNull();
  });
});
