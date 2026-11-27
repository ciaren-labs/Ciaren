# SPDX-License-Identifier: AGPL-3.0-only
"""Which nodes and settings the assistant may write. Anything not listed is denied."""

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
EXPRESSION_FUNCTIONS = frozenset(
    {"abs", "sqrt", "exp", "log", "log10", "log1p", "expm1", "sin", "cos", "tan", "sinh", "cosh", "tanh"}
)
_KEYWORDS = frozenset({"and", "or", "not", "in", "True", "False"})
_TOKEN = re.compile(
    r"""(?P<quoted>'[^'\n]*'|"[^"\n]*")|`(?P<named>[^`\n]*)`|(?P<number>\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)"""
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)


def guard_expression(expression: str, columns: Iterable[str], field: str = "expression") -> None:
    """Accept only short comparisons and arithmetic over known columns and math functions."""
    known = set(columns)
    if len(expression) > EXPRESSION_LIMIT:
        raise PolicyError(f"Expressions are limited to {EXPRESSION_LIMIT} characters.", field, "limit")
    if any(term in expression for term in ("@", "__", ";", "\n", "\r", "import", "lambda")):
        raise PolicyError("The expression uses a disallowed construct.", field)
    for match in _TOKEN.finditer(expression):
        if match["named"] is not None and match["named"] not in known:
            raise PolicyError("The expression references an unknown column.", field)
        name = match["name"]
        if name and name not in known and name not in EXPRESSION_FUNCTIONS and name not in _KEYWORDS:
            raise PolicyError("The expression references an unknown column or function.", field)


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
MAX_ESTIMATORS = 500
MAX_DEPTH = 64
MAX_SPLITS = 20
MAX_REPEATS = 5
LEAVE_ONE_OUT_ROWS = 2000


def check_fields(node_type: str, config: dict[str, Any], rows: int | None = None) -> None:
    """Field rules beyond the node model: caps that depend on policy or on the input size."""
    reject_templates(config)
    if node_type == "mlPredict" and config.get("model_uri"):
        raise PolicyError("Predictions must use the connected model, not a stored model URI.", "model_uri")
    params = config.get("hyperparameters") or {}
    if "n_jobs" in params:
        raise PolicyError("Parallel training settings are not allowed.", "hyperparameters")
    if set(params) - set(HYPERPARAMETERS.get(config.get("model_type", ""), ())):
        raise PolicyError("A hyperparameter is not available for this model.", "hyperparameters")
    for key, cap in (("n_estimators", MAX_ESTIMATORS), ("max_depth", MAX_DEPTH)):
        value = params.get(key)
        if isinstance(value, int) and value > cap:
            raise PolicyError(f"{key} is limited to {cap}.", "hyperparameters", "limit")
    if node_type == "mlCrossValidate":
        if config.get("n_splits", 5) > MAX_SPLITS or config.get("n_repeats", 1) > MAX_REPEATS:
            raise PolicyError("Cross-validation folds or repeats exceed the assistant limit.", "n_splits", "limit")
        if config.get("cv_strategy") == "leave_one_out" and (rows is None or rows > LEAVE_ONE_OUT_ROWS):
            raise PolicyError(
                f"Leave-one-out is limited to inputs of at most {LEAVE_ONE_OUT_ROWS} rows.", "cv_strategy", "limit"
            )
