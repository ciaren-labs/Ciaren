"""Single source of truth for input/output node types and their file formats.

Input and output node types used to be duplicated as literal sets/dicts across
the executor, code generator, graph validation, and dataset resolver. Keeping
them here keeps those four in sync and gives a new I/O node type exactly one
place to register.
"""

# Input node type -> source_type understood by ``EngineBackend.read``.
INPUT_SOURCE_TYPES: dict[str, str] = {
    "csvInput": "csv",
    "excelInput": "excel",
    "parquetInput": "parquet",
}

# Output node type -> source_type understood by ``EngineBackend.write``.
# ``sqlOutput`` and ``storageOutput`` are materialized to parquet by the executor;
# the execution service then pushes the parquet to the target via a connector.
OUTPUT_SOURCE_TYPES: dict[str, str] = {
    "csvOutput": "csv",
    "excelOutput": "excel",
    "parquetOutput": "parquet",
    "sqlOutput": "parquet",
    "storageOutput": "parquet",
}

# File extension written for each output source_type.
OUTPUT_SUFFIX: dict[str, str] = {
    "csv": ".csv",
    "excel": ".xlsx",
    "parquet": ".parquet",
}

# Database-backed I/O nodes (resolved via app/connectors/sql, not the file engine).
SQL_INPUT_TYPE = "sqlInput"
SQL_OUTPUT_TYPE = "sqlOutput"

# Object/file-storage I/O nodes (resolved via app/connectors storage connectors).
STORAGE_INPUT_TYPE = "storageInput"
STORAGE_OUTPUT_TYPE = "storageOutput"

# All "pre-materialized" input types — resolved in the async parent layer to a
# parquet snapshot; the executor reads the snapshot, never the live source.
PRE_MATERIALIZED_INPUT_TYPES: frozenset[str] = frozenset({SQL_INPUT_TYPE, STORAGE_INPUT_TYPE})

#: Membership sets — use these for ``in`` checks.
INPUT_TYPES: frozenset[str] = frozenset(INPUT_SOURCE_TYPES) | PRE_MATERIALIZED_INPUT_TYPES
OUTPUT_TYPES: frozenset[str] = frozenset(OUTPUT_SOURCE_TYPES)

# Nodes that emit more than one named output frame. The executor stores a frame
# per (node, handle); downstream edges select which one via ``sourceHandle``. The
# first handle listed is the node's *primary* output — the one sampled for the
# read-only run DAG (NodeResult) and returned by single-frame helpers like
# ``compute_frames``. Single-output nodes are absent here and default to "out".
MULTI_OUTPUT_NODES: dict[str, tuple[str, ...]] = {
    # ML: trainTestSplit emits two frames; "train" is the primary (sampled) output.
    "trainTestSplit": ("train", "test"),
}


def output_handles(node_type: str) -> tuple[str, ...]:
    """Declared output handles for a node type (``("out",)`` for single-output)."""
    return MULTI_OUTPUT_NODES.get(node_type, ("out",))


def primary_output_handle(node_type: str) -> str:
    """The handle whose frame represents the node in the run DAG / single-frame views."""
    return output_handles(node_type)[0]
