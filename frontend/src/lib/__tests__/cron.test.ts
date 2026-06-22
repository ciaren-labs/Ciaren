import { describe, expect, it } from "vitest";
import {
  buildCron,
  describeCron,
  isValidCron,
  parseCron,
  type CronModel,
} from "../cron";

const base: CronModel = {
  frequency: "daily",
  minute: 0,
  hour: 9,
  weekday: 1,
  monthday: 1,
  raw: "",
};

describe("buildCron", () => {
  it("builds hourly", () => {
    expect(buildCron({ ...base, frequency: "hourly", minute: 15 })).toBe("15 * * * *");
  });
  it("builds daily", () => {
    expect(buildCron({ ...base, frequency: "daily", minute: 30, hour: 14 })).toBe("30 14 * * *");
  });
  it("builds weekly", () => {
    expect(buildCron({ ...base, frequency: "weekly", minute: 0, hour: 8, weekday: 5 })).toBe(
      "0 8 * * 5",
    );
  });
  it("builds monthly", () => {
    expect(buildCron({ ...base, frequency: "monthly", minute: 0, hour: 6, monthday: 15 })).toBe(
      "0 6 15 * *",
    );
  });
  it("passes custom raw through trimmed", () => {
    expect(buildCron({ ...base, frequency: "custom", raw: "  */5 * * * *  " })).toBe("*/5 * * * *");
  });
});

describe("parseCron round-trips presets", () => {
  it.each([
    ["15 * * * *", "hourly"],
    ["30 14 * * *", "daily"],
    ["0 8 * * 5", "weekly"],
    ["0 6 15 * *", "monthly"],
  ])("parses %s as %s and rebuilds it", (expr, freq) => {
    const model = parseCron(expr);
    expect(model.frequency).toBe(freq);
    expect(buildCron(model)).toBe(expr);
  });

  it("falls back to custom for step syntax", () => {
    expect(parseCron("*/5 * * * *").frequency).toBe("custom");
  });
  it("falls back to custom for malformed input", () => {
    expect(parseCron("not a cron").frequency).toBe("custom");
  });
});

describe("isValidCron", () => {
  it.each(["0 9 * * *", "*/5 * * * *", "0 0 1 1 *", "0,30 * * * *", "0 9 * * 1-5"])(
    "accepts %s",
    (expr) => expect(isValidCron(expr)).toBe(true),
  );
  it.each(["", "0 9 * *", "60 9 * * *", "0 24 * * *", "0 9 32 * *", "0 9 * * 7", "abc"])(
    "rejects %s",
    (expr) => expect(isValidCron(expr)).toBe(false),
  );
});

describe("describeCron", () => {
  it("describes presets", () => {
    expect(describeCron("0 * * * *")).toBe("Every hour, on the hour");
    expect(describeCron("30 14 * * *")).toBe("Every day at 14:30");
    expect(describeCron("0 8 * * 1")).toBe("Every Monday at 08:00");
    expect(describeCron("0 6 15 * *")).toBe("On the 15th of each month at 06:00");
  });
  it("labels valid custom expressions", () => {
    expect(describeCron("*/5 * * * *")).toBe("Cron: */5 * * * *");
  });
  it("flags invalid expressions", () => {
    expect(describeCron("99 99 * * *")).toBe("Invalid cron expression");
  });
});
