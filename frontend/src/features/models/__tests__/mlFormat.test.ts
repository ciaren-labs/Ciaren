import { describe, expect, it } from "vitest";
import { fmtMetric, headlineMetric, modelUri } from "../components/mlFormat";
import type { MlModelVersion } from "@/features/models/types";

describe("fmtMetric", () => {
  it("prints integers with no decimals", () => {
    expect(fmtMetric(3)).toBe("3");
    expect(fmtMetric(0)).toBe("0");
  });

  it("uses 4 decimals for small non-integer values", () => {
    expect(fmtMetric(0.973421)).toBe("0.9734");
  });

  it("switches to 0 decimals once the magnitude reaches 1000", () => {
    expect(fmtMetric(1234.56)).toBe("1235");
  });

  it("handles negative values by magnitude, not sign", () => {
    expect(fmtMetric(-1234.56)).toBe("-1235");
    expect(fmtMetric(-0.5)).toBe("-0.5000");
  });
});

describe("headlineMetric", () => {
  it("returns null for an empty metrics object", () => {
    expect(headlineMetric({})).toBeNull();
  });

  it("prefers the highest-priority known metric when several are present", () => {
    expect(headlineMetric({ silhouette: 0.5, train_accuracy: 0.9, cv_mean: 0.7 })).toEqual({
      key: "train_accuracy",
      value: 0.9,
    });
  });

  it("falls back to the first key when no priority metric is present", () => {
    expect(headlineMetric({ custom_metric: 42 })).toEqual({ key: "custom_metric", value: 42 });
  });
});

describe("modelUri", () => {
  const baseVersion: MlModelVersion = {
    version: "3",
    run_id: "r1",
    status: "READY",
    aliases: [],
    created: "2026-06-01T00:00:00+00:00",
    metrics: {},
    lineage: {},
  };

  it("uses the versioned URI when the version has no alias", () => {
    expect(modelUri("iris-model", baseVersion)).toBe("models:/iris-model/3");
  });

  it("prefers the first alias when the version has one or more", () => {
    const withAliases = { ...baseVersion, aliases: ["production", "champion"] };
    expect(modelUri("iris-model", withAliases)).toBe("models:/iris-model@production");
  });
});
