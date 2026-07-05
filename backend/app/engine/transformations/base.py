# SPDX-License-Identifier: AGPL-3.0-only
import keyword
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend


def is_safe_kwarg(name: Any) -> bool:
    """Whether a column name can render as a keyword argument (``assign(col=...)``).

    Must be a plain string identifier: parameterized names arrive as ``CodeRef``
    objects (rendered via ``!r``), keywords aren't valid kwargs, and ``self``
    would collide with the bound method's own first parameter.
    """
    return isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name) and name != "self"


def pd_assign_args(items: dict[Any, str]) -> str:
    """Render ``.assign(...)`` arguments the way a person would: keyword form
    (``assign(total=...)``) when every column name allows it, ``**{...}`` otherwise."""
    if all(is_safe_kwarg(k) for k in items):
        return ", ".join(f"{k}={v}" for k, v in items.items())
    return "**{" + ", ".join(f"{k!r}: {v}" for k, v in items.items()) + "}"


def pl_exprs_arg(exprs: list[str]) -> str:
    """Render a ``with_columns`` / ``agg`` argument list: a lone expression stays
    bare, several are joined positionally (polars accepts both)."""
    return ", ".join(exprs)


def one_or_list(cols: list[Any]) -> Any:
    """Collapse a single-element column list to its bare name for emission —
    ``sort_values('a')`` instead of ``sort_values(['a'])``. Every call site
    (pandas by/subset/on, polars sort/group_by/over/unique) accepts both forms."""
    return cols[0] if len(cols) == 1 and isinstance(cols[0], str) else cols


def polars_to_datetime_expr(schema_var: str, column_code: str, fmt: str | None = None, strict: bool = False) -> str:
    """Emitted-polars expression coercing a column to datetime the way the engine
    does: parse it if it is a string, cast it if it is already temporal.

    ``PolarsEngine`` dispatches on the column's dtype at runtime (see
    ``_to_datetime_expr``), which a static emitter cannot know — the dtype depends
    on upstream nodes. Emitters must therefore reproduce the dispatch in the
    generated code against a schema captured as ``{schema_var} =
    <frame>.collect_schema()`` (which works on eager and lazy frames alike).
    ``column_code`` is a code fragment evaluating to the column name — pass
    ``repr(col)`` for a literal, or a loop variable like ``"c"``.
    """
    fmt_part = f"format={fmt!r}, " if fmt is not None else ""
    return (
        f"(pl.col({column_code}).str.to_datetime({fmt_part}strict={strict}) "
        f"if {schema_var}[{column_code}] == pl.Utf8 "
        f"else pl.col({column_code}).cast(pl.Datetime, strict={strict}))"
    )


@dataclass
class NodeMetadata:
    """Non-frame outcomes a node surfaces onto its ``NodeResult``.

    ML nodes populate the ml_* fields. Assertion nodes populate the
    assertion_* fields. All fields are ``None`` for plain ETL nodes.
    """

    # ML node fields
    ml_metrics: dict[str, float] | None = None
    mlflow_run_id: str | None = None
    model_uri: str | None = None
    task_type: str | None = None
    cv_scores: list[float] | None = None

    # Assertion node fields
    assertion_passed: bool | None = None
    assertion_violation_count: int | None = None
    assertion_violating_sample: list[dict[str, Any]] | None = None


class BaseTransformation(ABC):
    """A single visual node's data operation.

    Transformations are engine-agnostic: ``execute`` receives an
    :class:`~app.engine.backends.base.EngineBackend` and delegates the actual
    DataFrame work to it, so the same node runs on pandas or polars unchanged.

    Handle conventions:
    - Single-input nodes read ``inputs["in"]`` and write ``{"out": ...}``.
    - Join reads ``inputs["left"]`` / ``inputs["right"]``.
    - Concat reads every value in ``inputs`` (variadic).
    """

    type: str

    #: Named input handles this node reads from. Single-input nodes use the
    #: default ``("in",)``; join overrides it with ``("left", "right")``.
    input_handles: tuple[str, ...] = ("in",)

    #: Input handles that may be connected but are not required (e.g. mlPredict's
    #: ``"model"`` handle, which is optional when a ``model_uri`` is in the config).
    #: Each accepts at most one edge; graph validation does not require them.
    optional_input_handles: tuple[str, ...] = ()

    #: When true the node accepts an arbitrary number of incoming edges on its
    #: ``"in"`` handle (concat). ``input_handles`` is then advisory.
    multi_input: bool = False

    #: Whether this node's ``to_polars_code`` runs on a ``LazyFrame`` unchanged.
    #: Most nodes are expression-based and lazy-safe; a few (``pivot``, ``sample``)
    #: have no lazy equivalent, so the lazy code generator materializes around
    #: them (``.collect()`` before, ``.lazy()`` after).
    polars_lazy_safe: bool = True

    def polars_lazy_safe_for(self, config: dict[str, Any]) -> bool:
        """Whether the emitted polars code for *this configuration* runs on a
        ``LazyFrame``. Defaults to the class-level flag; a node whose lazy
        compatibility depends on its config (e.g. ``binColumn``: quantile is a
        pure expression, equal-width needs eager min/max) overrides this so the
        lazy generator only materializes when it truly has to."""
        return self.polars_lazy_safe

    #: Whether this node's ``to_polars_code`` actually emits **pandas** code (e.g. ML
    #: nodes that wrap scikit-learn). The polars code generator bridges these by
    #: converting inputs to pandas (``.to_pandas()``) and results back
    #: (``pl.from_pandas(...)``) around the node, and pulls in its ``imports()`` —
    #: so a polars flow that contains an ML node still produces a runnable script.
    emits_pandas_code: bool = False

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None: ...

    @abstractmethod
    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]: ...

    @abstractmethod
    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        """Readable **pandas** code for this node (``df`` variables)."""
        ...

    def imports(self, config: dict[str, Any]) -> list[str]:
        """Extra top-level import lines the generated pandas script needs for this
        node (e.g. ``from sklearn... import ...``). Most nodes need none; the code
        generator collects and de-duplicates these into the script header. ``config``
        is provided because some nodes import different classes per option (e.g. the
        chosen scaler/imputer)."""
        return []

    def polars_imports(self, config: dict[str, Any]) -> list[str]:
        """Extra imports for the generated **polars** script. Defaults to
        :meth:`imports` since most nodes need the same header in both dialects;
        a node whose pandas code needs something its polars code doesn't (e.g.
        conditionalColumn's ``numpy``) overrides this."""
        return self.imports(config)

    @abstractmethod
    def to_polars_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        """Readable **polars** code for this node, co-located with ``execute`` and
        ``to_python_code`` so a node's whole definition lives in one place."""
        ...


class EmitsNodeMetadata(ABC):
    """Mixin for nodes that surface non-frame metadata (ML metrics, model refs).

    The executor detects this via ``isinstance`` and calls
    :meth:`execute_with_metadata` instead of :meth:`BaseTransformation.execute`, so
    the base ``execute`` signature — and all 28 ETL nodes — stay untouched.

    Metadata is **returned** alongside the frames, never stored on ``self``: the
    registry holds one shared singleton per node type, which may run concurrently
    under thread execution mode, so per-call state must not live on the instance.
    """

    #: Marker the executor checks before deciding whether to collect metadata.
    emits_metadata: bool = True

    @abstractmethod
    def execute_with_metadata(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        """Run the node, returning its output frames and the metadata to attach to
        the run's :class:`NodeResult`. :meth:`BaseTransformation.execute` should
        delegate here and drop the metadata, so preview (which only needs frames)
        and the run executor (which wants both) share one implementation."""
        ...
