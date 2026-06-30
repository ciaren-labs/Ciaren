# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers for the pandas / polars code generators.

The only non-trivial bit is liveness analysis for the optional ``del``
("free intermediates") output: every node's dataframe variable can be released
once its **last** consumer has run, which lowers peak memory for materializing
engines without changing results.
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
