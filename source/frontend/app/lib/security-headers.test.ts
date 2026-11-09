import { describe, expect, it } from "vitest";

import { securityHeaders } from "../../security-headers.mjs";

const byKey = (headers: { key: string; value: string }[]) =>
  Object.fromEntries(headers.map((h) => [h.key, h.value]));

describe("заголовки безпеки", () => {
  it("примусова CSP — лише директиви, що нічого не ламають", () => {
    const csp = byKey(securityHeaders({}))["Content-Security-Policy"];
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("form-action 'self'");
    // Джерела скриптів не обмежуються примусово, поки повну політику не
    // виміряно на живих сторінках (Paddle, Turnstile, інлайн Next).
    expect(csp).not.toContain("script-src");
  });

  it("повна політика спершу у звітному режимі й знає касу, челендж і API", () => {
    const report = byKey(securityHeaders({ apiUrl: "https://api.crawldy.ai" }))[
      "Content-Security-Policy-Report-Only"
    ];
    expect(report).toContain("script-src 'self'");
    expect(report).toContain("https://cdn.paddle.com");
    expect(report).toContain("https://challenges.cloudflare.com");
    expect(report).toContain("connect-src 'self' https://api.crawldy.ai");
  });

  it("HSTS лише коли його явно ввімкнено", () => {
    expect(byKey(securityHeaders({}))["Strict-Transport-Security"]).toBeUndefined();
    expect(byKey(securityHeaders({ hsts: true }))["Strict-Transport-Security"]).toBe(
      "max-age=31536000; includeSubDomains",
    );
  });

  it("попередні заголовки на місці", () => {
    const h = byKey(securityHeaders({}));
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["X-Frame-Options"]).toBe("DENY");
  });
});
