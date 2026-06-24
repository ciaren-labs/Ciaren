// Pure helpers for presenting ML node metrics in the run view. Kept separate from
// the React panel so the parsing is unit-tested directly.

/** A confusion matrix flattened by mlEvaluate as cm_true{i}_pred{j} keys. */
export interface ConfusionMatrix {
  size: number;
  /** matrix[trueIdx][predIdx] = count. */
  matrix: number[][];
}

const CM_KEY = /^cm_true(\d+)_pred(\d+)$/;

/**
 * Split a flat ml_metrics map into ordinary scalar metrics and (if present) a
 * confusion matrix reconstructed from its cm_true{i}_pred{j} entries.
 */
export function splitMetrics(metrics: Record<string, number> | null | undefined): {
  scalars: [string, number][];
  confusion: ConfusionMatrix | null;
} {
  const scalars: [string, number][] = [];
  const cells: { i: number; j: number; v: number }[] = [];
  for (const [key, value] of Object.entries(metrics ?? {})) {
    const m = CM_KEY.exec(key);
    if (m) {
      cells.push({ i: Number(m[1]), j: Number(m[2]), v: value });
    } else {
      scalars.push([key, value]);
    }
  }
  if (cells.length === 0) return { scalars, confusion: null };

  const size = Math.max(...cells.map((c) => Math.max(c.i, c.j))) + 1;
  const matrix = Array.from({ length: size }, () => Array.from({ length: size }, () => 0));
  for (const { i, j, v } of cells) matrix[i][j] = v;
  return { scalars, confusion: { size, matrix } };
}

/** Friendlier labels for common metric keys; unknown keys are shown as-is. */
const METRIC_LABELS: Record<string, string> = {
  accuracy: "Accuracy",
  precision: "Precision",
  recall: "Recall",
  f1: "F1",
  roc_auc: "ROC-AUC",
  rmse: "RMSE",
  mae: "MAE",
  r2: "R²",
  mape: "MAPE",
  residual_std: "Residual std",
  silhouette: "Silhouette",
  davies_bouldin: "Davies-Bouldin",
  inertia: "Inertia",
  explained_variance: "Explained variance",
  cv_mean: "CV mean",
  train_accuracy: "Train accuracy",
  train_f1_weighted: "Train F1 (weighted)",
  train_r2: "Train R²",
  train_rmse: "Train RMSE",
  train_mae: "Train MAE",
};

export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key;
}

/** Round a metric for display: integers stay whole, others to 4 sig-ish digits. */
export function formatMetric(value: number): string {
  if (Number.isInteger(value)) return String(value);
  if (Math.abs(value) >= 1000) return value.toFixed(0);
  return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}
