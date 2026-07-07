# SPDX-License-Identifier: AGPL-3.0-only
"""Shared driver logic for the pandas / polars code generators.

Everything that must behave identically in both generated dialects lives here,
so a fix in one driver cannot silently miss the other: edge → variable
resolution (including multi-output ``sourceHandle`` routing), input-variable
collection, import ordering, SQL engine-variable allocation, and liveness.

The non-trivial bit is liveness analysis: every node's dataframe variable is
dead once its **last** consumer has run. Both generators use it two ways —
to reuse a dead variable as the consumer's output (``df_1 = df_1.head(5)``
instead of minting ``df_2``), and, under the optional ``del``
("free intermediates") mode, to release variables that could not be reused
(see :class:`DelScheduler`).
"""

import ast
import re
from typing import Any, NamedTuple

from app.engine.graph import GraphValidationError
from app.engine.sql_codegen import engine_url_parts

_SELF_ASSIGN = re.compile(r"^(\w+) = \1$")


def strip_self_assign(code: str) -> str:
    """Drop no-op ``x = x`` lines from an emitted snippet.

    Emitters that build their output incrementally seed it with ``dst = src``
    before appending per-item lines; under variable reuse dst and src are the
    same name and the seed degenerates to ``df_1 = df_1``. Filtering here keeps
    every emitter's seed-line idiom valid instead of making each one dst==src
    aware."""
    lines = [line for line in code.split("\n") if not _SELF_ASSIGN.match(line)]
    return "\n".join(lines) or code


# Only generated dataframe variables participate in chain fusion; everything
# else (module aliases like pd/pl, _eager_N temps, _engine_N) is left alone.
# Covers both the numbered fallback (df_1) and semantic names (df_sales).
_DF_VAR = re.compile(r"df_\w+$")

# A fused chain longer than this is rendered in parenthesized fluent style,
# one method call per line; at or below it, as a plain single-line statement.
_MAX_SINGLE_LINE = 88


class _ChainStep(NamedTuple):
    """One fusible statement ``target = root.method(...)…``, decomposed.

    ``dots`` are offsets into ``rhs`` of the spine dots — the ``.`` of each
    method call applied directly to the running dataframe (not dots inside
    arguments) — used to break a long chain one call per line.
    ``target_refs`` counts occurrences of ``target`` in the RHS: a statement
    whose RHS mentions its own target more than once (``df_1 =
    df_1[df_1['a'] > 0]``) reads the *pre-statement* value in those extra
    references, so it may only start a fused chain, never continue one
    (mid-chain, the extra references would see the pre-chain frame while the
    spine sees the running result — a semantic change).
    """

    target: str
    root: str
    rhs: str
    dots: list[int]
    target_refs: int


def _chain_step(line: str) -> _ChainStep | None:
    """Decompose ``line`` if it is a fusible single-statement assignment.

    Fusible means: one physical line, no comment, a single ``Assign`` to a bare
    ``df_N`` name, whose RHS is a chain of calls / attribute accesses /
    subscripts rooted at another bare ``df_N`` name. Anything else — reads
    (``pd.read_csv``), writes, ``del``, ``with`` blocks, multi-line snippets,
    temps — returns None and acts as a chain boundary.
    """
    if "\n" in line or "#" in line or " = " not in line:
        return None
    try:
        tree = ast.parse(line)
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign):
        return None
    assign = tree.body[0]
    if len(assign.targets) != 1 or not isinstance(assign.targets[0], ast.Name):
        return None
    target = assign.targets[0].id
    if not _DF_VAR.match(target):
        return None
    node: ast.expr = assign.value
    dots: list[int] = []
    while True:
        if isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Attribute):
            if node.value.end_col_offset is not None:
                dots.append(node.value.end_col_offset)
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        else:
            break
    if not isinstance(node, ast.Name) or not _DF_VAR.match(node.id):
        return None
    # ast col offsets count UTF-8 *bytes*; str slicing counts characters. Any
    # non-ASCII text (accented column names) shifts byte offsets past the char
    # position — translate before slicing or a split lands mid-string-literal.
    if line.isascii():
        rhs_start = assign.value.col_offset
        char_dots = dots
    else:
        raw = line.encode("utf-8")
        rhs_start = len(raw[: assign.value.col_offset].decode("utf-8"))
        char_dots = [len(raw[:d].decode("utf-8")) for d in dots]
    rhs = line[rhs_start:]
    # Keep only offsets that really are spine dots (generated code never puts
    # whitespace around them; if it ever did, we skip that split point).
    rel_dots = sorted(d - rhs_start for d in char_dots if rhs[d - rhs_start : d - rhs_start + 1] == ".")
    target_refs = sum(1 for n in ast.walk(assign.value) if isinstance(n, ast.Name) and n.id == target)
    return _ChainStep(target, node.id, rhs, rel_dots, target_refs)


