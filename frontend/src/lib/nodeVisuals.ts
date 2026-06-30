// Visual metadata for nodes: a lucide icon per node type and a colour theme
// per category. Kept separate from nodeCatalog (which is pure data) so the
// catalog has no React/icon dependency.

import {
  AlignLeft,
  Archive,
  ArrowRightLeft,
  Blocks,
  ArrowUpDown,
  BarChart3,
  BarChartBig,
  Binary,
  Boxes,
  Braces,
  Brain,
  BrainCircuit,
  CalendarClock,
  CalendarDays,
  Calculator,
  CaseSensitive,
  Code2,
  Columns3,
  CopyMinus,
  Database,
  DatabaseZap,
  Dices,
  Download,
  Droplets,
  Eraser,
  FileDown,
  FileSpreadsheet,
  FileText,
  Filter,
  FolderOpen,
  Gauge,
  GitBranch,
  GitMerge,
  Grid3x3,
  Hash,
  LayoutGrid,
  Layers,
  ListChecks,
  Replace,
  Rows3,
  Scaling,
  Scissors,
  ScatterChart,
  ShieldCheck,
  Shrink,
  Shuffle,
  Sheet,
  Sigma,
  Sparkles,
  Split,
  SquareSplitHorizontal,
  Tag,
  Tags,
  Target,
  Trash2,
  TrendingUp,
  Ungroup,
  type LucideIcon,
} from "lucide-react";
import type { NodeCategory } from "./nodeCatalog";

export const NODE_ICONS: Record<string, LucideIcon> = {
  fileInput: FileText,
  csvInput: FileText,
  excelInput: FileSpreadsheet,
  parquetInput: Boxes,
  jsonInput: Braces,
  textInput: AlignLeft,
  sqlInput: Database,
  storageInput: FolderOpen,
  dropNulls: Eraser,
  fillNulls: Droplets,
  dropColumns: Trash2,
  renameColumns: Tag,
  selectColumns: Columns3,
  combineColumns: GitMerge,
  coalesceColumns: Blocks,
  removeDuplicates: CopyMinus,
  filterRows: Filter,
  filterExpression: Filter,
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
  explodeRows: Rows3,
  splitColumn: Split,
  parseDates: CalendarDays,
  mapValues: ArrowRightLeft,
  windowFunction: Sigma,
  conditionalColumn: GitBranch,
  rollingAggregate: TrendingUp,
  rowDifference: ArrowUpDown,
  dateDifference: CalendarClock,
  trainTestSplit: SquareSplitHorizontal,
  scaleFeatures: Scaling,
  encodeCategories: Tags,
  selectFeatures: ListChecks,
  reduceDimensions: Shrink,
  mlTrainClassifier: BrainCircuit,
  mlTrainRegressor: BrainCircuit,
  mlTrainClustering: BrainCircuit,
  mlTrainForecaster: BrainCircuit,
  mlTrainDimReduction: BrainCircuit,
  mlPredict: Target,
  mlEvaluate: Gauge,
  featureImportance: BarChartBig,
  mlCrossValidate: Layers,
  pythonTransform: Code2,
  assertNotNull: ShieldCheck,
  assertUnique: ShieldCheck,
  assertValueRange: ShieldCheck,
  assertExpression: ShieldCheck,
  assertRowCount: Hash,
  assertValuesInSet: ShieldCheck,
  fileOutput: FileDown,
  csvOutput: FileDown,
  excelOutput: Sheet,
  parquetOutput: Archive,
  sqlOutput: DatabaseZap,
  storageOutput: Download,
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

export const CATEGORY_ICONS: Record<NodeCategory, LucideIcon> = {
  input: FolderOpen,
  clean: Sparkles,
  columns: Columns3,
  reshape: LayoutGrid,
  analytics: TrendingUp,
  quality: ShieldCheck,
  ml: Brain,
  output: Download,
  plugins: Blocks,
};

/** Theme used for plugin-contributed categories that aren't one of the built-in
 *  ones — keeps the palette/canvas from crashing on an unknown category. */
export const PLUGIN_CATEGORY_THEME: CategoryTheme = {
  badge: "bg-slate-500 text-white",
  card: "border-slate-200 bg-slate-50/60",
  ring: "ring-slate-400",
  text: "text-slate-700",
  dot: "bg-slate-500",
};

/** Icon for any category, falling back to a generic "plugin" icon for
 *  categories contributed by plugins that aren't built in. */
export function getCategoryIcon(category: string): LucideIcon {
  return CATEGORY_ICONS[category as NodeCategory] ?? Blocks;
}

/** Theme for any category, falling back to the neutral plugin theme. */
export function getCategoryTheme(category: string): CategoryTheme {
  return CATEGORY_THEME[category as NodeCategory] ?? PLUGIN_CATEGORY_THEME;
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
  quality: {
    badge: "bg-orange-500 text-white",
    card: "border-orange-200 bg-orange-50/60",
    ring: "ring-orange-400",
    text: "text-orange-700",
    dot: "bg-orange-500",
  },
  ml: {
    badge: "bg-purple-500 text-white",
    card: "border-purple-200 bg-purple-50/60",
    ring: "ring-purple-400",
    text: "text-purple-700",
    dot: "bg-purple-500",
  },
  output: {
    badge: "bg-amber-500 text-white",
    card: "border-amber-200 bg-amber-50/60",
    ring: "ring-amber-400",
    text: "text-amber-700",
    dot: "bg-amber-500",
  },
  plugins: PLUGIN_CATEGORY_THEME,
};
