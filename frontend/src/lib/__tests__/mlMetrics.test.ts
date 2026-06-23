import { describe, expect, it } from "vitest";
import { formatMetric, metricLabel, splitMetrics } from "../mlMetrics";

describe("splitMetrics", () => {
  it("separates scalar metrics from a confusion matrix", () => {
    const { scalars, confusion } = splitMetrics({
      accuracy: 0.9,
      f1: 0.88,
      cm_true0_pred0: 5,
      cm_true0_pred1: 1,
      cm_true1_pred0: 2,
      cm_true1_pred1: 7,
    });
    expect(Object.fromEntries(scalars)).toEqual({ accuracy: 0.9, f1: 0.88 });
    expect(confusion).toEqual({ size: 2, matrix: [[5, 1], [2, 7]] });
  });

  it("returns no confusion matrix when there are no cm_ keys", () => {
    const { scalars, confusion } = splitMetrics({ rmse: 1.2 });
    expect(confusion).toBeNull();
    expect(scalars).toEqual([["rmse", 1.2]]);
  });

  it("handles null/empty metrics", () => {
    expect(splitMetrics(null)).toEqual({ scalars: [], confusion: null });
    expect(splitMetrics(undefined)).toEqual({ scalars: [], confusion: null });
  });

  it("sizes the matrix from the largest index", () => {
    const { confusion } = splitMetrics({ cm_true2_pred0: 3 });
    expect(confusion?.size).toBe(3);
    expect(confusion?.matrix[2][0]).toBe(3);
  });
});

describe("metricLabel / formatMetric", () => {
  it("prettifies known keys and passes unknown ones through", () => {
    expect(metricLabel("roc_auc")).toBe("ROC-AUC");
    expect(metricLabel("custom_metric")).toBe("custom_metric");
  });

  it("formats integers and floats", () => {
    expect(formatMetric(5)).toBe("5");
    expect(formatMetric(0.123456)).toBe("0.1235");
    expect(formatMetric(2500.7)).toBe("2501");
  });
});