def _step_suffix(step: _ChainStep) -> str | None:
    """What a continuation step appends to the running chain (``.method(...)``
    or a plain subscript), or None if the RHS doesn't literally start with the
    root variable followed by ``.`` or ``[``."""
    if not step.rhs.startswith(step.root):
        return None
    suffix = step.rhs[len(step.root) :]
    if not suffix or suffix[0] not in ".[":
        return None
    return suffix


def _segments(step: _ChainStep) -> list[str]:
    """Split a step's RHS at its spine dots: ``df_1.groupby(x).agg(y)`` →
    ``['df_1', '.groupby(x)', '.agg(y)']``."""
    bounds = [0, *step.dots, len(step.rhs)]
    return [step.rhs[a:b] for a, b in zip(bounds, bounds[1:]) if step.rhs[a:b]]


def _render_chain(group: list[_ChainStep]) -> list[str]:
    """Render a run of ≥2 fusible steps as one fluent statement."""
    target = group[0].target
    suffixes = [_step_suffix(s) or "" for s in group[1:]]  # caller guarantees not None
    single = f"{target} = {group[0].rhs}" + "".join(suffixes)
    if len(single) <= _MAX_SINGLE_LINE:
        return [single]
    # One fragment per spine call: the first step contributes its full RHS
    # (split at its spine dots), each continuation its suffix (likewise split).
    fragments = _segments(group[0])
    for step in group[1:]:
        segs = _segments(step)
        head = segs[0][len(step.root) :]  # subscript between root and first dot, if any
        if head:
            fragments.append(head)
        fragments.extend(segs[1:])
    # A subscript fragment continues the previous physical line — a leading
    # `[` on its own line reads as indexing thin air.
    pieces: list[str] = []
    for frag in fragments:
        if pieces and frag.startswith("["):
            pieces[-1] += frag
        else:
            pieces.append(frag)
    # Don't leave a bare `df_1` line; open with `df_1.first_call(...)`.
    if len(pieces) > 1 and pieces[0] == group[0].root:
        pieces[0:2] = [pieces[0] + pieces[1]]
    return [f"{target} = (", *(f"    {p}" for p in pieces), ")"]


