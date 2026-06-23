import { describe, expect, it } from "vitest";
import { nodeConfigSchemas } from "../validators";

describe("conditionalColumn schema", () => {
  const schema = nodeConfigSchemas.conditionalColumn;

  it("accepts a numeric rule value (e.g. line_total >= 5000)", () => {
    const result = schema.safeParse({
      new_column: "revenue_tier",
      default: "low",
      rules: [{ column: "line_total", operator: ">=", value: 5000, result: "high" }],
    });
    expect(result.success).toBe(true);
  });

  it("still accepts a legacy flat rule (string value)", () => {
    const result = schema.safeParse({
      new_column: "flag",
      rules: [{ column: "status", operator: "==", value: "active", result: "yes" }],
    });
    expect(result.success).toBe(true);
  });

  it("accepts a rule with multiple AND/OR conditions", () => {
    const result = schema.safeParse({
      new_column: "segment",
      default: "other",
      rules: [
        {
          match: "all",
          conditions: [
            { column: "age", operator: ">=", value: 18 },
            { column: "country", operator: "==", value: "US" },
          ],
          result: "us_adult",
        },
      ],
    });
    expect(result.success).toBe(true);
  });

  it("rejects a rule with neither conditions nor a legacy column", () => {
    const result = schema.safeParse({
      new_column: "segment",
      rules: [{ result: "x" }],
    });
    expect(result.success).toBe(false);
  });
});
