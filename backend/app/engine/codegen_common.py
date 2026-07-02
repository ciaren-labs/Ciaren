# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers for the pandas / polars code generators.

The non-trivial bit is liveness analysis: every node's dataframe variable is
dead once its **last** consumer has run. Both generators use it two ways —
to reuse a dead variable as the consumer's output (``df_1 = df_1.head(5)``
instead of minting ``df_2``), and, under the optional ``del``
("free intermediates") mode, to release variables that could not be reused.
"""

from typing import Any


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
