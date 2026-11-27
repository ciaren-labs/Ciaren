# SPDX-License-Identifier: AGPL-3.0-only
"""Closed config models for the nodes the assistant may write.

The models are the tool schema shown to the provider and the second static gate.
Each node's ``validate_config`` stays authoritative after them. Enumerations come
from the engine constants so the two cannot drift. Column fields carry
``x-ciaren: column | column_list`` so callers can map turn-local column refs.
"""

from collections.abc import Iterable
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, GetJsonSchemaHandler, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

from app.engine.transformations import charts, conditional, join, quality
from app.engine.transformations import window as windows
from app.engine.transformations.ml import cross_validation, evaluate, feature_engineering
from app.ml.models import CLASSIFICATION, CLUSTERING, DIMENSIONALITY_REDUCTION, MODEL_CATALOG, REGRESSION


class OneOf:
    """A string restricted to engine-defined values, published as a JSON-schema enum."""

    def __init__(self, values: Iterable[str]) -> None:
        self.values = tuple(sorted(values))

    def __get_pydantic_core_schema__(self, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        def check(value: str) -> str:
            if value not in self.values:
                raise PydanticCustomError("enum", "Unsupported value.")
            return value

        return core_schema.no_info_after_validator_function(check, handler(source))

    def __get_pydantic_json_schema__(self, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        result = handler(schema)
        result["enum"] = list(self.values)
        return result


def _transformation(node_type: str) -> Any:
    from app.engine.registry import get_transformation

    return get_transformation(node_type)


Name = Annotated[str, Field(min_length=1, max_length=255)]
Column = Annotated[str, Field(min_length=1, max_length=255, json_schema_extra={"x-ciaren": "column"})]
# Optional single-column settings whose default is the empty string.
MaybeColumn = Annotated[str, Field(max_length=255, json_schema_extra={"x-ciaren": "column"})]
Columns = Annotated[list[Column], Field(max_length=64, json_schema_extra={"x-ciaren": "column_list"})]
Scalar = str | int | float | bool | None
# Mappings keyed by input column (casts, renames, aggregations).
KEYED = {"x-ciaren": "column_keys"}
Mode = Annotated[str, OneOf(quality._VALID_MODES)]
Aggregate = Annotated[str, OneOf(charts.VALID_AGGREGATES)]


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DatasetInput(NodeConfig):
    dataset_id: Name
    dataset_version: int | None = Field(None, ge=1)


class FileInput(DatasetInput):
    format: Literal["csv", "tsv", "excel", "parquet", "json", "jsonl", "text"] = "csv"


class FileOutput(NodeConfig):
    format: Literal["csv", "parquet", "excel", "json"] = "csv"
    dataset_name: Name


class DropNulls(NodeConfig):
    subset: Columns = []
    how: Literal["any", "all"] = "any"


class FillNulls(NodeConfig):
    strategy: Annotated[str, OneOf(_transformation("fillNulls")._VALID_STRATEGIES)] = "constant"
    value: Scalar = ""
    columns: Columns = []


class RemoveDuplicates(NodeConfig):
    subset: Columns = []
    keep: Literal["first", "last"] = "first"


class FilterRows(NodeConfig):
    column: Column
    operator: Literal["==", "!=", ">", ">=", "<", "<=", "isnull", "notnull", "contains", "between"] = "=="
    value: Scalar = ""
    value2: Scalar = None


class Expression(NodeConfig):
    expression: Annotated[str, Field(min_length=1, max_length=300)]


class SortRows(NodeConfig):
    columns: Annotated[Columns, Field(min_length=1)]
    ascending: bool = True
    na_position: Literal["first", "last"] = "last"


class CastDtypes(NodeConfig):
    casts: Annotated[
        dict[Column, Annotated[str, OneOf(_transformation("castDtypes")._VALID_DTYPES)]],
        Field(min_length=1, max_length=64, json_schema_extra=KEYED),
    ]
    errors: Literal["raise", "coerce"] = "raise"
    format: Annotated[str, Field(max_length=64)] = ""


class LimitRows(NodeConfig):
    n: int = Field(100, ge=0, le=10_000_000)
    offset: int = Field(0, ge=0)


class SampleRows(NodeConfig):
    n: int = Field(100, ge=0, le=10_000_000)
    seed: int = 42


class ColumnList(NodeConfig):
    columns: Annotated[Columns, Field(min_length=1)]


class RenameColumns(NodeConfig):
    mapping: Annotated[dict[Column, Name], Field(min_length=1, max_length=64, json_schema_extra=KEYED)]


class CombineColumns(NodeConfig):
    columns: Annotated[Columns, Field(min_length=2)]
    new_column: Name
    separator: Annotated[str, Field(max_length=16)] = " "
    keep_original: bool = True


class CoalesceColumns(NodeConfig):
    columns: Annotated[Columns, Field(min_length=2)]
    new_column: Name
    keep_original: bool = True


class ReplaceValues(NodeConfig):
    column: Column
    to_replace: Scalar = ""
    value: Scalar = ""
    regex: Literal[False] = False


class StringTransform(NodeConfig):
    column: Column
    operation: Annotated[str, OneOf(_transformation("stringTransform")._VALID_OPS)] = "lower"
    find: Annotated[str, Field(max_length=160)] | None = None
    replace: Annotated[str, Field(max_length=160)] | None = None
    width: int | None = Field(None, ge=1, le=1024)


class CalculatedColumn(NodeConfig):
    column_name: Name
    expression: Annotated[str, Field(min_length=1, max_length=300)]


class SplitColumn(NodeConfig):
    column: Column
    mode: Literal["delimiter"] = "delimiter"
    delimiter: Annotated[str, Field(min_length=1, max_length=16)] = ","
    pattern: Literal[""] = ""
    into: Annotated[list[Name], Field(min_length=1, max_length=32)]
    keep_original: bool = True


class MapValues(NodeConfig):
    column: Column
    new_column: Annotated[str, Field(max_length=255)] = ""
    mapping: Annotated[dict[Annotated[str, Field(max_length=160)], Scalar], Field(min_length=1, max_length=64)]
    default: Scalar = ""
    use_default: bool = False


AggFunc = Annotated[str, OneOf(_transformation("groupByAggregate")._SHARED_AGGFUNCS)]


class GroupByAggregate(NodeConfig):
    group_by: Annotated[Columns, Field(min_length=1)]
    aggregations: Annotated[dict[Column, AggFunc], Field(min_length=1, max_length=64, json_schema_extra=KEYED)]


class Join(NodeConfig):
    on: Column | Columns
    how: Annotated[str, OneOf(join._VALID_HOW)] = "inner"
    suffixes: Annotated[list[Annotated[str, Field(max_length=16)]], Field(min_length=2, max_length=2)] = ["_x", "_y"]


class ConcatRows(NodeConfig):
    pass


class Unpivot(NodeConfig):
    id_vars: Annotated[Columns, Field(min_length=1)]
    value_vars: Columns = []
    var_name: Name = "variable"
    value_name: Name = "value"


class Pivot(NodeConfig):
    index: Annotated[Columns, Field(min_length=1)]
    columns: Column
    values: Column
    aggfunc: Annotated[str, OneOf(_transformation("pivot")._SHARED_AGGFUNCS)] = "sum"


class ExplodeRows(NodeConfig):
    column: Column
    delimiter: Annotated[str, Field(max_length=16)] = ","


class RemoveOutliers(NodeConfig):
    columns: Annotated[Columns, Field(min_length=1)]
    method: Annotated[str, OneOf(_transformation("removeOutliers")._METHODS)] = "iqr"
    action: Annotated[str, OneOf(_transformation("removeOutliers")._ACTIONS)] = "drop"
    factor: float = Field(1.5, gt=0, le=100)
    threshold: float = Field(3, gt=0, le=100)
    lower: float = Field(1, ge=0, le=100)
    upper: float = Field(99, ge=0, le=100)


class RoundNumbers(NodeConfig):
    columns: Annotated[Columns, Field(min_length=1)]
    decimals: int = Field(0, ge=-10, le=15)


class BinColumn(NodeConfig):
    column: Column
    new_column: Name
    method: Annotated[str, OneOf(_transformation("binColumn")._METHODS)] = "equalwidth"
    bins: int = Field(4, ge=2, le=100)


class ExtractDateParts(NodeConfig):
    column: Column
    parts: Annotated[list[Annotated[str, OneOf(_transformation("extractDateParts")._VALID_PARTS)]], Field(min_length=1)]


class ParseDates(NodeConfig):
    columns: Annotated[Columns, Field(min_length=1)]
    format: Annotated[str, Field(max_length=64)] = ""
    errors: Annotated[str, OneOf(_transformation("parseDates")._ERRORS)] = "coerce"


class Ordered(NodeConfig):
    partition_by: Columns = []
    order_by: Columns = []
    descending: bool = False
    new_column: Name


class WindowFunction(Ordered):
    function: Annotated[str, OneOf(windows._ALL_FUNCS)] = "row_number"
    target: MaybeColumn = ""
    offset: int = Field(1, ge=1, le=10_000)

    @model_validator(mode="after")
    def _requirements(self) -> "WindowFunction":
        if self.function in windows._TARGET_FUNCS and not self.target:
            raise ValueError("This window function needs a target column.")
        if self.function in windows._RANK_FUNCS and not self.order_by:
            raise ValueError("Ranking needs an order_by column.")
        return self


class RollingAggregate(Ordered):
    target: Column
    function: Annotated[str, OneOf(windows.ROLLING_FUNCS)] = "mean"
    window: int = Field(3, ge=1, le=10_000)
    min_periods: int | None = Field(None, ge=1)


class RowDifference(Ordered):
    target: Column
    method: Annotated[str, OneOf(_transformation("rowDifference")._METHODS)] = "diff"
    periods: int = Field(1, ge=1, le=10_000)


class DateDifference(NodeConfig):
    start_column: Column
    end_column: Column
    unit: Annotated[str, OneOf(_transformation("dateDifference")._UNITS)] = "days"
    new_column: Name


class Condition(NodeConfig):
    column: Column
    operator: Annotated[str, OneOf(conditional._OPERATORS)] = "=="
    value: Scalar = None


class Rule(NodeConfig):
    match: Literal["all", "any"] = "all"
    conditions: Annotated[list[Condition], Field(min_length=1, max_length=8)] | None = None
    column: Column | None = None
    operator: Annotated[str, OneOf(conditional._OPERATORS)] | None = None
    value: Scalar = None
    result: Scalar

    @model_validator(mode="after")
    def _one_form(self) -> "Rule":
        if (self.conditions is None) == (self.column is None):
            raise ValueError("A rule needs either one column condition or a conditions list.")
        return self


class ConditionalColumn(NodeConfig):
    new_column: Name
    default: Scalar = ""
    rules: Annotated[list[Rule], Field(min_length=1, max_length=16)]


class AssertColumns(NodeConfig):
    columns: Columns = []
    mode: Mode = "error"


class AssertValueRange(NodeConfig):
    column: Column
    min: float | None = None
    max: float | None = None
    inclusive: bool = True
    mode: Mode = "error"

    @model_validator(mode="after")
    def _bound(self) -> "AssertValueRange":
        if self.min is None and self.max is None:
            raise ValueError("Set a minimum or a maximum.")
        return self


class AssertExpression(NodeConfig):
    expression: Annotated[str, Field(min_length=1, max_length=300)]
    mode: Mode = "error"


class AssertRowCount(NodeConfig):
    min_rows: int | None = Field(None, ge=0)
    max_rows: int | None = Field(None, ge=0)
    mode: Mode = "error"

    @model_validator(mode="after")
    def _bound(self) -> "AssertRowCount":
        if self.min_rows is None and self.max_rows is None:
            raise ValueError("Set a minimum or a maximum row count.")
        if self.min_rows is not None and self.max_rows is not None and self.min_rows > self.max_rows:
            raise ValueError("The minimum exceeds the maximum.")
        return self


class AssertValuesInSet(NodeConfig):
    column: Column
    allowed: Annotated[list[Scalar], Field(min_length=1, max_length=64)]
    allow_null: bool = True
    mode: Mode = "error"


Title = Annotated[str, Field(max_length=charts.MAX_TITLE_LEN)]


class ChartBar(NodeConfig):
    title: Title = ""
    x: Column
    y: MaybeColumn = ""
    aggregate: Aggregate = "sum"
    group_by: MaybeColumn = ""
    orientation: Literal["vertical", "horizontal"] = "vertical"
    limit: int | None = Field(None, ge=1, le=charts.MAX_BAR_CATEGORIES)

    @model_validator(mode="after")
    def _measure(self) -> "ChartBar":
        if self.aggregate != "count" and not self.y:
            raise ValueError("Bars need a y column unless they count rows.")
        return self


class ChartSeries(NodeConfig):
    title: Title = ""
    x: Column
    y_columns: Annotated[Columns, Field(min_length=1, max_length=charts.MAX_LINE_SERIES)]
    aggregate: Aggregate = "mean"


class ChartScatter(NodeConfig):
    title: Title = ""
    x: Column
    y: Column


class ChartPie(NodeConfig):
    title: Title = ""
    category: Column
    value: MaybeColumn = ""
    aggregate: Aggregate = "count"
    limit: int | None = Field(None, ge=2, le=charts.MAX_PIE_SLICES)

    @model_validator(mode="after")
    def _measure(self) -> "ChartPie":
        if self.aggregate != "count" and not self.value:
            raise ValueError("Slices need a value column unless they count rows.")
        return self


class ChartHistogram(NodeConfig):
    title: Title = ""
    column: Column
    bins: int = Field(20, ge=1, le=charts.MAX_HISTOGRAM_BINS)


class ChartBoxPlot(NodeConfig):
    title: Title = ""
    column: Column
    group_by: MaybeColumn = ""


class ChartHeatmap(NodeConfig):
    title: Title = ""
    columns: Annotated[Columns, Field(max_length=charts.MAX_HEATMAP_COLUMNS)] = []


class TrainTestSplit(NodeConfig):
    test_size: float = Field(0.2, gt=0, lt=1)
    stratify_column: Column | None = None
    seed: int = 42


class ScaleFeatures(NodeConfig):
    method: Annotated[str, OneOf(feature_engineering._SCALERS)] = "standard"
    columns: Annotated[Columns, Field(min_length=1)]


class EncodeCategories(NodeConfig):
    method: Literal["onehot", "ordinal"] = "onehot"
    columns: Annotated[Columns, Field(min_length=1)]
    drop_first: bool = False


class SelectFeatures(NodeConfig):
    method: Literal["variance", "correlation", "kbest"] = "variance"
    threshold: float = 0.0
    k: int = Field(10, ge=1, le=1000)
    target_column: MaybeColumn = ""


class ReduceDimensions(NodeConfig):
    method: Literal["pca"] = "pca"
    n_components: int = Field(2, ge=1, le=64)
    columns: Columns = []
    prefix: Name = "pc"
    seed: int = 42


Hyperparameters = Annotated[dict[Annotated[str, Field(max_length=64)], int | float | str | bool], Field(max_length=16)]


def _model_type(*tasks: str) -> OneOf:
    return OneOf(name for name, spec in MODEL_CATALOG.items() if spec.task in tasks)


class Estimator(NodeConfig):
    feature_columns: Columns = []
    hyperparameters: Hyperparameters = {}
    seed: int = 42


class Supervised(Estimator):
    target_column: Column

    @model_validator(mode="after")
    def _no_leakage(self) -> "Supervised":
        if self.target_column in self.feature_columns:
            raise ValueError("The target column cannot also be a feature.")
        return self


class Classifier(Supervised):
    model_type: Annotated[str, _model_type(CLASSIFICATION)] = "logistic_regression"


class Regressor(Supervised):
    model_type: Annotated[str, _model_type(REGRESSION)] = "ridge"


class TrainClassifier(Classifier):
    model_type: Annotated[str, _model_type(CLASSIFICATION)] = "random_forest_classifier"


class TrainRegressor(Regressor):
    model_type: Annotated[str, _model_type(REGRESSION)] = "random_forest_regressor"


class TrainClustering(Estimator):
    model_type: Annotated[str, _model_type(CLUSTERING)] = "kmeans"


class TrainDimReduction(Estimator):
    model_type: Annotated[str, _model_type(DIMENSIONALITY_REDUCTION)] = "pca_fit"


class Predict(NodeConfig):
    model_uri: Literal[""] = ""
    output_column: Name = "prediction"
    output_proba_columns: list[Name] = []
    batch_size: int | None = Field(None, ge=1, le=1_000_000)


class Evaluate(NodeConfig):
    task_type: Annotated[str, OneOf(evaluate._TASKS)] = "classification"
    target_column: MaybeColumn = ""
    prediction_column: Column = "prediction"
    proba_columns: Columns = []
    metrics: list[Annotated[str, Field(max_length=64)]] = []

    @model_validator(mode="after")
    def _target(self) -> "Evaluate":
        if self.task_type != CLUSTERING and not self.target_column:
            raise ValueError("Supervised evaluation needs a target column.")
        return self


class FeatureImportance(NodeConfig):
    top_n: int | None = Field(None, ge=1, le=1000)


Scoring = Annotated[str, OneOf({s for task in (CLASSIFICATION, REGRESSION) for s in cross_validation._SCORING[task]})]


class CrossValidate(NodeConfig):
    cv_strategy: Annotated[str, OneOf(cross_validation.CV_STRATEGIES)] = "kfold"
    n_splits: int = Field(5, ge=2)
    n_repeats: int = Field(1, ge=1)
    test_size: float = Field(0.2, gt=0, lt=1)
    shuffle: bool = True
    group_column: Column | None = None
    scoring: list[Scoring] = []
    seed: int = 42

    @model_validator(mode="after")
    def _group(self) -> "CrossValidate":
        if self.cv_strategy == "group_kfold" and not self.group_column:
            raise ValueError("Group k-fold needs a group column.")
        return self


MODELS: dict[str, type[NodeConfig]] = {
    "fileInput": FileInput,
    **{t: DatasetInput for t in ("csvInput", "excelInput", "parquetInput", "jsonInput", "textInput")},
    "fileOutput": FileOutput,
    "dropNulls": DropNulls,
    "fillNulls": FillNulls,
    "removeDuplicates": RemoveDuplicates,
    "filterRows": FilterRows,
    "filterExpression": Expression,
    "sortRows": SortRows,
    "castDtypes": CastDtypes,
    "limitRows": LimitRows,
    "sampleRows": SampleRows,
    "dropColumns": ColumnList,
    "renameColumns": RenameColumns,
    "selectColumns": ColumnList,
    "combineColumns": CombineColumns,
    "coalesceColumns": CoalesceColumns,
    "replaceValues": ReplaceValues,
    "stringTransform": StringTransform,
    "calculatedColumn": CalculatedColumn,
    "splitColumn": SplitColumn,
    "mapValues": MapValues,
    "groupByAggregate": GroupByAggregate,
    "join": Join,
    "concatRows": ConcatRows,
    "unpivot": Unpivot,
    "pivot": Pivot,
    "explodeRows": ExplodeRows,
    "removeOutliers": RemoveOutliers,
    "roundNumbers": RoundNumbers,
    "binColumn": BinColumn,
    "extractDateParts": ExtractDateParts,
    "parseDates": ParseDates,
    "windowFunction": WindowFunction,
    "conditionalColumn": ConditionalColumn,
    "rollingAggregate": RollingAggregate,
    "rowDifference": RowDifference,
    "dateDifference": DateDifference,
    "assertNotNull": AssertColumns,
    "assertUnique": AssertColumns,
    "assertValueRange": AssertValueRange,
    "assertExpression": AssertExpression,
    "assertRowCount": AssertRowCount,
    "assertValuesInSet": AssertValuesInSet,
    "chartBar": ChartBar,
    "chartLine": ChartSeries,
    "chartArea": ChartSeries,
    "chartScatter": ChartScatter,
    "chartPie": ChartPie,
    "chartHistogram": ChartHistogram,
    "chartBoxPlot": ChartBoxPlot,
    "chartHeatmap": ChartHeatmap,
    "trainTestSplit": TrainTestSplit,
    "scaleFeatures": ScaleFeatures,
    "encodeCategories": EncodeCategories,
    "selectFeatures": SelectFeatures,
    "reduceDimensions": ReduceDimensions,
    "mlClassifierModel": Classifier,
    "mlRegressorModel": Regressor,
    "mlTrainClassifier": TrainClassifier,
    "mlTrainRegressor": TrainRegressor,
    "mlTrainClustering": TrainClustering,
    "mlTrainDimReduction": TrainDimReduction,
    "mlPredict": Predict,
    "mlEvaluate": Evaluate,
    "featureImportance": FeatureImportance,
    "mlCrossValidate": CrossValidate,
}


def column_fields(node_type: str) -> dict[str, str]:
    """Field name -> ``column``, ``column_list`` or ``column_keys`` for one node model."""
    schema = MODELS[node_type].model_json_schema()
    found = {}
    for name, prop in schema.get("properties", {}).items():
        options = [prop, *prop.get("anyOf", [])]
        kinds = [o.get("x-ciaren") or (o.get("items") or {}).get("x-ciaren") for o in options]
        kind = next((k for k in kinds if k), None)
        if kind:
            found[name] = "column_list" if kind == "column" and any(o.get("type") == "array" for o in options) else kind
    return found
