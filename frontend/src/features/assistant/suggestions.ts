import type { Dataset } from "@/features/datasets/types";
import type { Mode } from "./api";

/** Capabilities the server can compile into a proposal without a provider-side plan. */
export const SUPPORTED = [
  "Keep the first N rows",
  "Sort by a column",
  "Filter rows on a value",
  "Remove rows with empty values",
  "Remove duplicate rows",
  "Select or drop columns",
  "Join two CSV inputs",
];

const NUMERIC = ["integer", "float"];
const isKey = (name: string) => /(^|_)id$/i.test(name);

/** Up to three prompts built from the dataset schema; nothing is sent until the user submits. */
export function suggestedPrompts({
  mode,
  dataset,
  target,
  training,
  joined,
}: {
  mode: Mode;
  dataset?: Dataset;
  target?: string;
  training: boolean;
  joined: boolean;
}): string[] {
  if (mode === "docs")
    return [
      "How do I export Polars code?",
      "How do I schedule a flow?",
      "How do parameters work?",
    ];
  if (mode === "diagnose")
    return ["Check the most recent failure", "Why are rows missing after the Join?"];
  if (training)
    return target ? [`Train a model to predict ${target}`] : [];
  if (joined) return ["Keep all rows from the left input"];
  const columns = dataset?.column_schema?.slice(0, 64) ?? [];
  const nullable = columns.find((c) =>
    dataset?.column_profile?.some((p) => p.name === c.name && p.null_count > 0),
  );
  const numeric = columns.find((c) => NUMERIC.includes(c.type) && !isKey(c.name));
  return [
    nullable && `Remove rows where ${nullable.name} is empty`,
    numeric && `Sort by ${numeric.name}`,
    "Remove duplicate rows",
    "Keep the first 100 rows",
  ]
    .filter((p): p is string => !!p)
    .slice(0, 3);
}
