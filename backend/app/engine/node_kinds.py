# SPDX-License-Identifier: AGPL-3.0-only
"""Single source of truth for input/output node types and their file formats.

Input and output node types used to be duplicated as literal sets/dicts across
the executor, code generator, graph validation, and dataset resolver. Keeping
them here keeps those four in sync and gives a new I/O node type exactly one
place to register.
"""

from dataclasses import dataclass
from typing import Any

# Input node type -> source_type understood by ``EngineBackend.read``.
INPUT_SOURCE_TYPES: dict[str, str] = {
    "csvInput": "csv",
    "excelInput": "excel",
    "parquetInput": "parquet",
    "jsonInput": "json",
    "textInput": "text",
}

# Unified uploaded-file input node. Its read format is selected in node config,
# mirroring ``fileOutput`` on the write side. Legacy single-format input nodes
# remain registered so existing flows keep running, but the palette can hide them.
FILE_INPUT_TYPE = "fileInput"
FILE_INPUT_FORMATS: tuple[str, ...] = ("csv", "tsv", "excel", "parquet", "json", "jsonl", "text")
DEFAULT_FILE_INPUT_FORMAT = "csv"

# Output node type -> source_type understood by ``EngineBackend.write``.
# ``sqlOutput`` and ``storageOutput`` are materialized to parquet by the executor;
# the execution service then pushes the parquet to the target via a connector.
# ``fileOutput`` is the unified local-file output: its format is chosen per-node in
# config (see ``output_source_type``). The legacy csv/excel/parquet output types
# remain registered (existing flows keep running) but are hidden from the palette.
OUTPUT_SOURCE_TYPES: dict[str, str] = {
    "csvOutput": "csv",
    "excelOutput": "excel",
    "parquetOutput": "parquet",
    "sqlOutput": "parquet",
    "storageOutput": "parquet",
}

# The unified local-file output node. Its format (and so its source_type) comes
# from the node config rather than the node type.
FILE_OUTPUT_TYPE = "fileOutput"
#: Formats the File Output node can write.
FILE_OUTPUT_FORMATS: tuple[str, ...] = ("csv", "tsv", "excel", "parquet", "json", "jsonl", "text")
DEFAULT_FILE_OUTPUT_FORMAT = "csv"

# File extension written for each output source_type.
OUTPUT_SUFFIX: dict[str, str] = {
    "csv": ".csv",
    "tsv": ".tsv",
    "excel": ".xlsx",
    "parquet": ".parquet",
    "json": ".json",
    "jsonl": ".jsonl",
    "text": ".txt",
}


def output_source_type(node_type: str, config: dict[str, Any] | None = None) -> str:
    """The engine ``source_type`` an output node writes.

    Fixed by type for the legacy/SQL/storage outputs; taken from ``config['format']``
    for the unified ``fileOutput`` node (defaulting to CSV)."""
    if node_type == FILE_OUTPUT_TYPE:
        fmt = (config or {}).get("format") or DEFAULT_FILE_OUTPUT_FORMAT
        if fmt not in FILE_OUTPUT_FORMATS:
            raise ValueError(f"fileOutput: unknown format {fmt!r}. Allowed: {', '.join(FILE_OUTPUT_FORMATS)}.")
        return fmt
    return OUTPUT_SOURCE_TYPES[node_type]


def input_source_type(node_type: str, config: dict[str, Any] | None = None) -> str:
    """The engine ``source_type`` an uploaded-file input node reads."""
    if node_type == FILE_INPUT_TYPE:
        fmt = (config or {}).get("format") or DEFAULT_FILE_INPUT_FORMAT
        if fmt not in FILE_INPUT_FORMATS:
            raise ValueError(f"fileInput: unknown format {fmt!r}. Allowed: {', '.join(FILE_INPUT_FORMATS)}.")
        return fmt
    return INPUT_SOURCE_TYPES[node_type]


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
INPUT_TYPES: frozenset[str] = frozenset(INPUT_SOURCE_TYPES) | {FILE_INPUT_TYPE} | PRE_MATERIALIZED_INPUT_TYPES
OUTPUT_TYPES: frozenset[str] = frozenset(OUTPUT_SOURCE_TYPES) | {FILE_OUTPUT_TYPE}

