"""Shared base classes for ML nodes.

``MLTransformation`` bridges FlowFrame's engine-agnostic frame world to sklearn,
which only speaks pandas/numpy: subclasses work in pandas via ``engine.to_pandas``
and hand results back with ``engine.from_pandas`` (Arrow-backed for polars), so an
ML node can sit inside a polars flow and still return a frame of the active engine.

``MetadataMLTransformation`` adds the metadata side-channel for nodes that surface
metrics / a model URI (mlTrain, mlEvaluate, featureImportance) onto their
``NodeResult`` — see :class:`app.engine.transformations.base.EmitsNodeMetadata`.
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import (
    BaseTransformation,
    EmitsNodeMetadata,
    NodeMetadata,
)


class MLSchema:
    """The minimal, data-free description an ML node's ``validate_with_schema`` sees
    at run start: column names and an optional row count (from the upstream
    ``DatasetVersion`` or propagated node schema). Kept tiny on purpose — full data
    is not loaded just to validate config."""

    def __init__(self, columns: list[str], row_count: int | None = None) -> None:
        self.columns = columns
        self.row_count = row_count


class MLTransformation(BaseTransformation):
    """Base for ML nodes. Provides the pandas boundary, pandas-based codegen, and a
    data-aware validation hook. Subclasses implement :meth:`validate_config`,
    :meth:`execute`, and :meth:`to_python_code`."""

    # sklearn operations have no lazy-polars equivalent; the polars code generator
    # must materialize around them.
    polars_lazy_safe = False

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        """Optional data-aware validation run at run start (and on save), once the
        upstream column names / row count are known. Cheap, config-only checks stay
        in :meth:`validate_config` so preview and the frontend surface them instantly.
        Default: no extra checks."""
        return None

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        """ML steps use scikit-learn (pandas/numpy); there is no native polars
        equivalent, so emit the same pandas body on either engine. The polars code
        generator materializes around it (``polars_lazy_safe = False``)."""
        return self.to_python_code(input_vars, output_vars, config)

    # -- helpers for subclasses ----------------------------------------------

    @staticmethod
    def _to_pandas(engine: EngineBackend, frame: AnyFrame) -> Any:
        return engine.to_pandas(frame)

    @staticmethod
    def _from_pandas(engine: EngineBackend, pdf: Any) -> AnyFrame:
        return engine.from_pandas(pdf)


class MetadataMLTransformation(MLTransformation, EmitsNodeMetadata):
    """An ML node that also surfaces non-frame metadata onto its NodeResult.

    Subclasses implement :meth:`execute_with_metadata`; :meth:`execute` delegates to
    it and drops the metadata, so preview (frames only) and the run executor (frames
    + metadata) share one implementation. Metadata is returned, never stored on
    ``self`` — the registry holds a single shared instance per node type.
    """

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frames, _meta = self.execute_with_metadata(engine, inputs, config)
        return frames

    @abstractmethod
    def execute_with_metadata(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]: ...
