"""Central definitions for the app's closed-set string options.

Previously these lived as bare string literals scattered across models, services,
schemas and routes (with the allowed values only documented in comments). Defining
them once as :class:`StrEnum`s gives a single source of truth, request/response
validation, OpenAPI ``enum`` docs, and IDE autocomplete — while still behaving as
plain strings at the DB / sklearn / polars boundaries (``StrEnum`` *is* ``str``).
"""

from __future__ import annotations

from enum import StrEnum


class Engine(StrEnum):
    """Dataframe engine used to execute a flow."""

    PANDAS = "pandas"
    POLARS = "polars"


class ExecutionMode(StrEnum):
    """How the synchronous executor is run off the event loop."""

    THREAD = "thread"
    PROCESS = "process"


class RunStatus(StrEnum):
    """Lifecycle status of a :class:`FlowRun`."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class NodeStatus(StrEnum):
    """Per-node outcome within a run (a node may be skipped, a run may not)."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunTrigger(StrEnum):
    """What started a run."""

    MANUAL = "manual"
    SCHEDULE = "schedule"
    RETRY = "retry"
    SEED = "seed"


class DatasetKind(StrEnum):
    """Whether a dataset was uploaded or produced by a flow."""

    INPUT = "input"
    OUTPUT = "output"


class MLTask(StrEnum):
    """Learning task a model/evaluation targets."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    DIMENSIONALITY_REDUCTION = "dimensionality_reduction"


class RunSortField(StrEnum):
    """Sortable columns for ``GET /api/runs``."""

    CREATED_AT = "created_at"
    STARTED_AT = "started_at"
    STATUS = "status"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class TransformationCategory(StrEnum):
    """Palette category filter for ``GET /api/transformations``."""

    ML = "ml"
    ETL = "etl"


class ParameterType(StrEnum):
    """Declared type of a flow parameter (controls coercion of its value)."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
