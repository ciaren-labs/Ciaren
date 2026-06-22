from app.engine.transformations.base import BaseTransformation
from app.engine.transformations.columns import (
    CastDtypesTransformation,
    DropColumnsTransformation,
    RenameColumnsTransformation,
    SelectColumnsTransformation,
)
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
    ReplaceValuesTransformation,
    StringTransformTransformation,
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
)


def get_transformation(node_type: str) -> BaseTransformation:
    if node_type not in _REGISTRY:
        raise KeyError(f"Unknown transformation type: {node_type!r}")
    return _REGISTRY[node_type]


def list_transformation_types() -> list[str]:
    return sorted(_REGISTRY.keys())
