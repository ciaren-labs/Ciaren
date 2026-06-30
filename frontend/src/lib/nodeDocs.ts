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
  fileInput: {
    summary: "Loads rows from an uploaded dataset to start the pipeline. Pick the file type in the node instead of choosing a separate input node per format.",
    fields: [
      { name: "File type", desc: "CSV, TSV, Excel, Parquet, JSON, JSON Lines, or text." },
      { name: "Dataset", desc: "Only datasets compatible with the selected file type are listed." },
      { name: "Version", desc: "Pin a dataset version so scheduled runs read the same data until you update it." },
    ],
    tips: [
      "Upload files on the Datasets page first.",
      "Changing the file type clears the selected dataset to prevent format mismatches.",
    ],
  },
  csvInput: INPUT_DOC("CSV"),
  excelInput: INPUT_DOC("Excel"),
  parquetInput: INPUT_DOC("Parquet"),
  jsonInput: INPUT_DOC("JSON"),
  textInput: INPUT_DOC("Text"),

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
    summary: "Keeps only the rows that match a condition. Rows that don't match are dropped.",
    fields: [
      { name: "Column", desc: "The column to test." },
      {
        name: "Operator",
        desc: "Comparison to apply: equals, not equals, greater/less than, between (range), in (list), contains / starts with / ends with (text), is null, is not null.",
      },
      {
        name: "Value",
        desc: "What to compare against. Not needed for 'is null' / 'is not null'. For 'in', enter comma-separated values. For 'between', two bound fields appear.",
      },
    ],
    example: "Column = country, Operator = in, Value = US, CA → keeps only US and Canadian rows.",
    tips: [
      "Chain multiple Filter Rows nodes to apply several conditions — rows must pass all of them.",
      "'is null' and 'is not null' need no value — they just check for missing data.",
    ],
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
      { name: "Column", desc: "A text column to transform." },
      {
        name: "Operation",
        desc: "Lowercase / Uppercase / Strip whitespace / Title Case / Capitalize / String length / Find & Replace / Pad to width.",
      },
    ],
    tips: [
      "Use 'Strip whitespace' before comparisons to avoid invisible-space mismatches.",
      "'String length' produces a numeric column counting characters per row.",
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
    summary: "Combines two tables side-by-side on matching key columns — equivalent to SQL JOIN.",
    fields: [
      { name: "Join type", desc: "Inner: only matched rows. Left: all left rows + matched right. Right: all right rows + matched left. Full outer: all rows from both sides." },
      { name: "Join on", desc: "The key column(s) that must match between the left and right inputs. Enable 'different names' if the key has a different name on each side." },
    ],
    tips: [
      "Connect the two sources to the 'left' and 'right' handles on the node.",
      "Use 'Left join' to keep all rows from the primary table even when there's no match in the lookup.",
    ],
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
    summary: "Compute a window/analytical function into a new column — equivalent to SQL window functions (OVER PARTITION BY).",
    fields: [
      {
        name: "Function",
        desc: "Ranking: row_number, rank, dense_rank, cumcount. Running totals: cumsum, cummax, cummin. Time-shifted: lag (previous row), lead (next row).",
      },
      { name: "Partition by", desc: "Reset the window per group — e.g. partition by region gives an independent running total per region." },
      { name: "Order by", desc: "Defines row order within each partition. Required for lag/lead and most ranking functions." },
      { name: "Target column", desc: "Source column for cumsum / cummax / cummin / lag / lead. Not needed for ranking functions." },
      { name: "New column name", desc: "Where the result is written." },
    ],
    example: "cumsum partitioned by region, ordered by date → running sales total that resets per region.",
    tips: [
      "Use 'rank' when you want gaps for ties (1, 1, 3), 'dense_rank' for no gaps (1, 1, 2).",
      "lag(n=1) gives you the previous row's value; lead(n=1) gives the next row's value.",
    ],
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

  filterExpression: {
    summary: "Keep rows where a boolean expression is true. Combine multiple conditions in one expression.",
    fields: [{ name: "Expression", desc: "A boolean expression; same syntax as Calculated Column." }],
    example: "amount > 100 and status == 'paid'",
    tips: ["Use Filter Rows for a simple single-column condition; use this when you need AND/OR across columns."],
  },
  combineColumns: {
    summary: "Join several columns into one text column with a separator (the inverse of Split Column).",
    fields: [
      { name: "Columns to combine", desc: "Joined left-to-right in this order." },
      { name: "New column", desc: "Where the combined text is written." },
      { name: "Separator", desc: "Text inserted between values (default a space)." },
    ],
    tips: ["Null cells become empty strings, so the separator's position is preserved."],
  },
  coalesceColumns: {
    summary: "Take the first non-null value across several columns into a new column.",
    fields: [
      { name: "Columns", desc: "Checked left-to-right; the first non-null wins." },
      { name: "New column", desc: "Where the result is written." },
    ],
    example: "phone_mobile, phone_home, phone_work → phone.",
  },
  explodeRows: {
    summary: "Expand a column into multiple rows — one per value. Other columns are repeated.",
    fields: [
      { name: "Column", desc: "The column to expand." },
      { name: "Delimiter", desc: "Split text on this delimiter first; leave empty to explode an existing list column." },
    ],
    example: "\"x;y;z\" with delimiter ';' → three rows.",
  },
  rollingAggregate: {
    summary: "Moving aggregate (mean/sum/min/max/std/median) over a window of N rows.",
    fields: [
      { name: "Target", desc: "The numeric column to aggregate." },
      { name: "Function", desc: "How to combine the rows in each window." },
      { name: "Window", desc: "Number of rows per window." },
      { name: "Order by", desc: "Orders rows within the window (e.g. a date)." },
      { name: "Partition by", desc: "Optional — restart the window within each group." },
    ],
    tips: ["Set Min periods to allow partial windows at the start; otherwise the first rows are null."],
  },
  rowDifference: {
    summary: "Difference or percent change between consecutive rows — deltas and growth rates.",
    fields: [
      { name: "Target", desc: "The numeric column to compare." },
      { name: "Method", desc: "Absolute difference or percent change." },
      { name: "Periods", desc: "How many rows back to compare against." },
      { name: "Order by / Partition by", desc: "Order rows (e.g. by date) and optionally compare within groups." },
    ],
  },
  dateDifference: {
    summary: "Difference between two date columns (end − start), in days, hours, minutes, seconds, or weeks.",
    fields: [
      { name: "Start / End date column", desc: "The two dates; the result is end − start." },
      { name: "Unit", desc: "The unit of the resulting number." },
      { name: "New column", desc: "Where the difference is written." },
    ],
    tips: ["Unparseable dates become null rather than failing the run."],
  },
  pythonTransform: {
    summary: "Runs custom Python against the incoming DataFrame and must return a DataFrame. Use it when a transformation is too specific for the built-in nodes.",
    fields: [
      { name: "Script", desc: "Write the body of transform(df). The variable df is the input table." },
    ],
    example: "df['margin'] = df['revenue'] - df['cost']\nreturn df",
    tips: [
      "Use pd with the pandas engine and pl with the polars engine; both are provided by FlowFrame.",
      "The script runs locally with your app process, so treat it like trusted code.",
    ],
  },
  assertValuesInSet: {
    summary: "Fail or warn when a column contains values outside an allowed set (a domain check).",
    fields: [
      { name: "Column", desc: "The column whose values are checked." },
      { name: "Allowed values", desc: "The permitted set; anything else is a violation." },
      { name: "On violation", desc: "Error stops the run; warn records the result and continues." },
    ],
    example: "status in {paid, pending, failed}.",
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

  storageInput: {
    summary: "Read a file (CSV, Excel, or Parquet) from S3, Azure Blob Storage, Google Cloud Storage, or a local folder.",
    fields: [
      { name: "Storage connection", desc: "The cloud storage or local folder connection to use." },
      { name: "File path", desc: "Path to the file within the bucket or folder (e.g. data/input.csv)." },
      { name: "Format", desc: "File format: CSV, Excel, or Parquet." },
    ],
  },

  storageOutput: {
    summary: "Write the result as a file (CSV, Excel, or Parquet) to S3, Azure Blob Storage, Google Cloud Storage, or a local folder.",
    fields: [
      { name: "Storage connection", desc: "The cloud storage or local folder connection to use." },
      { name: "Destination path", desc: "Where to write the file within the bucket or folder." },
      { name: "Format", desc: "File format: CSV, Excel, or Parquet." },
      { name: "If file exists", desc: "Overwrite the existing file, or fail with an error." },
    ],
  },

  fileOutput: {
    summary:
      "Write the result to a file. Pick the format (CSV, Excel, Parquet, JSON, or text) and a name; the output is saved as a reusable dataset you can download or feed into another flow.",
    fields: [
      { name: "File type", desc: "CSV, Excel, Parquet, JSON, or text." },
      { name: "Dataset name", desc: "Names the saved output dataset; re-running adds a new version." },
    ],
  },
  csvOutput: OUTPUT_DOC("CSV"),
  excelOutput: OUTPUT_DOC("Excel"),
  parquetOutput: OUTPUT_DOC("Parquet"),

  // ----- Machine learning -----
  trainTestSplit: {
    summary:
      "Splits rows into a training set and a test set. Train your model on one, measure it honestly on the other. Has two outputs: train and test.",
    fields: [
      { name: "Test size", desc: "Fraction held out for testing, e.g. 0.2 = 20% test." },
      { name: "Stratify by", desc: "Optional. Keep the same class balance in both splits (classification targets)." },
      { name: "Random seed", desc: "Required — the same seed always produces the same split." },
    ],
    tips: [
      "Wire the train output into Train Model, and the test output into Predict → Evaluate.",
      "Stratify on your target column for imbalanced classification data.",
    ],
  },
  scaleFeatures: {
    summary: "Puts numeric columns on a comparable scale so no single feature dominates by magnitude.",
    fields: [{ name: "Method", desc: "Standard (z-score), Min-max (0–1), or Robust (median/IQR, resists outliers)." }],
    tips: ["Helpful for distance- and gradient-based models (KNN, SVM, logistic regression)."],
  },
  encodeCategories: {
    summary: "Turns text categories into numbers a model can use.",
    fields: [
      { name: "Method", desc: "One-hot makes a 0/1 column per category; ordinal maps each to an integer." },
      { name: "Drop first", desc: "One-hot only: drop one category to avoid collinearity." },
    ],
  },
  selectFeatures: {
    summary: "Keeps the most useful columns and drops noise to simplify and speed up training.",
    fields: [
      { name: "Method", desc: "Variance threshold, correlation filter, or top-K by relevance to a target." },
      { name: "Threshold / K / Target", desc: "Shown depending on the chosen method." },
    ],
  },
  reduceDimensions: {
    summary: "Compresses many numeric columns into a few principal components (PCA) — handy for visualization or de-noising.",
    fields: [
      { name: "Components", desc: "A whole number of components, or a fraction (0–1) of variance to keep." },
      { name: "Columns", desc: "Optional. Empty means all numeric columns." },
    ],
  },
  mlTrainClassifier: {
    summary:
      "Fits a classification model (predicts a category) and logs it to MLflow. Preprocessing is bundled into the model so the same steps run at prediction time. Its single output is a model reference — wire it into Predict or Feature Importance.",
    fields: [
      { name: "Model", desc: "Pick a classification algorithm (e.g. Random Forest, Logistic Regression)." },
      { name: "Target", desc: "The category column to predict." },
      { name: "Features", desc: "Optional. Empty = every column except the target." },
      { name: "Advanced options", desc: "Cross-validation, preprocessing, and the full hyperparameter set." },
    ],
    tips: [
      "Feed it the train output of Train / Test Split.",
      "The seed is required so a run reproduces the same model.",
      "Wire the model output into Predict or Feature Importance.",
    ],
  },
  mlTrainRegressor: {
    summary:
      "Fits a regression model (predicts a number) and logs it to MLflow. Preprocessing is bundled in so the same steps run at prediction time. Its single output is a model reference.",
    fields: [
      { name: "Model", desc: "Pick a regression algorithm (e.g. Random Forest, Ridge, Linear)." },
      { name: "Target", desc: "The numeric column to predict." },
      { name: "Features", desc: "Optional. Empty = every column except the target." },
      { name: "Advanced options", desc: "Cross-validation, preprocessing, and hyperparameters." },
    ],
    tips: [
      "Feed it the train output of Train / Test Split.",
      "The seed is required so a run reproduces the same model.",
      "Wire the model output into Predict or Feature Importance.",
    ],
  },
  mlTrainClustering: {
    summary:
      "Groups rows into clusters (unsupervised — no target) and logs the model to MLflow. Its single output is a model reference.",
    fields: [
      { name: "Model", desc: "Pick a clustering algorithm (e.g. K-Means, DBSCAN)." },
      { name: "Features", desc: "Optional. Empty = all columns." },
      { name: "Advanced options", desc: "Preprocessing and hyperparameters (e.g. number of clusters)." },
    ],
    tips: [
      "No target column — clustering is unsupervised.",
      "The seed is required so a run reproduces the same model.",
    ],
  },
  mlTrainForecaster: {
    summary:
      "Trains a time-series forecasting model. Defined as a scaffold — forecasting models are coming soon, so this node isn't runnable yet.",
    fields: [
      { name: "Time column", desc: "The column that orders rows in time." },
      { name: "Target", desc: "The value to forecast." },
    ],
    tips: ["Forecasting models will appear here in a future release."],
  },
  mlTrainDimReduction: {
    summary:
      "Fits a dimensionality-reduction model (e.g. PCA) and logs it to MLflow. Its single output is a model reference. (For inline reduction, use the Reduce Dimensions node instead.)",
    fields: [
      { name: "Model", desc: "Pick a method (e.g. PCA)." },
      { name: "Features", desc: "Optional. Empty = all columns." },
      { name: "Advanced options", desc: "Preprocessing and hyperparameters (e.g. number of components)." },
    ],
    tips: ["The seed is required so a run reproduces the same model."],
  },
  mlPredict: {
    summary: "Scores rows with a trained model, adding a prediction column.",
    fields: [
      { name: "Model URI", desc: "Optional. Use a registry URI, or leave empty and connect the model wire." },
      { name: "Prediction column", desc: "Name for the output column." },
      { name: "Probability columns", desc: "Optional class probabilities (classifiers)." },
    ],
  },
  mlEvaluate: {
    summary: "Computes evaluation metrics from predictions and returns them as a metric/value table.",
    fields: [
      { name: "Task type", desc: "Classification, regression, or clustering." },
      { name: "True value / Prediction", desc: "The columns to compare." },
      { name: "Metrics", desc: "Optional. Empty uses a sensible default set for the task." },
    ],
  },
  featureImportance: {
    summary: "Ranks which features a trained model relied on most.",
    fields: [{ name: "Top N", desc: "Optional limit to the N most important features." }],
    tips: ["Connect the model output of Train Model. Works for tree and linear models (not SVM-rbf or KNN)."],
  },
  mlCrossValidate: {
    summary: "Estimates how well a model generalizes by scoring it across resampling folds. Returns one row per fold.",
    fields: [
      { name: "Model", desc: "The classification or regression model to evaluate." },
      { name: "Target column", desc: "The column the model learns to predict." },
      { name: "Strategy", desc: "K-Fold, Stratified, Shuffle, Time Series, Group, Repeated, or Leave-One-Out." },
      { name: "Folds / splits", desc: "How many folds to evaluate (ignored by Leave-One-Out)." },
      { name: "Scoring", desc: "Optional. Empty uses a sensible default set for the task." },
    ],
    tips: [
      "Use Stratified for imbalanced classes, Time Series for ordered data, and Group to keep a group within one fold.",
      "Preprocessing is refit inside each fold, so scores aren't inflated by leakage.",
    ],
  },
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
