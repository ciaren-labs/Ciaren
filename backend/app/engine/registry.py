from app.engine.transformations.base import BaseTransformation
from app.engine.transformations.clean import (
    CastDtypesTransformation,
    DropColumnsTransformation,
    DropNullsTransformation,
    FillNullsTransformation,
    FilterRowsTransformation,
    RemoveDuplicatesTransformation,
    RenameColumnsTransformation,
    SelectColumnsTransformation,
    SortRowsTransformation,
)
from app.engine.transformations.join import JoinTransformation
from app.engine.transformations.reshape import (
    ConcatRowsTransformation,
    CreateCalculatedColumnTransformation,
    GroupByAggregateTransformation,
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
    GroupByAggregateTransformation(),
    ConcatRowsTransformation(),
    CreateCalculatedColumnTransformation(),
    JoinTransformation(),
)


def get_transformation(node_type: str) -> BaseTransformation:
    if node_type not in _REGISTRY:
        raise KeyError(f"Unknown transformation type: {node_type!r}")
    return _REGISTRY[node_type]


def list_transformation_types() -> list[str]:
    return sorted(_REGISTRY.keys())
