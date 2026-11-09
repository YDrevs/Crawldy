import { describe, expect, it } from "vitest";

import { localPath } from "./local-path";

const BACKSLASH = String.fromCharCode(92);
const TAB = String.fromCharCode(9);
const NEWLINE = String.fromCharCode(10);

describe("localPath — лише власні шляхи", () => {
  it("пропускає звичайні шляхи без змін", () => {
    for (const ok of ["/", "/app", "/checkout?offer=pack", "/admin/payment#x", "/r/abc?lang=uk"]) {
      expect(localPath(ok), ok).toBe(ok);
    }
  });

  it("відкидає чужі адреси й обхідні форми", () => {
    for (const hostile of [
      "https://evil.example",
      "//evil.example",
      `/${BACKSLASH}evil.example`,
      `/${BACKSLASH}/evil.example`,
      `${BACKSLASH}${BACKSLASH}evil.example`,
      `/${TAB}/evil.example`,
      `/${NEWLINE}/evil.example`,
      "javascript:alert(1)",
      "evil.example",
      "",
      null,
      undefined,
    ]) {
      expect(localPath(hostile), JSON.stringify(hostile)).toBeNull();
    }
  });
});
