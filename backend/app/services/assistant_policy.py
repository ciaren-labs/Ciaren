# SPDX-License-Identifier: AGPL-3.0-only
"""Which nodes and settings the assistant may write. Anything not listed is denied."""

import ast
import re
from collections.abc import Iterable
from typing import Any, Literal

from app.plugins.builtin import CORE_PROVIDER, ML_PROVIDER

Tier = Literal["allow", "review"]

_INPUTS = ("fileInput", "csvInput", "excelInput", "parquetInput", "jsonInput", "textInput")
_CORE = (
    *_INPUTS,
    "fileOutput",
    "dropNulls",
    "fillNulls",
    "removeDuplicates",
    "filterRows",
    "sortRows",
    "castDtypes",
    "limitRows",
    "sampleRows",
    "dropColumns",
    "renameColumns",
    "selectColumns",
    "combineColumns",
    "coalesceColumns",
    "replaceValues",
    "stringTransform",
    "splitColumn",
    "mapValues",
    "groupByAggregate",
    "join",
    "concatRows",
    "unpivot",
    "pivot",
    "explodeRows",
    "removeOutliers",
    "roundNumbers",
    "binColumn",
    "extractDateParts",
    "parseDates",
    "windowFunction",
    "conditionalColumn",
    "rollingAggregate",
    "rowDifference",
    "dateDifference",
    "assertNotNull",
    "assertUnique",
    "assertValueRange",
    "assertRowCount",
    "assertValuesInSet",
    "chartBar",
    "chartLine",
    "chartArea",
    "chartScatter",
    "chartPie",
    "chartHistogram",
    "chartBoxPlot",
    "chartHeatmap",
)
_ML = (
    "selectFeatures",
    "scaleFeatures",
    "encodeCategories",
    "reduceDimensions",
    "mlClassifierModel",
    "mlRegressorModel",
    "mlTrainClassifier",
    "mlTrainRegressor",
    "mlTrainClustering",
    "mlTrainDimReduction",
    "trainTestSplit",
    "mlPredict",
    "mlEvaluate",
    "featureImportance",
    "mlCrossValidate",
)
#: Free-text expressions run through the engine evaluator; they pass the expression guard
#: and are highlighted for review.
REVIEW = ("filterExpression", "calculatedColumn", "assertExpression")
_ALLOW: Tier = "allow"
_REVIEW: Tier = "review"
POLICY: dict[str, Tier] = {t: _ALLOW for t in (*_CORE, *_ML)} | {t: _REVIEW for t in REVIEW}
PROVIDERS = {t: ML_PROVIDER if t in _ML else CORE_PROVIDER for t in POLICY}
#: Never written by the assistant: unsandboxed code, connections and credentials,
#: destructive writes and free filesystem paths. Listed for documentation and tests;
#: absence from POLICY is what denies them, together with every plugin node.
DENIED = (
    "pythonTransform",
    "sqlInput",
    "storageInput",
    "sqlOutput",
    "storageOutput",
    "csvOutput",
    "excelOutput",
    "parquetOutput",
    "mlTrainForecaster",
)
INPUTS = frozenset(_INPUTS)
TERMINAL = frozenset({"fileOutput", *(t for t in _CORE if t.startswith("chart"))})


class PolicyError(ValueError):
    """A node, field or value the assistant may not write. ``code`` is ``policy`` or ``limit``."""

    def __init__(self, message: str, field: str | None = None, code: str = "policy") -> None:
        self.field = field
        self.code = code
        super().__init__(message)


def tier(node_type: str, provider: str | None) -> Tier | None:
    """The tier of a node, or None when it is denied (unknown, plugin or explicitly excluded)."""
    found = POLICY.get(node_type)
    return found if found and provider == PROVIDERS[node_type] else None


def reject_templates(value: Any, field: str | None = None) -> None:
    """Model-written strings may never contain parameter placeholders (SEC-004)."""
    if isinstance(value, str):
        if "{{" in value:
            raise PolicyError("Parameter placeholders are not allowed in assistant edits.", field)
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_templates(key, field)
            reject_templates(item, field)
    elif isinstance(value, list):
        for item in value:
            reject_templates(item, field)


EXPRESSION_LIMIT = 300
LITERAL_LIMIT = 160
#: Functions both evaluators accept: pandas ``DataFrame.eval`` (filters, assertions and
#: pandas calculated columns) and polars ``pl.sql_expr`` (polars calculated columns).
EXPRESSION_FUNCTIONS = frozenset({"abs", "sqrt", "exp", "log10", "log1p", "sin", "cos", "floor", "ceil"})
_OPERATORS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.And,
    ast.Or,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)
_DECIMAL = re.compile(r"\d+(\.\d+)?")
_STRUCTURE = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Load)


