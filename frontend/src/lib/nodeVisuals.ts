// Visual metadata for nodes: a lucide icon per node type and a colour theme
// per category. Kept separate from nodeCatalog (which is pure data) so the
// catalog has no React/icon dependency.

import {
  Archive,
  ArrowRightLeft,
  ArrowUpDown,
  BarChart3,
  Binary,
  Boxes,
  CalendarClock,
  CalendarDays,
  Calculator,
  CaseSensitive,
  Columns3,
  CopyMinus,
  Database,
  DatabaseZap,
  Dices,
  Droplets,
  Eraser,
  FileDown,
  FileSpreadsheet,
  FileText,
  Filter,
  GitBranch,
  GitMerge,
  Grid3x3,
  Layers,
  Replace,
  Rows3,
  Scissors,
  ScatterChart,
  Shuffle,
  Sheet,
  Sigma,
  Split,
  Tag,
  Trash2,
  Ungroup,
  type LucideIcon,
} from "lucide-react";
import type { NodeCategory } from "./nodeCatalog";

export const NODE_ICONS: Record<string, LucideIcon> = {
  csvInput: FileText,
  excelInput: FileSpreadsheet,
  parquetInput: Boxes,
  sqlInput: Database,
  dropNulls: Eraser,
  fillNulls: Droplets,
  dropColumns: Trash2,
  renameColumns: Tag,
  selectColumns: Columns3,
  removeDuplicates: CopyMinus,
  filterRows: Filter,
  sortRows: ArrowUpDown,
  castDtypes: Shuffle,
  limitRows: Scissors,
  replaceValues: Replace,
  stringTransform: CaseSensitive,
  calculatedColumn: Calculator,
  groupByAggregate: Layers,
  join: GitMerge,
  concatRows: Rows3,
  sampleRows: Dices,
  removeOutliers: ScatterChart,
  roundNumbers: Binary,
  binColumn: BarChart3,
  extractDateParts: CalendarClock,
  unpivot: Ungroup,
  pivot: Grid3x3,
  splitColumn: Split,
  parseDates: CalendarDays,
  mapValues: ArrowRightLeft,
  windowFunction: Sigma,
  conditionalColumn: GitBranch,
  csvOutput: FileDown,
  excelOutput: Sheet,
  parquetOutput: Archive,
  sqlOutput: DatabaseZap,
};

export function getNodeIcon(type: string | undefined): LucideIcon {
  return (type && NODE_ICONS[type]) || Filter;
}

export interface CategoryTheme {
  /** Solid accent (icon badge background). */
  badge: string;
  /** Node card surface + border. */
  card: string;
  /** Selected-state ring colour. */
  ring: string;
  /** Small text/label accent. */
  text: string;
  /** Palette swatch dot. */
  dot: string;
}

export const CATEGORY_THEME: Record<NodeCategory, CategoryTheme> = {
  input: {
    badge: "bg-emerald-500 text-white",
    card: "border-emerald-200 bg-emerald-50/60",
    ring: "ring-emerald-400",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
  },
  clean: {
    badge: "bg-sky-500 text-white",
    card: "border-sky-200 bg-sky-50/60",
    ring: "ring-sky-400",
    text: "text-sky-700",
    dot: "bg-sky-500",
  },
  columns: {
    badge: "bg-indigo-500 text-white",
    card: "border-indigo-200 bg-indigo-50/60",
    ring: "ring-indigo-400",
    text: "text-indigo-700",
    dot: "bg-indigo-500",
  },
  reshape: {
    badge: "bg-violet-500 text-white",
    card: "border-violet-200 bg-violet-50/60",
    ring: "ring-violet-400",
    text: "text-violet-700",
    dot: "bg-violet-500",
  },
  analytics: {
    badge: "bg-fuchsia-500 text-white",
    card: "border-fuchsia-200 bg-fuchsia-50/60",
    ring: "ring-fuchsia-400",
    text: "text-fuchsia-700",
    dot: "bg-fuchsia-500",
  },
  output: {
    badge: "bg-amber-500 text-white",
    card: "border-amber-200 bg-amber-50/60",
    ring: "ring-amber-400",
    text: "text-amber-700",
    dot: "bg-amber-500",
  },
};
