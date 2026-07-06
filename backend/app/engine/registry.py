# SPDX-License-Identifier: AGPL-3.0-only
from app.engine.transformations.base import BaseTransformation
from app.engine.transformations.charts import (
    ChartAreaTransformation,
    ChartBarTransformation,
    ChartBoxPlotTransformation,
    ChartHeatmapTransformation,
    ChartHistogramTransformation,
    ChartLineTransformation,
    ChartPieTransformation,
    ChartScatterTransformation,
)
from app.engine.transformations.columns import (
    CastDtypesTransformation,
    CoalesceColumnsTransformation,
    CombineColumnsTransformation,
    DropColumnsTransformation,
    RenameColumnsTransformation,
    SelectColumnsTransformation,
)
from app.engine.transformations.conditional import ConditionalColumnTransformation
from app.engine.transformations.join import JoinTransformation
from app.engine.transformations.nulls import (
    DropNullsTransformation,
    FillNullsTransformation,
)
from app.engine.transformations.numeric import (
    BinColumnTransformation,
    RemoveOutliersTransformation,
    RoundNumbersTransformation,
)
from app.engine.transformations.quality import (
    AssertExpressionTransformation,
    AssertNotNullTransformation,
    AssertRowCountTransformation,
    AssertUniqueTransformation,
    AssertValueRangeTransformation,
    AssertValuesInSetTransformation,
)
from app.engine.transformations.reshape import (
    ConcatRowsTransformation,
    CreateCalculatedColumnTransformation,
    DateDifferenceTransformation,
    ExplodeRowsTransformation,
    ExtractDatePartsTransformation,
    GroupByAggregateTransformation,
    ParseDatesTransformation,
    PivotTransformation,
    UnpivotTransformation,
)
from app.engine.transformations.rows import (
    FilterExpressionTransformation,
    FilterRowsTransformation,
    LimitRowsTransformation,
    RemoveDuplicatesTransformation,
    SampleRowsTransformation,
    SortRowsTransformation,
)
from app.engine.transformations.script import PythonTransformTransformation
from app.engine.transformations.text import (
    MapValuesTransformation,
    ReplaceValuesTransformation,
    SplitColumnTransformation,
    StringTransformTransformation,
)
from app.engine.transformations.window import (
    RollingAggregateTransformation,
    RowDifferenceTransformation,
    WindowFunctionTransformation,
)

_REGISTRY: dict[str, BaseTransformation] = {}


def _register(*transformations: BaseTransformation) -> None:
    for t in transformations:
        _REGISTRY[t.type] = t


_register(
    DropNullsTransformation(),
    FillNullsTransformation(),
    DropColumnsTransformation(),
    RenameColumnsTransformation(),
    SelectColumnsTransformation(),
    RemoveDuplicatesTransformation(),
    FilterRowsTransformation(),
    SortRowsTransformation(),
    CastDtypesTransformation(),
    LimitRowsTransformation(),
    ReplaceValuesTransformation(),
    StringTransformTransformation(),
    GroupByAggregateTransformation(),
    ConcatRowsTransformation(),
    CreateCalculatedColumnTransformation(),
    JoinTransformation(),
    SampleRowsTransformation(),
    RemoveOutliersTransformation(),
    RoundNumbersTransformation(),
    BinColumnTransformation(),
    ExtractDatePartsTransformation(),
    UnpivotTransformation(),
    PivotTransformation(),
    SplitColumnTransformation(),
    ParseDatesTransformation(),
    MapValuesTransformation(),
    WindowFunctionTransformation(),
    ConditionalColumnTransformation(),
    AssertNotNullTransformation(),
    AssertUniqueTransformation(),
    AssertValueRangeTransformation(),
    AssertExpressionTransformation(),
    AssertRowCountTransformation(),
    AssertValuesInSetTransformation(),
    PythonTransformTransformation(),
    FilterExpressionTransformation(),
    CombineColumnsTransformation(),
    CoalesceColumnsTransformation(),
    ExplodeRowsTransformation(),
    RollingAggregateTransformation(),
    RowDifferenceTransformation(),
    DateDifferenceTransformation(),
    ChartBarTransformation(),
    ChartLineTransformation(),
    ChartAreaTransformation(),
    ChartScatterTransformation(),
    ChartPieTransformation(),
    ChartHistogramTransformation(),
    ChartBoxPlotTransformation(),
    ChartHeatmapTransformation(),
)


