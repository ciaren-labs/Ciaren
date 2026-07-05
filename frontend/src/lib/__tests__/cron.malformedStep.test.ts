// Regression: isValidCron() used to accept malformed step tokens — each
// member was split on "/" destructuring only two segments, so garbage after a
// second slash was silently ignored and only failed server-side (croniter).
import { describe, expect, it } from "vitest";
import { isValidCron } from "../cron";

describe("isValidCron malformed step tokens", () => {
  it("rejects a doubled step like */5/7", () => {
    expect(isValidCron("*/5/7 * * * *")).toBe(false);
  });

  it("rejects a trailing empty step like */", () => {
    // "*/".split("/") -> ["*", ""]; isInt("") is false, so this one IS caught —
    // but "1-5/2/9" is not.
    expect(isValidCron("0 9 1-5/2/9 * *")).toBe(false);
  });
});
