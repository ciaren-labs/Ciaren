// Plain-language documentation for each node type, shown in the sidebar's
// "Guide" tab. Kept in sync with the backend transformations in
// app/engine/registry.py — only document what is actually implemented.

export interface NodeDoc {
  summary: string;
  fields?: { name: string; desc: string }[];
  example?: string;
  tips?: string[];
}

const INPUT_DOC = (kind: string): NodeDoc => ({
  summary: `Loads rows from an uploaded ${kind} dataset to start the pipeline.`,
  fields: [{ name: "Dataset", desc: `Pick one of your uploaded ${kind} datasets. Only ${kind} datasets are listed.` }],
  tips: [
    "Upload files on the Datasets page first.",
    "An input node has no inputs — it's where a flow begins.",
  ],
});

const OUTPUT_DOC = (kind: string): NodeDoc => ({
  summary: `Writes the incoming table to a ${kind} file when the flow runs.`,
  fields: [{ name: "Output path", desc: "Optional. Leave empty to auto-generate a path under the run's output folder." }],
  tips: ["A flow needs at least one output node before it can run or export."],
});

export const NODE_DOCS: Record<string, NodeDoc> = {
  csvInput: INPUT_DOC("CSV"),
  excelInput: INPUT_DOC("Excel"),
  parquetInput: INPUT_DOC("Parquet"),

  dropNulls: {
    summary: "Removes rows that contain missing (null) values.",
    fields: [{ name: "Subset", desc: "Only check these columns for nulls. Empty means check every column." }],
    example: "Subset = [email] → drop rows where email is blank.",
  },
  fillNulls: {
    summary: "Replaces missing values with a fixed value.",
    fields: [
      { name: "Fill value", desc: "The value written into empty cells." },
      { name: "Columns", desc: "Limit filling to these columns. Empty means all columns." },
    ],
    example: "Fill value = 0, Columns = [score] → blanks in score become 0.",
  },
  dropColumns: {
    summary: "Removes the selected columns from the table.",
    fields: [{ name: "Columns to drop", desc: "These columns are deleted; everything else is kept." }],
  },
  selectColumns: {
    summary: "Keeps only the selected columns and drops the rest.",
    fields: [{ name: "Columns to keep", desc: "The output contains only these columns, in this order." }],
  },
  renameColumns: {
    summary: "Renames columns using an old → new mapping.",
    fields: [{ name: "Rename mapping", desc: "For each column you pick, type its new name." }],
    example: "qty → quantity, amt → amount.",
  },
  removeDuplicates: {
    summary: "Drops duplicate rows, keeping one copy.",
    fields: [
      { name: "Subset", desc: "Rows are duplicates when these columns match. Empty means compare whole rows." },
      { name: "Keep", desc: "Whether to keep the first or last of each duplicate group." },
    ],
  },
  filterRows: {
    summary: "Keeps only the rows that match a condition.",
    fields: [
      { name: "Column", desc: "The column to test." },
      { name: "Operator", desc: "How to compare — equals, greater-than, contains, is-null, etc." },
      { name: "Value", desc: "What to compare against (not needed for is-null / not-null)." },
    ],
    example: "age >= 18 keeps adults only.",
  },
  sortRows: {
    summary: "Reorders rows by one or more columns.",
    fields: [
      { name: "Sort by columns", desc: "Rows are ordered by these columns, in the order you add them." },
      { name: "Order", desc: "Ascending (A→Z, low→high) or descending." },
    ],
  },
  castDtypes: {
    summary: "Converts columns to a different data type.",
    fields: [{ name: "Casts", desc: "Pick a column and the type to convert it to (integer, float, boolean, string, datetime)." }],
    tips: ["Conversion fails at run time if a value can't be parsed — clean the column first if needed."],
  },
  limitRows: {
    summary: "Keeps only the first N rows.",
    fields: [{ name: "Number of rows", desc: "How many rows from the top to keep." }],
    tips: ["Handy for quick previews on large data — combine with Sort to get top-N."],
  },
  replaceValues: {
    summary: "Replaces a specific value in a column with another.",
    fields: [
      { name: "Column", desc: "The column to edit." },
      { name: "Replace", desc: "The exact value to find." },
      { name: "With", desc: "The value to substitute in." },
    ],
    example: "In country: replace USA with United States.",
  },
  stringTransform: {
    summary: "Applies a text operation to every value in a column.",
    fields: [
      { name: "Column", desc: "A text column." },
      { name: "Operation", desc: "lower, upper, strip (trim spaces), title or capitalize." },
    ],
  },
  calculatedColumn: {
    summary: "Adds a new column computed from a formula over existing columns.",
    fields: [
      { name: "New column name", desc: "The name of the column to create." },
      { name: "Formula", desc: "Start from a common template, or write a pandas expression by hand." },
    ],
    example: "total = price * quantity",
    tips: [
      "Reference columns by name; arithmetic (+ - * /) and comparisons (>, <, ==) work.",
      "Comparisons produce a true/false column — useful for flags.",
    ],
  },
  groupByAggregate: {
    summary: "Groups rows and summarizes each group.",
    fields: [
      { name: "Group by columns", desc: "Rows sharing the same values here form one group." },
      { name: "Aggregations", desc: "For each column, choose how to combine the group (sum, mean, count, min, max, …)." },
    ],
    example: "Group by region, sum of sales → one row per region.",
  },
  join: {
    summary: "Combines two tables side-by-side on matching key columns.",
    fields: [
      { name: "Join on", desc: "The key column(s) that must match between the left and right inputs." },
      { name: "How", desc: "inner = only matches; left/right = keep all of one side; outer = keep everything." },
    ],
    tips: ["Connect the two sources to the left and right handles on the node."],
  },
  concatRows: {
    summary: "Stacks two or more tables on top of each other (union of rows).",
    tips: [
      "Connect every table you want to stack to this node.",
      "Works best when the tables share the same columns.",
    ],
  },
  sampleRows: {
    summary: "Takes a random subset of rows.",
    fields: [
      { name: "Sample by", desc: "A fixed row count, or a fraction (0–1) of the table." },
      { name: "Random seed", desc: "Optional. Set it for the same sample every run." },
    ],
  },
  removeOutliers: {
    summary: "Detects outliers per column and either drops those rows or clips them to the bounds.",
    fields: [
      { name: "Columns", desc: "Numeric columns to evaluate." },
      { name: "Method", desc: "IQR (Q1/Q3 ± factor·IQR), z-score (± threshold·std), or percentile range." },
      { name: "Action", desc: "Drop offending rows, or clip values into the allowed range." },
    ],
    tips: ["No machine learning — these are transparent statistical rules that export to readable code."],
  },
  roundNumbers: {
    summary: "Rounds numeric columns to a fixed number of decimals.",
    fields: [{ name: "Decimals", desc: "0 rounds to whole numbers; 2 keeps cents, etc." }],
  },
  binColumn: {
    summary: "Buckets a numeric column into labeled bins, added as a new column.",
    fields: [
      { name: "Method", desc: "Equal-width splits the value range; quantile makes equally-sized groups." },
      { name: "Number of bins", desc: "How many buckets to create." },
    ],
  },
  extractDateParts: {
    summary: "Pulls calendar parts out of a date column into new columns.",
    fields: [
      { name: "Date column", desc: "A datetime or parseable date-string column." },
      { name: "Parts", desc: "Each selected part (year, month, …) becomes a column like date_year." },
    ],
  },
  unpivot: {
    summary: "Reshapes wide columns into long key/value rows (pandas melt).",
    fields: [
      { name: "Keep columns", desc: "Identifier columns repeated on every output row." },
      { name: "Unpivot columns", desc: "Columns folded into a variable/value pair. Empty = all the rest." },
    ],
    example: "Keep [id], unpivot [jan, feb] → rows of (id, variable, value).",
  },
  pivot: {
    summary: "Reshapes long rows into a wide aggregated table (pandas pivot_table).",
    fields: [
      { name: "Index", desc: "Columns that identify each output row." },
      { name: "Columns from", desc: "Distinct values here become new columns." },
      { name: "Values / Aggregation", desc: "The column to aggregate and how (sum, mean, …)." },
    ],
  },

  splitColumn: {
    summary: "Splits one text column into several columns by a delimiter or regex groups.",
    fields: [
      { name: "Column", desc: "The text column to split." },
      { name: "Split by", desc: "A literal delimiter, or a regex whose capture groups become columns." },
      { name: "New columns", desc: "Names for the resulting columns, in order." },
      { name: "Keep original", desc: "Whether the source column is retained." },
    ],
    example: "name = 'Ada Lovelace', delimiter ' ' → first = 'Ada', last = 'Lovelace'.",
  },
  parseDates: {
    summary: "Parses text columns into real datetimes so date operations work.",
    fields: [
      { name: "Columns", desc: "The text columns to parse." },
      { name: "Date format", desc: "Optional strptime format; leave empty to auto-detect." },
      { name: "On bad values", desc: "Coerce unparseable values to null, or raise an error." },
    ],
    tips: ["Pairs well with Extract Date Parts once the column is a datetime."],
  },
  mapValues: {
    summary: "Maps column values to new values via a lookup (CASE-WHEN-style).",
    fields: [
      { name: "Column", desc: "The column whose values are mapped." },
      { name: "New column", desc: "Optional. Empty overwrites the source column." },
      { name: "Mapping", desc: "Each listed value is replaced with its mapped value." },
      { name: "Default", desc: "Optional value for anything not in the mapping (otherwise kept as-is)." },
    ],
    example: "{'A': 'Pass', 'B': 'Pass'}, default 'Fail' → C becomes 'Fail'.",
  },

  windowFunction: {
    summary: "Compute a window function (rank, running total, lag/lead) into a new column.",
    fields: [
      { name: "Function", desc: "row_number, rank, dense_rank, cumcount, cumsum, cummax, cummin, lag, lead." },
      { name: "Partition by", desc: "Restart the window within each group (optional)." },
      { name: "Order by", desc: "Row order within each partition." },
      { name: "Target", desc: "Value column for cumsum/cummax/cummin/lag/lead." },
    ],
    example: "function cumsum, partition by region, order by date → a running total per region.",
    tips: ["Row order is preserved; the result is added as a new column."],
  },
  conditionalColumn: {
    summary: "Build a column from ordered if/elif/else rules (CASE-WHEN). First match wins.",
    fields: [
      { name: "New column", desc: "Where the result is written." },
      {
        name: "Rules",
        desc: "Each rule has one or more conditions (column + operator + value) combined with match ALL (AND) or ANY (OR) → result.",
      },
      { name: "Default", desc: "Value used when no rule matches." },
    ],
    example: "if age >= 18 AND country == 'US' → 'us_adult'; else 'other'.",
  },

  sqlInput: {
    summary: "Read rows live from a database (table or custom SQL) at run time.",
    fields: [
      { name: "Connection", desc: "A reusable connection from the Connections page." },
      { name: "Source", desc: "Pick a table, or write a custom SQL query." },
    ],
    tips: [
      "Scheduled runs re-read the source each time, so the data is always fresh.",
      "Passwords come from environment variables — never stored in the flow.",
    ],
  },
  sqlOutput: {
    summary: "Write the incoming table to a database table when the flow runs.",
    fields: [
      { name: "Connection", desc: "Where to write the result." },
      { name: "Target table", desc: "The destination table (or collection)." },
      { name: "If table exists", desc: "Replace, append, or fail." },
    ],
  },

  csvOutput: OUTPUT_DOC("CSV"),
  excelOutput: OUTPUT_DOC("Excel"),
  parquetOutput: OUTPUT_DOC("Parquet"),
};