# The task-scoped train nodes. Each fits a model and emits a single "model" wire.
# Kept as plain strings here so node_kinds stays free of any ML imports (the [ml]
# extra is optional); the authoritative mapping lives in app/ml/models.py.
TRAIN_NODE_TYPES: tuple[str, ...] = (
    "mlTrainClassifier",
    "mlTrainRegressor",
    "mlTrainClustering",
    "mlTrainForecaster",
    "mlTrainDimReduction",
)
MODEL_DEFINITION_NODE_TYPES: tuple[str, ...] = (
    "mlClassifierModel",
    "mlRegressorModel",
)

# Nodes that are a valid terminal *result* of a flow even without a file-output
# node: a train node persists a model to MLflow, so a "train only" graph
# (csvInput -> ... -> mlTrainClassifier) is complete. Graph validation accepts
# these in lieu of an OUTPUT_TYPES node.
ML_OUTPUT_NODES: frozenset[str] = frozenset(TRAIN_NODE_TYPES)

# Report nodes whose result is a score/metrics frame: a valid flow terminal even
# without a downstream file-output node (the scores show in the inspector), though
# the frame can also be wired onward to an output. Cross-validation is one.
ML_REPORT_NODES: frozenset[str] = frozenset({"mlCrossValidate"})

# Every node that makes a flow "complete" on its own (no output node required).
FLOW_TERMINAL_NODES: frozenset[str] = ML_OUTPUT_NODES | ML_REPORT_NODES

# Nodes that emit more than one named output frame. The executor stores a frame
# per (node, handle); downstream edges select which one via ``sourceHandle``. The
# first handle listed is the node's *primary* output — the one sampled for the
# read-only run DAG (NodeResult) and returned by single-frame helpers like
# ``compute_frames``. Single-output nodes are absent here and default to "out".
MULTI_OUTPUT_NODES: dict[str, tuple[str, ...]] = {
    # ML: trainTestSplit emits two frames; "train" is the primary (sampled) output.
    "trainTestSplit": ("train", "test"),
}

# -- model handles ----------------------------------------------------------
# A "model" connection carries a trained model, not a dataframe. It is its own
# kind of wire: a model output may only feed a model input (graph validation
# enforces this), so a model can never be mis-wired into a data input (or written
# to a file). mlTrain's single output IS the model; mlPredict / featureImportance
# consume it on a dedicated "model" input handle.

#: Output handles (by node type) that carry a model rather than a frame.
MODEL_OUTPUT_HANDLES: dict[str, frozenset[str]] = {
    t: frozenset({"model"}) for t in (*TRAIN_NODE_TYPES, *MODEL_DEFINITION_NODE_TYPES)
}
#: Input handles (by node type) that expect a model rather than a frame.
MODEL_INPUT_HANDLES: dict[str, frozenset[str]] = {
    "mlPredict": frozenset({"model"}),
    "featureImportance": frozenset({"model"}),
    "mlCrossValidate": frozenset({"model"}),
}


# -- plugin node kinds --------------------------------------------------------
# The sets above are static because the core node set is static. Plugin nodes
# arrive at runtime with their topology declared in a NodeSpec; the plugin bridge
# (app/plugins/runtime.py) registers each executable plugin node here so graph
# validation, the executor, and both code generators treat its handles — including
# model wires and flow-terminal behavior — exactly like a built-in's.


@dataclass(frozen=True)
class PluginNodeKind:
    """Handle topology + terminal flags for one plugin-contributed node type."""

    output_handles: tuple[str, ...] = ("out",)
    model_input_handles: frozenset[str] = frozenset()
    model_output_handles: frozenset[str] = frozenset()
    flow_terminal: bool = False
    model_sink: bool = False


_PLUGIN_NODE_KINDS: dict[str, PluginNodeKind] = {}


