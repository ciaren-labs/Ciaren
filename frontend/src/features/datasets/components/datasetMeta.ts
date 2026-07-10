import { AlignLeft, Braces, Database, FileSpreadsheet, FileText } from "lucide-react";
import type { Dataset, DatasetSourceType } from "@/features/datasets/types";

/**
 * Version label for a dataset. ``latest_version`` is the current version number;
 * ``version_count`` is how many versions still exist. They only differ once older
 * versions have been deleted/purged (e.g. v5 is current but only 2 remain), so we
 * show just ``v5`` normally and append the kept-count only when it's informative.
 */
export function versionLabel(latest: number, count: number): string {
  return count < latest ? `v${latest} (${count} kept)` : `v${latest}`;
}

export type DatasetSortKey = "name" | "columns" | "versions" | "created";

export const DATASET_SORT: Record<DatasetSortKey, (d: Dataset) => string | number> = {
  name: (d) => d.name.toLowerCase(),
  columns: (d) => d.column_schema?.length ?? 0,
  versions: (d) => d.latest_version,
  created: (d) => d.created_at,
};

export const SOURCE_META: Record<DatasetSourceType, { icon: typeof FileText; tint: string }> = {
  csv: { icon: FileText, tint: "bg-emerald-500" },
  tsv: { icon: FileText, tint: "bg-teal-500" },
  excel: { icon: FileSpreadsheet, tint: "bg-green-600" },
  parquet: { icon: Database, tint: "bg-indigo-500" },
  json: { icon: Braces, tint: "bg-amber-500" },
  jsonl: { icon: Braces, tint: "bg-orange-500" },
  text: { icon: AlignLeft, tint: "bg-slate-500" },
};
