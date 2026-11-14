import { describe, expect, it } from "vitest";
import { formatCount, formatDuration } from "../format";

describe("formatCount", () => {
  it("shows small numbers verbatim", () => {
    expect(formatCount(0)).toBe("0");
    expect(formatCount(999)).toBe("999");
  });

  it("abbreviates thousands and millions", () => {
    expect(formatCount(1000)).toBe("1k");
    expect(formatCount(12_500)).toBe("12.5k");
    expect(formatCount(2_000_000)).toBe("2.0M");
  });

  it("renders a dash for nullish input", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatCount(undefined)).toBe("—");
  });
});

describe("formatDuration", () => {
  it("returns a dash when either endpoint is missing", () => {
    expect(formatDuration(null, "2026-01-01T00:00:01Z")).toBe("—");
    expect(formatDuration("2026-01-01T00:00:00Z", null)).toBe("—");
  });

  it("formats sub-second and second ranges", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:00.250Z")).toBe("250ms");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:01.200Z")).toBe("1.2s");
  });

  it("formats minute ranges", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:02:05Z")).toBe("2m 5s");
  });

  // Regression: rounded seconds must carry into the next minute, never "1m 60s".
  // 119,500 ms and 179,500 ms fail on the old implementation ("1m 60s" / "2m 60s").
  it.each([
    ["2026-01-01T00:01:59.499Z", "1m 59s"],
    ["2026-01-01T00:01:59.500Z", "2m 0s"],
    ["2026-01-01T00:02:00.000Z", "2m 0s"],
    ["2026-01-01T00:02:59.500Z", "3m 0s"],
  ])("carries rounded seconds into the next minute: %s -> %s", (end, expected) => {
    expect(formatDuration("2026-01-01T00:00:00Z", end)).toBe(expected);
  });
});
