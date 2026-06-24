from app.engine.transformations.base import BaseTransformation
from app.engine.transformations.columns import (
    CastDtypesTransformation,
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
from app.engine.transformations.reshape import (
    ConcatRowsTransformation,
    CreateCalculatedColumnTransformation,
    ExtractDatePartsTransformation,
    GroupByAggregateTransformation,
    ParseDatesTransformation,
    PivotTransformation,
    UnpivotTransformation,
)
from app.engine.transformations.rows import (
    FilterRowsTransformation,
    LimitRowsTransformation,
    RemoveDuplicatesTransformation,
    SampleRowsTransformation,
    SortRowsTransformation,
)
from app.engine.transformations.text import (
    MapValuesTransformation,
    ReplaceValuesTransformation,
    SplitColumnTransformation,
    StringTransformTransformation,
)
from app.engine.transformations.window import WindowFunctionTransformation

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
)


def _register_ml_nodes() -> None:
    """Register ML nodes when the ``[ml]`` extra is installed.

    Gated on library *availability* (not ``ML_ENABLED``): a base install without
    the extra never imports ``app.engine.transformations.ml`` at all, keeping it
    import-isolated per the architecture guide. The ``ML_ENABLED`` flag gates the
    product surface (palette, routes) at the service layer, not the registry — so
    the engine can validate and run ML graphs in tests without restart gymnastics.
    The ML node modules import sklearn lazily, so this stays cheap.
    """
    from app.ml.availability import ml_core_available

    if not ml_core_available():
        return
    before = set(_REGISTRY)
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
    from app.engine.transformations.ml.train import MLTrainTransformation

    _register(
        TrainTestSplitTransformation(),
        ScaleFeaturesTransformation(),
        EncodeCategoriesTransformation(),
        SelectFeaturesTransformation(),
        ReduceDimensionsTransformation(),
        MLTrainTransformation(),
        MLPredictTransformation(),
        MLEvaluateTransformation(),
        FeatureImportanceTransformation(),
    )
    _ML_TYPES.update(set(_REGISTRY) - before)


# Type names registered as ML nodes (empty when the [ml] extra is absent). Lets the
# API filter/hide ML nodes by category without hard-coding the list in two places.
_ML_TYPES: set[str] = set()

_register_ml_nodes()


def get_transformation(node_type: str) -> BaseTransformation:
    if node_type not in _REGISTRY:
        raise KeyError(f"Unknown transformation type: {node_type!r}")
    return _REGISTRY[node_type]


def list_transformation_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def ml_node_types() -> set[str]:
    """The set of registered ML node type names (empty without the [ml] extra)."""
    return set(_ML_TYPES)


def is_ml_node(node_type: str) -> bool:
    return node_type in _ML_TYPES