def fuse_method_chains(lines: list[str]) -> list[str]:
    """Merge consecutive ``df = df.method(...)`` statements into one fluent chain.

    Both drivers emit one statement per node; on linear chains variable reuse
    already collapses names (``df_1 = df_1.dropna()`` line after line). This
    pass rewrites each such run the way a person would: short runs on one line
    (``df_1 = df_1.dropna().head(5)``), longer ones in parenthesized fluent
    style with one call per line.

    Safety comes from :func:`_chain_step`'s AST validation plus two rules:

    - a run only *continues* while each statement assigns the same variable it
      roots its RHS in and references it exactly once (see ``_ChainStep``);
    - any non-fusible entry (``del``, writes, comments, multi-line snippets)
      breaks the run, so liveness / ``free_intermediates`` behavior is
      untouched — fusion never reorders or crosses statements.

    The first statement of a run may root in a *different* dataframe
    (``df_2 = df_1.agg(...)`` on a fan-out) and may reference it any number of
    times: at that point every reference still sees the same pre-chain frame.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        step = _chain_step(lines[i])
        if step is None:
            out.append(lines[i])
            i += 1
            continue
        group = [step]
        j = i + 1
        while j < len(lines):
            nxt = _chain_step(lines[j])
            if (
                nxt is None
                or nxt.target != step.target
                or nxt.root != nxt.target
                or nxt.target_refs != 1
                or _step_suffix(nxt) is None
            ):
                break
            group.append(nxt)
            j += 1
        if len(group) >= 2:
            out.extend(_render_chain(group))
        else:
            out.append(lines[i])
        i = j  # j == i + 1 when the group stayed a singleton
    return out


_FRAME_STEM = re.compile(r"[^0-9a-zA-Z]+")


def frame_var_name(filename: Any, taken: set[str]) -> str | None:
    """A readable ``df_<stem>`` variable for an input read, or None to fall back
    to the numbered ``df_N`` sequence.

    ``filename`` is the dataset's file name (or a SQL table name): its stem is
    lowercased and squeezed to identifier characters, so ``Sales 2024.csv``
    reads back as ``df_sales_2024``. Rejected stems fall back to ``df_N``:
    empty, overlong (nobody wants a 40-character variable), and all-digit ones
    (``df_2024`` would collide with the numbered namespace). Non-string hints
    (a parameterized config holds a ``CodeRef``) fall back too. ``taken`` holds
    every name already claimed — earlier inputs, flow parameters — and the
    chosen name is added to it; duplicates get a ``_2``/``_3`` suffix.
    """
    if not filename or not isinstance(filename, str):
        return None
    stem = re.split(r"[\\/]", filename)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    stem = _FRAME_STEM.sub("_", stem.lower()).strip("_")
    # A dataset already named df_something must not read back as df_df_something.
    stem = stem.removeprefix("df_")
    if not stem or stem.isdigit() or len(stem) > 30:
        return None
    var = f"df_{stem}"
    if var in taken:
        n = 2
        while f"{var}_{n}" in taken:
            n += 1
        var = f"{var}_{n}"
    taken.add(var)
    return var


# A parenthesized fluent chain opens with `target = (` and closes with a bare
# `)` — both produced only by _render_chain, never by node emitters.
_CHAIN_OPEN = re.compile(r"\w+ = \($")


def insert_paragraph_breaks(lines: list[str]) -> list[str]:
    """Blank line before and after each parenthesized fluent chain.

    Without this the script is a solid wall of statements; with it, it reads in
    paragraphs the way a person lays out a pipeline — the input reads, one block
    per multi-step chain, then the writes.
    """
    out: list[str] = []
    for line in lines:
        if _CHAIN_OPEN.match(line) and out and out[-1] != "":
            out.append("")
        out.append(line)
        if line == ")":
            out.append("")
    while out and out[-1] == "":
        out.pop()
    return out


def parameter_names(parameter_lines: list[str] | None) -> set[str]:
    """The variable names a flow-parameter prelude assigns (comments skipped)."""
    if not parameter_lines:
        return set()
    return {ln.split(" = ", 1)[0] for ln in parameter_lines if " = " in ln and not ln.startswith("#")}


def assert_params_do_not_shadow_imports(header: list[str], parameter_lines: list[str]) -> None:
    """Fail export clearly when a flow parameter would rebind a script import.

    The parameter prelude (``name = default``) sits *after* the imports, so a
    parameter named ``Pipeline`` or ``create_engine`` silently rebinds the
    import and the exported script breaks in a confusing place. Which imports a
    script needs depends on the flow's nodes and dialect, so this can't be a
    static reserved-name list at save time — instead the generators check the
    final header and name the offending parameter(s).
    """
    if not parameter_lines:
        return
    imported: set[str] = set()
    for node in ast.walk(ast.parse("\n".join(header))):
        if isinstance(node, ast.Import):
            imported.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.update(a.asname or a.name for a in node.names)
    clash = sorted(imported & parameter_names(parameter_lines))
    if clash:
        raise GraphValidationError(
            f"Flow parameter name(s) {', '.join(clash)} collide with import(s) the exported "
            "script needs — rename the parameter(s)."
        )


def pandas_dialect_kwargs(source_type: str, options: dict[str, Any] | None) -> str:
    """Extra ``pd.read_*`` keywords reproducing an upload's ORIGINAL dialect.

    Exported scripts read the user's own file by name — which still has the
    dialect the upload had (the copy Ciaren stores is normalized, the user's
    file is not). Only non-default values are emitted, so standard files keep
    the clean bare read."""
    if not options:
        return ""
    parts: list[str] = []
    if source_type == "csv" and options.get("delimiter", ",") != ",":
        parts.append(f"sep={options['delimiter']!r}")
    if source_type in ("csv", "tsv"):
        if options.get("encoding", "utf-8") != "utf-8":
            parts.append(f"encoding={options['encoding']!r}")
        if options.get("decimal", ".") == ",":
            parts.append("decimal=','")
    if source_type == "excel" and options.get("sheet") not in (None, 0):
        parts.append(f"sheet_name={options['sheet']!r}")
    return "".join(f", {p}" for p in parts)


def polars_dialect_kwargs(source_type: str, options: dict[str, Any] | None) -> str:
    """The polars equivalent of :func:`pandas_dialect_kwargs` for UTF-8 files
    (non-UTF-8 needs a decode wrapper — the drivers handle that separately).
    Excel sheet indexes are 0-based here; polars' ``sheet_id`` is 1-based."""
    if not options:
        return ""
    parts: list[str] = []
    if source_type == "csv" and options.get("delimiter", ",") != ",":
        parts.append(f"separator={options['delimiter']!r}")
    if source_type in ("csv", "tsv") and options.get("decimal", ".") == ",":
        parts.append("decimal_comma=True")
    if source_type == "excel" and options.get("sheet") not in (None, 0):
        sheet = options["sheet"]
        parts.append(f"sheet_id={sheet + 1!r}" if isinstance(sheet, int) else f"sheet_name={sheet!r}")
    return "".join(f", {p}" for p in parts)