export function getNodeDoc(type: string | undefined): NodeDoc | undefined {
  return type ? NODE_DOCS[type] : undefined;
}

// --- Calculated-column formula templates ------------------------------------

export interface ExpressionTemplate {
  label: string;
  description: string;
  /** Build the expression, using real upstream column names when available. */
  build: (columns: string[]) => string;
}

function pick(columns: string[], i: number, fallback: string): string {
  return columns[i] ?? fallback;
}

export const EXPRESSION_TEMPLATES: ExpressionTemplate[] = [
  {
    label: "Sum of two columns",
    description: "a + b",
    build: (c) => `${pick(c, 0, "col_a")} + ${pick(c, 1, "col_b")}`,
  },
  {
    label: "Difference",
    description: "a - b",
    build: (c) => `${pick(c, 0, "col_a")} - ${pick(c, 1, "col_b")}`,
  },
  {
    label: "Product",
    description: "a * b",
    build: (c) => `${pick(c, 0, "col_a")} * ${pick(c, 1, "col_b")}`,
  },
  {
    label: "Ratio as percent",
    description: "a / b * 100",
    build: (c) => `${pick(c, 0, "col_a")} / ${pick(c, 1, "col_b")} * 100`,
  },
  {
    label: "Average of two",
    description: "(a + b) / 2",
    build: (c) => `(${pick(c, 0, "col_a")} + ${pick(c, 1, "col_b")}) / 2`,
  },
  {
    label: "Threshold flag",
    description: "a > 0 (true/false column)",
    build: (c) => `${pick(c, 0, "col_a")} > 0`,
  },
];
