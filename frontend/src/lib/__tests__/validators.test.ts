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

  it("still accepts a string rule value (e.g. status == active)", () => {
    const result = schema.safeParse({
      new_column: "flag",
      rules: [{ column: "status", operator: "==", value: "active", result: "yes" }],
    });
    expect(result.success).toBe(true);
  });
});