def dialect_needs_decode(source_type: str, options: dict[str, Any] | None) -> bool:
    """Whether the original file's encoding forces the polars script to decode
    via Python first (polars itself only reads UTF-8)."""
    if not options or source_type not in ("csv", "tsv"):
        return False
    return bool(options.get("encoding", "utf-8") != "utf-8")


def incoming_by_target(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Index a graph's edges by target node id (every node gets an entry)."""
    incoming: dict[str, list[dict[str, Any]]] = {n["id"]: [] for n in graph["nodes"]}
    for edge in graph.get("edges", []):
        incoming[edge["target"]].append(edge)
    return incoming


def edge_source_var(node_outputs: dict[str, dict[str, str]], edge: dict[str, Any]) -> str:
    """The variable an edge carries, honoring ``sourceHandle`` for multi-output nodes."""
    outs = node_outputs[edge["source"]]
    handle = edge.get("sourceHandle")
    if handle and handle in outs:
        return outs[handle]
    if "out" in outs:
        return outs["out"]
    return next(iter(outs.values()))


def collect_input_vars(
    edges_in: list[dict[str, Any]],
    node_outputs: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Map a node's input handles to source variables. A repeated handle (variadic
    concat) is disambiguated with the edge's position (``in``, ``in_1``, …)."""
    input_vars: dict[str, str] = {}
    for i, e in enumerate(edges_in):
        handle = e.get("targetHandle") or "in"
        if handle in input_vars:
            handle = f"{handle}_{i}"
        input_vars[handle] = edge_source_var(node_outputs, e)
    return input_vars


_PLACEHOLDER_EXT = {
    "csv": ".csv",
    "tsv": ".tsv",
    "excel": ".xlsx",
    "parquet": ".parquet",
    "json": ".json",
    "jsonl": ".jsonl",
    "text": ".txt",
}


def placeholder_input_path(source_type: str) -> str:
    """Fallback filename for an input node whose dataset id isn't in the caller's
    ``dataset_paths`` map, matching the node's format — pd.read_excel('input.xlsx'),
    not pd.read_excel('input.csv')."""
    return f"input{_PLACEHOLDER_EXT.get(source_type, '.csv')}"


def ordered_imports(imports: list[str]) -> list[str]:
    """``import x`` lines first, then ``from x import y`` lines, each sorted."""
    plain = sorted(i for i in imports if i.startswith("import "))
    froms = sorted(i for i in imports if not i.startswith("import "))
    return plain + froms


def sql_engine_var(
    connection_id: str,
    connections: dict[str, dict[str, Any]],
    engine_vars: dict[str, str],
    lines: list[str],
) -> str:
    """The sqlalchemy engine variable for a connection, emitting its
    ``create_engine`` line into ``lines`` on first use."""
    if connection_id not in engine_vars:
        n = len(engine_vars) + 1
        var = f"_engine_{n}"
        info = connections.get(connection_id, {"provider": "sqlite", "database": ""})
        # A file: secret reference needs a prelude line fetching the secret into
        # a named variable (see engine_url_parts); env/keyring inline in the URL.
        prelude, url_expr = engine_url_parts(info, secret_var=f"_secret_{n}")
        lines.extend(prelude)
        lines.append(f"{var} = create_engine({url_expr})")
        engine_vars[connection_id] = var
    return engine_vars[connection_id]


def last_consumer_index(order: list[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    """Map each source node id to the position (in ``order``) of its *last* consumer.

    A node that fans out to several downstream nodes — or whose result a later
    join needs — must stay alive until the highest-positioned consumer has run,
    so we take the maximum. Nodes with no consumers (e.g. output sinks) are
    absent from the result. ``order`` is the topological execution order, so a
    consumer's index is always greater than its producer's.
    """
    position = {node_id: i for i, node_id in enumerate(order)}
    last: dict[str, int] = {}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source not in position or target not in position:
            continue
        idx = position[target]
        if idx > last.get(source, -1):
            last[source] = idx
    return last


def reusable_output_var(
    idx: int,
    incoming_edges: list[dict[str, Any]],
    node_outputs: dict[str, dict[str, str]],
    n_output_handles: int,
    last_use: dict[str, int],
) -> str | None:
    """The input variable the node at position ``idx`` may overwrite, or ``None``.

    Every node's generated code fully evaluates its input before (re)assigning
    its output variable, so a single-output node that is the *last* consumer of
    its single input can write its result back into the input's variable
    (``df_1 = df_1.head(5)``) instead of minting a fresh one — the exported
    script then reads like hand-written code. Reuse is safe iff:

    - the node has exactly one incoming edge and exactly one output handle;
    - the source node produced exactly one variable (liveness is tracked per
      node, not per handle, so reusing one handle's variable could clobber a
      sibling handle another consumer still needs);
    - this node is the source's last consumer in emission order, so no later
      node reads the variable.
    """
    if n_output_handles != 1 or len(incoming_edges) != 1:
        return None
    source = incoming_edges[0]["source"]
    outs = node_outputs.get(source)
    if outs is None or len(outs) != 1:
        return None
    if last_use.get(source) != idx:
        return None
    return next(iter(outs.values()))


class DelScheduler:
    """Emits ``del`` statements once a variable's last consumer has run.

    The risk with freeing intermediates is deleting a frame a later node still
    needs; scheduling strictly at ``last_use`` positions (and never at the final
    node, whose result is the script's point) makes that impossible. Disabled
    instances are inert, so drivers can call unconditionally.
    """

    def __init__(self, order: list[str], last_use: dict[str, int], enabled: bool) -> None:
        self._last_use = last_use
        self._final_idx = len(order) - 1
        self._enabled = enabled
        self._pending: dict[int, list[str]] = {}

    def schedule(self, node_id: str, outs: dict[str, str]) -> None:
        """Queue a just-emitted node's output for deletion after its last consumer.
        Multi-output liveness is per node, not per handle, so only single-output
        nodes are freed."""
        if not self._enabled or len(outs) != 1:
            return
        li = self._last_use.get(node_id)
        if li is not None and li < self._final_idx:
            self._pending.setdefault(li, []).append(next(iter(outs.values())))

    def cancel(self, idx: int, var: str) -> None:
        """A consumer at position ``idx`` took ``var`` over as its own output
        (variable reuse) — it must not be deleted there."""
        if var in self._pending.get(idx, []):
            self._pending[idx].remove(var)

    def flush(self, idx: int) -> list[str]:
        """The ``del`` lines to append after emitting the node at position ``idx``.
        Popped at *every* position — a variable's last consumer may be an output
        sink, which produces no variable of its own."""
        return [f"del {var}" for var in self._pending.pop(idx, [])]
