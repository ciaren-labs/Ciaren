import type { MlModelVersion } from "@/features/models/types";

// Lower-is-better metric names (everything else is higher-is-better) so the
// leaderboard bars/highlights and "best" picks point the right way.
export const LOWER_IS_BETTER = /rmse|mae|mse|error|loss|inertia/i;
// Preference order for the single "headline" metric shown on summary cards.
export const HEADLINE_PRIORITY = [
  "train_f1_weighted",
  "train_accuracy",
  "train_r2",
  "explained_variance",
  "silhouette",
  "cv_mean",
];

export function fmtMetric(v: number): string {
  if (Number.isInteger(v)) return String(v);
  return Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(4);
}

export function headlineMetric(metrics: Record<string, number>): { key: string; value: number } | null {
  const keys = Object.keys(metrics);
  if (keys.length === 0) return null;
  const key = HEADLINE_PRIORITY.find((k) => k in metrics) ?? keys[0];
  return { key, value: metrics[key] };
}

/** Prefer the alias URI when the version carries one, else a versioned URI. */
export function modelUri(name: string, v: MlModelVersion): string {
  if (v.aliases.length) return `models:/${name}@${v.aliases[0]}`;
  return `models:/${name}/${v.version}`;
}
