"""A mandatory structural contract for every registered transformation node.

Per-node *behavior* is covered elsewhere (``test_transformation_codegen.py`` drives
each node's pandas/polars codegen branches; ``test_demo_seed.py`` executes real
flows end-to-end on both engines; ``test_polars_lazy_safety.py`` covers lazy
materialization). What was only ever *spot-checked* — on join, concat, and the
I/O nodes — is the cross-cutting structural contract every node must satisfy:
well-formed input handles, disjoint optional handles, consistent flags, a
config-safe lazy-safety hook, string-list imports, and a catalog entry with a
real label. This module enforces that uniformly across every built-in
transformation in the registry, so a new node can't quietly violate the
conventions the executor, codegen, and graph validation rely on. (Output-handle
topology and I/O nodes are derived elsewhere — see ``tests/plugins/test_builtin.py``
— and runtime plugin registration is out of this static sweep's reach.)

The handle rules are expressed as a single ``_handle_violations`` detector that
is exercised both against every real node (must be clean) and against
deliberately-broken stub nodes (must be flagged), so the guard itself can't rot
into a vacuous pass.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.node_metadata import CATEGORY_LABELS, NODE_META_BY_TYPE
from app.engine.registry import (
    get_transformation,
    is_ml_node,
    list_transformation_types,
)
from app.engine.transformations.base import BaseTransformation, EmitsNodeMetadata

# Snapshot the registry once; ML node types are present only when core ML deps
# are installed, so the parametrization adapts to the environment.
_TYPES = list_transformation_types()


def _default_config(node_type: str) -> dict[str, Any]:
    """The node's catalog default config — a safe, representative config that its
    own hooks (imports / lazy-safety) must handle without crashing."""
    meta = NODE_META_BY_TYPE.get(node_type)
    return dict(meta.default_config) if meta is not None else {}


def _handle_violations(t: BaseTransformation) -> list[str]:
    """Every way ``t``'s handle declarations break the documented conventions.

    Empty list == conformant. Shared by the positive sweep and the negative
    stub tests so the detector can't silently stop detecting.
    """
    problems: list[str] = []

    if not isinstance(t.input_handles, tuple) or not t.input_handles:
        problems.append("input_handles must be a non-empty tuple")
    else:
        if not all(isinstance(h, str) and h for h in t.input_handles):
            problems.append("input_handles entries must be non-empty strings")
        if len(set(t.input_handles)) != len(t.input_handles):
            problems.append("input_handles must be unique")

    if not isinstance(t.optional_input_handles, tuple):
        problems.append("optional_input_handles must be a tuple")
    else:
        if not all(isinstance(h, str) and h for h in t.optional_input_handles):
            problems.append("optional_input_handles entries must be non-empty strings")
        if isinstance(t.input_handles, tuple) and not set(t.optional_input_handles).isdisjoint(t.input_handles):
            problems.append("optional_input_handles must be disjoint from input_handles")

    if t.multi_input and t.input_handles != ("in",):
        problems.append("multi_input nodes must expose only the single 'in' handle")

    return problems


# ---------------------------------------------------------------------------
# Positive sweep: every registered node satisfies the contract
# ---------------------------------------------------------------------------


def test_registry_is_populated() -> None:
    # The 28 core ETL transformations are always registered, independent of ML.
    assert len(_TYPES) >= 28


@pytest.mark.parametrize("node_type", _TYPES)
def test_registry_key_matches_declared_type(node_type: str) -> None:
    assert get_transformation(node_type).type == node_type


@pytest.mark.parametrize("node_type", _TYPES)
def test_is_a_base_transformation(node_type: str) -> None:
    assert isinstance(get_transformation(node_type), BaseTransformation)


@pytest.mark.parametrize("node_type", _TYPES)
def test_handles_are_wellformed(node_type: str) -> None:
    assert _handle_violations(get_transformation(node_type)) == []


@pytest.mark.parametrize("node_type", _TYPES)
def test_flags_are_booleans(node_type: str) -> None:
    t = get_transformation(node_type)
    assert isinstance(t.multi_input, bool)
    assert isinstance(t.polars_lazy_safe, bool)
    assert isinstance(t.emits_pandas_code, bool)


@pytest.mark.parametrize("node_type", _TYPES)
def test_lazy_safety_hook_returns_bool_for_default_config(node_type: str) -> None:
    # binColumn (and any future config-dependent node) overrides this; it must
    # never crash on the node's own default config and must return a bool.
    result = get_transformation(node_type).polars_lazy_safe_for(_default_config(node_type))
    assert isinstance(result, bool)


@pytest.mark.parametrize("node_type", _TYPES)
def test_imports_are_lists_of_nonempty_strings(node_type: str) -> None:
    t = get_transformation(node_type)
    cfg = _default_config(node_type)
    try:
        emitted = (t.imports(cfg), t.polars_imports(cfg))
    except ValueError as exc:
        # The ONLY tolerated rejection: a node whose imports derive from a chosen
        # option whose catalog default is a "Models coming soon" placeholder
        # (mlTrainForecaster ships model_type=""). Pinning to that message keeps
        # this from silently swallowing a genuinely broken imports() or a
        # template/imports key mismatch (which would raise a KeyError and fail).
        if "model_type" not in str(exc):
            raise
        pytest.skip(f"{node_type} imports require a chosen model_type its default template leaves blank")
    for lines in emitted:
        assert isinstance(lines, list)
        assert all(isinstance(line, str) and line for line in lines)


@pytest.mark.parametrize("node_type", _TYPES)
def test_has_catalog_metadata_with_a_real_label(node_type: str) -> None:
    meta = NODE_META_BY_TYPE.get(node_type)
    assert meta is not None, f"{node_type} has no catalog metadata"
    assert meta.label and meta.label != node_type, "label must be human, not the raw type slug"
    assert meta.category in CATEGORY_LABELS, f"unknown category {meta.category!r}"
    assert isinstance(meta.default_config, dict)


@pytest.mark.parametrize("node_type", _TYPES)
def test_ml_nodes_are_categorized_ml(node_type: str) -> None:
    if is_ml_node(node_type):
        assert NODE_META_BY_TYPE[node_type].category == "ml"


@pytest.mark.parametrize("node_type", _TYPES)
def test_metadata_emitter_flag_is_consistent(node_type: str) -> None:
    t = get_transformation(node_type)
    if isinstance(t, EmitsNodeMetadata):
        assert t.emits_metadata is True


# ---------------------------------------------------------------------------
# Negative cases: the detector actually flags broken nodes
# ---------------------------------------------------------------------------


class _StubTransform(BaseTransformation):
    """Minimal concrete node used to build deliberately-broken variants."""

    type = "stub"

    def validate_config(self, config: dict[str, Any]) -> None:
        return None

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": inputs["in"]}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        return f"{output_vars['out']} = {input_vars['in']}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        return f"{output_vars['out']} = {input_vars['in']}"


def test_stub_node_is_itself_conformant() -> None:
    assert _handle_violations(_StubTransform()) == []


def test_detector_flags_empty_input_handles() -> None:
    class Bad(_StubTransform):
        input_handles = ()

    assert "input_handles must be a non-empty tuple" in _handle_violations(Bad())


def test_detector_flags_duplicate_input_handles() -> None:
    class Bad(_StubTransform):
        input_handles = ("in", "in")

    assert "input_handles must be unique" in _handle_violations(Bad())


def test_detector_flags_optional_overlapping_required() -> None:
    class Bad(_StubTransform):
        input_handles = ("in", "model")
        optional_input_handles = ("model",)

    assert "optional_input_handles must be disjoint from input_handles" in _handle_violations(Bad())


def test_detector_flags_multi_input_with_extra_handles() -> None:
    class Bad(_StubTransform):
        multi_input = True
        input_handles = ("left", "right")

    assert "multi_input nodes must expose only the single 'in' handle" in _handle_violations(Bad())


def test_detector_flags_blank_handle_name() -> None:
    class Bad(_StubTransform):
        input_handles = ("",)

    assert "input_handles entries must be non-empty strings" in _handle_violations(Bad())