def _register_ml_nodes() -> None:
    """Register ML nodes when the core ML libraries are installed.

    Gated on library *availability* (not ``ML_ENABLED``): a broken/stripped-down
    install that lacks scikit-learn, MLflow, or joblib never imports
    ``app.engine.transformations.ml`` at all. The ``ML_ENABLED`` flag gates the
    product surface (palette, routes) at the service layer, not the registry, so
    the engine can validate and run ML graphs in tests without restart gymnastics.
    The ML node modules import heavy libraries lazily, so registration stays cheap.
    """
    from app.ml.availability import ml_core_available

    if not ml_core_available():
        return
    before = set(_REGISTRY)
    from app.engine.transformations.ml.cross_validation import CrossValidateTransformation
    from app.engine.transformations.ml.evaluate import MLEvaluateTransformation
    from app.engine.transformations.ml.feature_engineering import (
        EncodeCategoriesTransformation,
        ReduceDimensionsTransformation,
        ScaleFeaturesTransformation,
        SelectFeaturesTransformation,
    )
    from app.engine.transformations.ml.importance import FeatureImportanceTransformation
    from app.engine.transformations.ml.predict import MLPredictTransformation
    from app.engine.transformations.ml.split import TrainTestSplitTransformation
    from app.engine.transformations.ml.train import (
        ClassifierModelTransformation,
        RegressorModelTransformation,
        TrainClassifierTransformation,
        TrainClusteringTransformation,
        TrainDimReductionTransformation,
        TrainForecasterTransformation,
        TrainRegressorTransformation,
    )

    _register(
        TrainTestSplitTransformation(),
        ScaleFeaturesTransformation(),
        EncodeCategoriesTransformation(),
        SelectFeaturesTransformation(),
        ReduceDimensionsTransformation(),
        ClassifierModelTransformation(),
        RegressorModelTransformation(),
        TrainClassifierTransformation(),
        TrainRegressorTransformation(),
        TrainClusteringTransformation(),
        TrainForecasterTransformation(),
        TrainDimReductionTransformation(),
        MLPredictTransformation(),
        MLEvaluateTransformation(),
        FeatureImportanceTransformation(),
        CrossValidateTransformation(),
    )
    _ML_TYPES.update(set(_REGISTRY) - before)


# Type names registered as ML nodes (empty when core ML deps are unavailable).
# Lets the API filter/hide ML nodes by category without hard-coding the list in
# two places.
_ML_TYPES: set[str] = set()

_register_ml_nodes()


def register_transformations(*transformations: BaseTransformation) -> None:
    """Register externally-provided transformations (e.g. a plugin's nodes) so the
    executor, codegen, and graph validation resolve them like built-ins. Raises
    ``ValueError`` on a duplicate type, so a plugin can never silently shadow a
    built-in node."""
    for t in transformations:
        if t.type in _REGISTRY:
            raise ValueError(f"transformation {t.type!r} is already registered")
        _REGISTRY[t.type] = t


def unregister_transformations(*types: str) -> None:
    """Remove externally-registered node types (plugin unload / test reset). No-op
    for unknown types."""
    for type_name in types:
        _REGISTRY.pop(type_name, None)


def get_transformation(node_type: str) -> BaseTransformation:
    if node_type not in _REGISTRY:
        raise KeyError(f"Unknown transformation type: {node_type!r}")
    return _REGISTRY[node_type]


def list_transformation_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def ml_node_types() -> set[str]:
    """The set of registered ML node type names (empty without core ML deps)."""
    return set(_ML_TYPES)


def is_ml_node(node_type: str) -> bool:
    return node_type in _ML_TYPES
