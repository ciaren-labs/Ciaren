# SPDX-License-Identifier: AGPL-3.0-only
"""Presentational metadata for the built-in node catalog.

This used to live only in the frontend (``frontend/src/features/flows/editor/nodeCatalog.ts``).
Moving the label / category / default-config / description here makes the backend
the source of truth so it can serve a complete node catalog
(``GET /api/catalog/nodes``) — the frontend then renders what the backend (plus
installed plugins) reports instead of hard-coding it.

Handle topology is **not** duplicated here: it is derived from the transformation
classes (``input_handles`` / ``optional_input_handles`` / ``multi_input``) and
``node_kinds`` (output handles, model handles) by ``app.plugins.builtin``. This
module only holds the bits the engine does not already know.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Category id -> display label (UI palette grouping). Mirrors the frontend.
CATEGORY_LABELS: dict[str, str] = {
    "input": "Inputs",
    "clean": "Cleaning",
    "columns": "Columns",
    "reshape": "Reshape",
    "analytics": "Analytics",
    "quality": "Data Quality",
    "chart": "Charts",
    "ml": "Machine Learning",
    "output": "Outputs",
}

#: Stable palette ordering.
CATEGORY_ORDER: list[str] = [
    "input",
    "clean",
    "columns",
    "reshape",
    "analytics",
    "quality",
    "chart",
    "ml",
    "output",
]


@dataclass(frozen=True)
class NodeMeta:
    """Presentation for one node type (no handle topology — see module docstring)."""

    type: str
    label: str
    category: str
    description: str
    #: A *template* default config; copied per generated spec so callers can never
    #: mutate the shared dict.
    default_config: dict[str, Any] = field(default_factory=dict)


BUILTIN_NODE_META: tuple[NodeMeta, ...] = (
    # ----- Inputs -----
    NodeMeta(
        "fileInput",
        "File Input",
        "input",
        "Load rows from an uploaded dataset — choose the file type in the node.",
        {"dataset_id": "", "dataset_version": None, "format": "csv"},
    ),
    NodeMeta(
        "csvInput",
        "CSV Input",
        "input",
        "Load rows from an uploaded CSV dataset.",
        {"dataset_id": "", "dataset_version": None},
    ),
    NodeMeta(
        "excelInput",
        "Excel Input",
        "input",
        "Load rows from an uploaded Excel dataset.",
        {"dataset_id": "", "dataset_version": None},
    ),
    NodeMeta(
        "parquetInput",
        "Parquet Input",
        "input",
        "Load rows from an uploaded Parquet dataset.",
        {"dataset_id": "", "dataset_version": None},
    ),
    NodeMeta(
        "jsonInput",
        "JSON Input",
        "input",
        "Load records from an uploaded JSON dataset.",
        {"dataset_id": "", "dataset_version": None},
    ),
    NodeMeta(
        "textInput",
        "Text Input",
        "input",
        "Load lines from an uploaded text file (one row per line).",
        {"dataset_id": "", "dataset_version": None},
    ),
    NodeMeta(
        "sqlInput",
        "SQL Input",
        "input",
        "Read rows live from a database table or query.",
        {"connection_id": "", "mode": "table", "table": "", "schema": None, "query": ""},
    ),
    NodeMeta(
        "storageInput",
        "Storage Input",
        "input",
        "Read a file (CSV, Excel, Parquet) from S3, Azure Blob, GCS, or a local folder.",
        {"connection_id": "", "path": "", "format": "csv"},
    ),
    # ----- Cleaning -----
    NodeMeta("dropNulls", "Drop Nulls", "clean", "Drop rows containing null values.", {"subset": [], "how": "any"}),
    NodeMeta(
        "fillNulls",
        "Fill Nulls",
        "clean",
        "Replace null values with a fixed value.",
        {"strategy": "constant", "value": "", "columns": []},
    ),
    NodeMeta("removeDuplicates", "Remove Duplicates", "clean", "Drop duplicate rows.", {"subset": [], "keep": "first"}),
    NodeMeta(
        "filterRows",
        "Filter Rows",
        "clean",
        "Keep rows matching a condition.",
        {"column": "", "operator": "==", "value": ""},
    ),
    NodeMeta(
        "filterExpression",
        "Filter by Expression",
        "clean",
        "Keep rows where a boolean expression is true (e.g. amount > 100 and status == 'paid').",
        {"expression": ""},
    ),
    NodeMeta(
        "sortRows",
        "Sort Rows",
        "clean",
        "Sort rows by one or more columns.",
        {"columns": [], "ascending": True, "na_position": "last"},
    ),
    NodeMeta(
        "castDtypes",
        "Change Types",
        "clean",
        "Cast columns to a new data type.",
        {"casts": {}, "errors": "raise", "format": ""},
    ),
    NodeMeta("limitRows", "Limit Rows", "clean", "Keep only the first N rows.", {"n": 100, "offset": 0}),
    NodeMeta(
        "sampleRows",
        "Sample Rows",
        "clean",
        "Take a reproducible random sample of rows (seed required).",
        {"n": 100, "seed": 42},
    ),
    # ----- Columns -----
    NodeMeta("dropColumns", "Drop Columns", "columns", "Remove columns from the dataframe.", {"columns": []}),
    NodeMeta(
        "renameColumns", "Rename Columns", "columns", "Rename columns using an old -> new mapping.", {"mapping": {}}
    ),
    NodeMeta("selectColumns", "Select Columns", "columns", "Keep only the selected columns.", {"columns": []}),
    NodeMeta(
        "combineColumns",
        "Combine Columns",
        "columns",
        "Join several columns into one text column with a separator.",
        {"columns": [], "new_column": "", "separator": " ", "keep_original": True},
    ),
    NodeMeta(
        "coalesceColumns",
        "Coalesce Columns",
        "columns",
        "Take the first non-null value across several columns into a new column.",
        {"columns": [], "new_column": "", "keep_original": True},
    ),
    NodeMeta(
        "replaceValues",
        "Replace Values",
        "columns",
        "Replace values in a column.",
        {"column": "", "to_replace": "", "value": "", "regex": False},
    ),
    NodeMeta(
        "stringTransform",
        "String Transform",
        "columns",
        "Apply a string operation to a column.",
        {"column": "", "operation": "lower"},
    ),
    NodeMeta(
        "calculatedColumn",
        "Calculated Column",
        "columns",
        "Create a new column from an expression.",
        {"column_name": "", "expression": ""},
    ),
    NodeMeta(
        "splitColumn",
        "Split Column",
        "columns",
        "Split a text column into several columns by a delimiter or regex groups.",
        {"column": "", "mode": "delimiter", "delimiter": ",", "pattern": "", "into": [], "keep_original": True},
    ),
    NodeMeta(
        "mapValues",
        "Map Values",
        "columns",
        "Map column values via a lookup (CASE-WHEN), with an optional default.",
        {"column": "", "new_column": "", "mapping": {}, "default": "", "use_default": False},
    ),
    # ----- Reshape -----
    NodeMeta(
        "groupByAggregate",
        "Group By Aggregate",
        "reshape",
        "Group rows and aggregate columns.",
        {"group_by": [], "aggregations": {}},
    ),
    NodeMeta(
        "join", "Join / Merge", "reshape", "Join two dataframes (left + right inputs).", {"on": "", "how": "inner"}
    ),
    NodeMeta("concatRows", "Concat Rows", "reshape", "Stack multiple dataframes vertically.", {}),
    NodeMeta(
        "unpivot",
        "Unpivot / Melt",
        "reshape",
        "Reshape wide columns into long key/value rows.",
        {"id_vars": [], "value_vars": [], "var_name": "variable", "value_name": "value"},
    ),
    NodeMeta(
        "pivot",
        "Pivot Table",
        "reshape",
        "Reshape long rows into a wide aggregated table.",
        {"index": [], "columns": "", "values": "", "aggfunc": "sum"},
    ),
    NodeMeta(
        "explodeRows",
        "Split to Rows",
        "reshape",
        "Expand a delimited or list column into one row per value.",
        {"column": "", "delimiter": ","},
    ),
    # ----- Analytics -----
    NodeMeta(
        "removeOutliers",
        "Remove Outliers",
        "analytics",
        "Drop or clip statistical outliers (IQR / z-score / percentile).",
        {"columns": [], "method": "iqr", "action": "drop", "factor": 1.5, "threshold": 3, "lower": 1, "upper": 99},
    ),
    NodeMeta(
        "roundNumbers",
        "Round Numbers",
        "analytics",
        "Round numeric columns to a number of decimals.",
        {"columns": [], "decimals": 0},
    ),
    NodeMeta(
        "binColumn",
        "Bin Column",
        "analytics",
        "Bucket a numeric column into bins (equal-width or quantile).",
        {"column": "", "new_column": "", "method": "equalwidth", "bins": 4},
    ),
    NodeMeta(
        "extractDateParts",
        "Extract Date Parts",
        "analytics",
        "Add year/month/day/weekday/hour columns from a date column.",
        {"column": "", "parts": []},
    ),
    NodeMeta(
        "parseDates",
        "Parse Dates",
        "analytics",
        "Parse text columns into datetimes (optional format, coerce errors).",
        {"columns": [], "format": "", "errors": "coerce"},
    ),
    NodeMeta(
        "windowFunction",
        "Window Function",
        "analytics",
        "Rank, running total, or lag/lead over a partition and order.",
        {
            "function": "row_number",
            "partition_by": [],
            "order_by": [],
            "target": "",
            "offset": 1,
            "descending": False,
            "new_column": "",
        },
    ),
    NodeMeta(
        "conditionalColumn",
        "Conditional Column",
        "analytics",
        "Build a column from if/elif/else rules (CASE-WHEN).",
        {"new_column": "", "default": "", "rules": []},
    ),
    NodeMeta(
        "rollingAggregate",
        "Rolling Aggregate",
        "analytics",
        "Moving mean/sum/min/max/std/median over a window of N rows.",
        {
            "target": "",
            "function": "mean",
            "window": 3,
            "min_periods": None,
            "partition_by": [],
            "order_by": [],
            "descending": False,
            "new_column": "",
        },
    ),
    NodeMeta(
        "rowDifference",
        "Row Difference",
        "analytics",
        "Difference or percent change between consecutive rows.",
        {
            "target": "",
            "method": "diff",
            "periods": 1,
            "partition_by": [],
            "order_by": [],
            "descending": False,
            "new_column": "",
        },
    ),
    NodeMeta(
        "dateDifference",
        "Date Difference",
        "analytics",
        "Difference between two date columns (end − start) in days, hours, etc.",
        {"start_column": "", "end_column": "", "unit": "days", "new_column": ""},
    ),
    # ----- Advanced -----
    NodeMeta(
        "pythonTransform",
        "Python Transform",
        "analytics",
        "Run arbitrary Python code on the DataFrame — an escape hatch for custom logic.",
        {"script": "# Write the body of: def transform(df):\n#   ...\nreturn df"},
    ),
    # ----- Data Quality -----
    NodeMeta(
        "assertNotNull",
        "Assert Not Null",
        "quality",
        "Fail or warn when any specified column contains null values.",
        {"columns": [], "mode": "error"},
    ),
    NodeMeta(
        "assertUnique",
        "Assert Unique",
        "quality",
        "Fail or warn when duplicate rows exist across the specified columns.",
        {"columns": [], "mode": "error"},
    ),
    NodeMeta(
        "assertValueRange",
        "Assert Value Range",
        "quality",
        "Fail or warn when column values fall outside a numeric range.",
        {"column": "", "min": None, "max": None, "inclusive": True, "mode": "error"},
    ),
    NodeMeta(
        "assertExpression",
        "Assert Expression",
        "quality",
        "Fail or warn when a boolean expression is false for any row.",
        {"expression": "", "mode": "error"},
    ),
    NodeMeta(
        "assertRowCount",
        "Assert Row Count",
        "quality",
        "Fail or warn when the row count falls outside declared bounds.",
        {"min_rows": None, "max_rows": None, "mode": "error"},
    ),
    NodeMeta(
        "assertValuesInSet",
        "Assert Values In Set",
        "quality",
        "Fail or warn when a column has values outside an allowed set.",
        {"column": "", "allowed": [], "allow_null": True, "mode": "error"},
    ),
    # ----- Charts -----
    # Pass-through nodes: the frame flows on unchanged; the run stores a
    # render-ready chart artifact computed over the full data.
    NodeMeta(
        "chartBar",
        "Bar Chart",
        "chart",
        "Aggregate a value per category and store a bar chart on the run (optionally stacked).",
        {"title": "", "x": "", "y": "", "aggregate": "sum", "group_by": "", "orientation": "vertical", "limit": None},
    ),
    NodeMeta(
        "chartLine",
        "Line Chart",
        "chart",
        "Plot one or more measures over an ordered axis (dates or numbers) and store it on the run.",
        {"title": "", "x": "", "y_columns": [], "aggregate": "mean"},
    ),
    NodeMeta(
        "chartArea",
        "Area Chart",
        "chart",
        "A line chart with a filled area, stored on the run.",
        {"title": "", "x": "", "y_columns": [], "aggregate": "mean"},
    ),
    NodeMeta(
        "chartScatter",
        "Scatter Plot",
        "chart",
        "Plot two numeric columns against each other and store it on the run.",
        {"title": "", "x": "", "y": ""},
    ),
    NodeMeta(
        "chartPie",
        "Pie Chart",
        "chart",
        "Share of a total per category (top slices + Other), stored on the run.",
        {"title": "", "category": "", "value": "", "aggregate": "count", "limit": None},
    ),
    NodeMeta(
        "chartHistogram",
        "Histogram",
        "chart",
        "Distribution of a numeric column in equal-width bins, stored on the run.",
        {"title": "", "column": "", "bins": 20},
    ),
    NodeMeta(
        "chartBoxPlot",
        "Box Plot",
        "chart",
        "Five-number summary of a numeric column, optionally per group, stored on the run.",
        {"title": "", "column": "", "group_by": ""},
    ),
    NodeMeta(
        "chartHeatmap",
        "Correlation Heatmap",
        "chart",
        "Pairwise correlations between numeric columns, stored on the run.",
        {"title": "", "columns": []},
    ),
    # ----- Machine Learning -----
    NodeMeta(
        "trainTestSplit",
        "Train / Test Split",
        "ml",
        "Split rows into a training set and a test set (seed required).",
        {"test_size": 0.2, "stratify_column": None, "seed": 42},
    ),
    NodeMeta(
        "scaleFeatures",
        "Scale Features",
        "ml",
        "Standardize / normalize numeric columns (standard, min-max, robust).",
        {"method": "standard", "columns": []},
    ),
    NodeMeta(
        "encodeCategories",
        "Encode Categories",
        "ml",
        "Turn categorical columns into numbers (one-hot or ordinal).",
        {"method": "onehot", "columns": [], "drop_first": False},
    ),
    NodeMeta(
        "selectFeatures",
        "Select Features",
        "ml",
        "Keep the most useful features (variance, correlation, or top-K).",
        {"method": "variance", "threshold": 0.0, "k": 10, "target_column": ""},
    ),
    NodeMeta(
        "reduceDimensions",
        "Reduce Dimensions",
        "ml",
        "Compress numeric features into principal components (PCA).",
        {"method": "pca", "n_components": 2, "columns": [], "prefix": "pc", "seed": 42},
    ),
    NodeMeta(
        "mlClassifierModel",
        "Classifier Model",
        "ml",
        "Configure a classification model without fitting it; use it with Cross-Validate.",
        {
            "model_type": "logistic_regression",
            "target_column": "",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlRegressorModel",
        "Regressor Model",
        "ml",
        "Configure a regression model without fitting it; use it with Cross-Validate.",
        {
            "model_type": "ridge",
            "target_column": "",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlTrainClassifier",
        "Train Classifier",
        "ml",
        "Fit a classification model (predict a category) and log it to MLflow.",
        {
            "model_type": "random_forest_classifier",
            "target_column": "",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlTrainRegressor",
        "Train Regressor",
        "ml",
        "Fit a regression model (predict a number) and log it to MLflow.",
        {
            "model_type": "random_forest_regressor",
            "target_column": "",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlTrainClustering",
        "Train Clustering",
        "ml",
        "Group rows into clusters (unsupervised) and log the model to MLflow.",
        {
            "model_type": "kmeans",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlTrainForecaster",
        "Train Forecaster",
        "ml",
        "Train a time-series forecasting model. (Models coming soon.)",
        {
            "model_type": "",
            "time_column": "",
            "target_column": "",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlTrainDimReduction",
        "Train Dim. Reduction",
        "ml",
        "Fit a dimensionality-reduction model (e.g. PCA) and log it to MLflow.",
        {
            "model_type": "pca_fit",
            "feature_columns": [],
            "hyperparameters": {},
            "seed": 42,
        },
    ),
    NodeMeta(
        "mlPredict",
        "Predict",
        "ml",
        "Score rows with a trained model (from the model wire or a registry URI).",
        {"model_uri": "", "output_column": "prediction", "output_proba_columns": [], "batch_size": None},
    ),
    NodeMeta(
        "mlEvaluate",
        "Evaluate",
        "ml",
        "Compute metrics from predictions (accuracy, RMSE, silhouette, …).",
        {
            "task_type": "classification",
            "target_column": "",
            "prediction_column": "prediction",
            "proba_columns": [],
            "metrics": [],
        },
    ),
    NodeMeta(
        "featureImportance",
        "Feature Importance",
        "ml",
        "Rank which features a trained model relied on most.",
        {"top_n": None},
    ),
    NodeMeta(
        "mlCrossValidate",
        "Cross-Validate",
        "ml",
        "Estimate model performance with k-fold, stratified, time-series, group, or other CV strategies.",
        {
            "cv_strategy": "kfold",
            "n_splits": 5,
            "n_repeats": 1,
            "test_size": 0.2,
            "shuffle": True,
            "group_column": None,
            "scoring": [],
            "seed": 42,
        },
    ),
    # ----- Outputs -----
    NodeMeta(
        "fileOutput",
        "File Output",
        "output",
        "Write the result to a file — pick the format (CSV, Excel, Parquet, JSON, text) and a name.",
        {"format": "csv", "dataset_name": ""},
    ),
    # Legacy single-format outputs — superseded by File Output, kept so existing
    # flows keep running. Hidden from the palette in the editor.
    NodeMeta("csvOutput", "CSV Output", "output", "Write the result to a CSV file.", {"path": ""}),
    NodeMeta("excelOutput", "Excel Output", "output", "Write the result to an Excel file.", {"path": ""}),
    NodeMeta("parquetOutput", "Parquet Output", "output", "Write the result to a Parquet file.", {"path": ""}),
    NodeMeta(
        "sqlOutput",
        "SQL Output",
        "output",
        "Write the result to a database table.",
        {"connection_id": "", "table": "", "schema": None, "if_exists": "replace"},
    ),
    NodeMeta(
        "storageOutput",
        "Storage Output",
        "output",
        "Write the result as a file (CSV, Excel, Parquet) to S3, Azure Blob, GCS, or a local folder.",
        {"connection_id": "", "path": "", "format": "parquet", "if_exists": "overwrite"},
    ),
)

#: Lookup by node type.
NODE_META_BY_TYPE: dict[str, NodeMeta] = {m.type: m for m in BUILTIN_NODE_META}