def guard_expression(expression: str, columns: Iterable[str], field: str = "expression") -> None:
    """Allow only arithmetic, comparisons and boolean logic over known columns and literals.

    The text must be printable ASCII, so evaluators that normalise Unicode identifiers
    cannot see a name the check did not. Attribute access, indexing, keyword arguments,
    comprehensions and every other node type are rejected.
    """
    known = set(columns)
    if len(expression) > EXPRESSION_LIMIT:
        raise PolicyError(f"Expressions are limited to {EXPRESSION_LIMIT} characters.", field, "limit")
    if not expression.isascii() or not expression.isprintable():
        raise PolicyError("Expressions may only contain printable ASCII characters.", field)
    if any(term in expression for term in ("@", "__", ";", "`", "import", "lambda")):
        raise PolicyError("The expression uses a disallowed construct.", field)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise PolicyError("The expression is not a supported formula.", field) from None
    for node in ast.walk(tree):
        if isinstance(node, _STRUCTURE + _OPERATORS):
            continue
        if isinstance(node, ast.Name):
            if node.id not in known and node.id not in EXPRESSION_FUNCTIONS:
                raise PolicyError("The expression references an unknown column.", field)
        elif isinstance(node, ast.Constant):
            value = node.value
            source = ast.get_source_segment(expression, node) or ""
            # Plain decimals only: polars SQL rejects exponent and hex forms, and None.
            plain = isinstance(value, bool | str) or isinstance(value, int | float) and _DECIMAL.fullmatch(source)
            if not plain:
                raise PolicyError("Unsupported literal in the expression.", field)
            if isinstance(value, str) and len(value) > LITERAL_LIMIT:
                raise PolicyError(f"Text literals are limited to {LITERAL_LIMIT} characters.", field, "limit")
        elif isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in EXPRESSION_FUNCTIONS
                or len(node.args) != 1
                or node.keywords
            ):
                raise PolicyError("Only single-argument math functions may be called.", field)
        else:
            raise PolicyError("The expression uses a disallowed construct.", field)
    # A function name used as a value (``abs > 1``) is not a column.
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and id(node) not in called and node.id not in known:
            raise PolicyError("The expression references an unknown column.", field)


_TREES = ("n_estimators", "max_depth", "min_samples_split", "min_samples_leaf")
_BOOSTED = ("n_estimators", "max_depth", "learning_rate")
#: Hyperparameter names the assistant may set, per model type. Others are rejected.
HYPERPARAMETERS: dict[str, tuple[str, ...]] = {
    "logistic_regression": ("C", "max_iter"),
    "random_forest_classifier": _TREES,
    "random_forest_regressor": _TREES,
    "svm_classifier": ("C", "kernel"),
    "svr": ("C", "kernel", "epsilon"),
    "knn_classifier": ("n_neighbors",),
    "xgboost_classifier": _BOOSTED,
    "xgboost_regressor": _BOOSTED,
    "lightgbm_classifier": (*_BOOSTED, "num_leaves"),
    "lightgbm_regressor": (*_BOOSTED, "num_leaves"),
    "linear_regression": (),
    "ridge": ("alpha",),
    "lasso": ("alpha",),
    "kmeans": ("n_clusters",),
    "dbscan": ("eps", "min_samples"),
    "agglomerative": ("n_clusters",),
    "pca_fit": ("n_components",),
}
#: Integer hyperparameters that scale compute, with the largest value the assistant may write.
HYPERPARAMETER_CAPS = {"n_estimators": 500, "max_depth": 64, "num_leaves": 1024, "max_iter": 10_000}
MAX_SPLITS = 20
MAX_REPEATS = 5
LEAVE_ONE_OUT_ROWS = 2000


def _typed(config: dict[str, Any], key: str, kind: type, default: Any) -> Any:
    """A field the caps read, with its type checked first so malformed values become issues."""
    value = config.get(key, default)
    if type(value) is not kind:
        raise PolicyError(f"{key} has an unsupported value type.", key, "config")
    return value


def check_fields(node_type: str, config: dict[str, Any], rows: int | None = None) -> None:
    """Field rules beyond the node model: caps that depend on policy or on the input size.

    Runs before the node model, so every value it reads is type-checked here.
    """
    reject_templates(config)
    if node_type == "mlPredict" and _typed(config, "model_uri", str, ""):
        raise PolicyError("Predictions must use the connected model, not a stored model URI.", "model_uri")
    if "hyperparameters" in config or "model_type" in config:
        params = _typed(config, "hyperparameters", dict, {})
        model_type = _typed(config, "model_type", str, "")
        if "n_jobs" in params:
            raise PolicyError("Parallel training settings are not allowed.", "hyperparameters")
        if set(params) - set(HYPERPARAMETERS.get(model_type, ())):
            raise PolicyError("A hyperparameter is not available for this model.", "hyperparameters")
        for key, cap in HYPERPARAMETER_CAPS.items():
            if key in params and _typed(params, key, int, None) > cap:
                raise PolicyError(f"{key} is limited to {cap}.", "hyperparameters", "limit")
    if node_type == "mlCrossValidate":
        splits, repeats = _typed(config, "n_splits", int, 5), _typed(config, "n_repeats", int, 1)
        if splits > MAX_SPLITS or repeats > MAX_REPEATS:
            raise PolicyError("Cross-validation folds or repeats exceed the assistant limit.", "n_splits", "limit")
        strategy = _typed(config, "cv_strategy", str, "kfold")
        if strategy == "leave_one_out" and (rows is None or rows > LEAVE_ONE_OUT_ROWS):
            raise PolicyError(
                f"Leave-one-out is limited to inputs of at most {LEAVE_ONE_OUT_ROWS} rows.", "cv_strategy", "limit"
            )
