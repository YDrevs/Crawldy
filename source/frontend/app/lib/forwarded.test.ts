import { describe, expect, it } from "vitest";

import { trustedForwardedFor, trustedProxyCount } from "./forwarded";

describe("trustedForwardedFor", () => {
  it("без довірених проксі не пересилає нічого", () => {
    expect(trustedForwardedFor("6.6.6.6", 0)).toBe("");
  });

  it("відкидає записи, які дописав клієнт", () => {
    expect(trustedForwardedFor("6.6.6.6, 203.0.113.7", 1)).toBe("203.0.113.7");
    expect(trustedForwardedFor("1.1.1.1, 2.2.2.2, 203.0.113.7, 10.0.0.2", 2)).toBe(
      "203.0.113.7, 10.0.0.2",
    );
  });

  it("короткий ланцюг — запит обійшов проксі, нічого не пересилаємо", () => {
    expect(trustedForwardedFor("203.0.113.7", 2)).toBe("");
    expect(trustedForwardedFor(null, 1)).toBe("");
  });
});

describe("trustedProxyCount", () => {
  it("читає лише розумні цілі", () => {
    expect(trustedProxyCount("1")).toBe(1);
    expect(trustedProxyCount(undefined)).toBe(0);
    expect(trustedProxyCount("-1")).toBe(0);
    expect(trustedProxyCount("abc")).toBe(0);
    expect(trustedProxyCount("99")).toBe(0);
  });
});