def register_plugin_node_kind(
    node_type: str,
    *,
    output_handles: tuple[str, ...] = ("out",),
    model_input_handles: frozenset[str] = frozenset(),
    model_output_handles: frozenset[str] = frozenset(),
    flow_terminal: bool = False,
    model_sink: bool = False,
) -> None:
    """Register a plugin node's handle topology. A core node type cannot be
    shadowed (the engine registry already refuses duplicate transformations; this
    guard keeps the kind tables consistent even if that changes)."""
    if node_type in MODEL_OUTPUT_HANDLES or node_type in MODEL_INPUT_HANDLES or node_type in MULTI_OUTPUT_NODES:
        raise ValueError(f"node type {node_type!r} is a built-in and cannot be re-registered")
    _PLUGIN_NODE_KINDS[node_type] = PluginNodeKind(
        output_handles=tuple(output_handles) or ("out",),
        model_input_handles=frozenset(model_input_handles),
        model_output_handles=frozenset(model_output_handles),
        flow_terminal=flow_terminal,
        model_sink=model_sink,
    )


def unregister_plugin_node_kinds(*node_types: str) -> None:
    """Remove plugin node kinds (used when the plugin registry is rebuilt)."""
    for node_type in node_types:
        _PLUGIN_NODE_KINDS.pop(node_type, None)


def registered_plugin_node_kinds() -> tuple[str, ...]:
    return tuple(_PLUGIN_NODE_KINDS)


def model_output_handles(node_type: str) -> frozenset[str]:
    """Output handles of ``node_type`` that carry a model (core or plugin)."""
    static = MODEL_OUTPUT_HANDLES.get(node_type)
    if static is not None:
        return static
    kind = _PLUGIN_NODE_KINDS.get(node_type)
    return kind.model_output_handles if kind else frozenset()


def model_input_handles(node_type: str) -> frozenset[str]:
    """Input handles of ``node_type`` that expect a model (core or plugin)."""
    static = MODEL_INPUT_HANDLES.get(node_type)
    if static is not None:
        return static
    kind = _PLUGIN_NODE_KINDS.get(node_type)
    return kind.model_input_handles if kind else frozenset()


def multi_output_handles(node_type: str) -> tuple[str, ...] | None:
    """The declared handle tuple for a node with more than one output, else None."""
    static = MULTI_OUTPUT_NODES.get(node_type)
    if static is not None:
        return static
    kind = _PLUGIN_NODE_KINDS.get(node_type)
    if kind and len(kind.output_handles) > 1:
        return kind.output_handles
    return None


def is_flow_terminal(node_type: str) -> bool:
    """Whether ``node_type`` completes a flow on its own (no output node needed)."""
    if node_type in FLOW_TERMINAL_NODES:
        return True
    kind = _PLUGIN_NODE_KINDS.get(node_type)
    return bool(kind and kind.flow_terminal)


def is_model_sink(node_type: str) -> bool:
    """Whether ``node_type`` persists a model as a terminal result (e.g. mlTrain)."""
    if node_type in ML_OUTPUT_NODES:
        return True
    kind = _PLUGIN_NODE_KINDS.get(node_type)
    return bool(kind and kind.model_sink)


def output_handles(node_type: str) -> tuple[str, ...]:
    """Declared output handles for a node type.

    Multi-output nodes are listed in ``MULTI_OUTPUT_NODES``; a model-emitting node
    (mlTrain) declares its single ``"model"`` handle; plugin nodes declare theirs
    at registration; everything else defaults to the implicit ``"out"``.
    """
    if node_type in MULTI_OUTPUT_NODES:
        return MULTI_OUTPUT_NODES[node_type]
    kind = _PLUGIN_NODE_KINDS.get(node_type)
    if kind is not None:
        return kind.output_handles
    model_out = MODEL_OUTPUT_HANDLES.get(node_type)
    if model_out:
        return tuple(sorted(model_out))
    return ("out",)


def primary_output_handle(node_type: str) -> str:
    """The handle whose frame represents the node in the run DAG / single-frame views."""
    return output_handles(node_type)[0]


def edge_carries_model(source_type: str, source_handle: str | None) -> bool:
    """Whether an edge leaving ``source_type`` (via ``source_handle``) carries a
    trained model rather than a dataframe. For a single-output model node (mlTrain)
    the edge has no ``sourceHandle`` and resolves to its sole model handle."""
    handles = model_output_handles(source_type)
    if not handles:
        return False
    resolved = source_handle or primary_output_handle(source_type)
    return resolved in handles


def is_model_input_handle(node_type: str, handle: str) -> bool:
    """Whether ``handle`` on ``node_type`` expects a model rather than a frame."""
    return handle in model_input_handles(node_type)
