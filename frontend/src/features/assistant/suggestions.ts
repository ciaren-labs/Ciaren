import type { Dataset } from "@/features/datasets/types";
import type { Mode } from "./api";

const NUMERIC = ["integer", "float"];
const isKey = (name: string) => /(^|_)id$/i.test(name);

/**
 * Up to two prompts from the dataset schema plus examples of what the assistant can
 * build; nothing is sent until the user submits.
 */
export function suggestedPrompts({
  mode,
  dataset,
  target,
  training,
  joined,
  ml,
}: {
  mode: Mode;
  dataset?: Dataset;
  target?: string;
  training: boolean;
  joined: boolean;
  /** Machine learning is enabled, so training examples can run. */
  ml: boolean;
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
  const fromSchema = [
    nullable && `Remove rows where ${nullable.name} is empty`,
    numeric && `Sort by ${numeric.name}`,
  ].filter((p): p is string => !!p);
  return [
    ...fromSchema.slice(0, 2),
    "Join orders with customers and aggregate revenue by month",
    "Encode categories and scale numeric features",
    ...(ml ? ["Train a random forest with cross-validation and add charts"] : []),
  ];
}
