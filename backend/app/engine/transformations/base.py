# SPDX-License-Identifier: AGPL-3.0-only
import keyword
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend, numeric_filter_value


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


# Comparison values of filterRows and conditionalColumn conditions. An exported
# script doesn't know column dtypes, so it types a number-like text value at
# runtime with the engines' rule (backends.base.numeric_filter_value). Only the
# numeric-column check (IS_NUMERIC) differs per dialect.
_FILTER_VALUE_HELPER_TEMPLATE = '''def _filter_value(df, column, value):
    """Type a comparison value like its column: text becomes a number on a numeric column."""
    if isinstance(value, list):
        return [_filter_value(df, column, v) for v in value]
    numeric = IS_NUMERIC
    if not isinstance(value, str) or not numeric:
        return value
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Value {value!r} is not a number, but column {column!r} is numeric.") from None'''
FILTER_VALUE_HELPER_PANDAS = _FILTER_VALUE_HELPER_TEMPLATE.replace(
    "IS_NUMERIC",
    "pd.api.types.is_numeric_dtype(df[column]) and not pd.api.types.is_bool_dtype(df[column])",
)
FILTER_VALUE_HELPER_POLARS = _FILTER_VALUE_HELPER_TEMPLATE.replace(
    "IS_NUMERIC", "df.collect_schema()[column].is_numeric()"
)


def needs_typed_value(value: Any) -> bool:
    """Whether an exported comparison must type ``value`` at runtime via ``_filter_value``.

    Only text that parses as a number can compare differently by column type
    ('100' is 100 on a numeric column, '100' on a text one), and a flow-parameter
    reference (``CodeRef``) is unknown until the script runs. Other text stays a
    plain literal so exports read naturally (``_d['status'] == 'paid'``); against
    a numeric column such text is an invalid config the app rejects when it runs.
    """
    if isinstance(value, list):
        return any(needs_typed_value(v) for v in value)
    if isinstance(value, str):
        try:
            numeric_filter_value(value, "")
        except ValueError:
            return False
        return True
    return not (value is None or isinstance(value, (int, float)))


def typed_value_code(frame: str, column: Any, value: Any) -> str:
    """Source for ``value`` compared against ``frame[column]`` in an exported script."""
    return f"_filter_value({frame}, {column!r}, {value!r})" if needs_typed_value(value) else repr(value)


@dataclass
class NodeMetadata:
    """Non-frame outcomes a node surfaces onto its ``NodeResult``.

    ML nodes populate the ml_* fields. Assertion nodes populate the
    assertion_* fields. Chart nodes populate ``chart``. All fields are
    ``None`` for plain ETL nodes.
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

    # Chart node field: a render-ready, size-capped chart artifact (JSON) the
    # run view draws directly — see app.engine.transformations.charts.
    chart: dict[str, Any] | None = None


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

    def imports_for_inputs(self, config: dict[str, Any], input_vars: dict[str, str]) -> list[str]:
        """The pandas-code imports for this node given its connected input handles
        (``input_vars``, as passed to :meth:`to_python_code`). Defaults to
        :meth:`imports`; a node whose code depends on an optional input overrides
        it (mlPredict loads a model by URI only when no upstream model is wired)."""
        return self.imports(config)

    def polars_imports(self, config: dict[str, Any]) -> list[str]:
        """Extra imports for the generated **polars** script. Defaults to
        :meth:`imports` since most nodes need the same header in both dialects;
        a node whose pandas code needs something its polars code doesn't (e.g.
        conditionalColumn's ``numpy``) overrides this."""
        return self.imports(config)

    def helpers(self, config: dict[str, Any]) -> list[str]:
        """Top-level function definitions the generated pandas code calls (e.g.
        filterRows' ``_filter_value``). The code generator emits each distinct
        definition once, before the script body. Names start with ``_`` so flow
        parameters (which must start with a letter) cannot shadow them."""
        return []

    def polars_helpers(self, config: dict[str, Any]) -> list[str]:
        """:meth:`helpers` for the generated **polars** script. Not defaulted to
        :meth:`helpers`: a helper's body is dialect-specific."""
        return []

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
