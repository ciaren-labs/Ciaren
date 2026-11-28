# SPDX-License-Identifier: AGPL-3.0-only
"""The edit language shared by every planner, and the materializer that applies it.

Ops address nodes by turn-local refs. ``materialize`` applies a whole batch to a copy
of the working graph or rejects it: a failed op leaves the working graph unchanged.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.plugins import get_registry
from app.services.assistant_activity import editor_edge_id

Graph = dict[str, Any]
Ref = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")]
Port = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]
MAX_OPS = 24


class Op(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AddNode(Op):
    op: Literal["add_node"] = "add_node"
    ref: Ref = Field(alias="as")
    type: Annotated[str, Field(max_length=64)]
    config: dict[str, Any] = {}


class UpdateConfig(Op):
    op: Literal["update_config"] = "update_config"
    node: Ref
    set: dict[str, Any] = {}
    unset: list[Annotated[str, Field(max_length=64)]] = []


class Connect(Op):
    op: Literal["connect"] = "connect"
    source: Ref = Field(alias="from")
    source_port: Port = Field("out", alias="from_port")
    target: Ref = Field(alias="to")
    target_port: Port = Field("in", alias="to_port")


class Disconnect(Op):
    op: Literal["disconnect"] = "disconnect"
    source: Ref = Field(alias="from")
    target: Ref = Field(alias="to")
    target_port: Port | None = Field(None, alias="to_port")


class RemoveNode(Op):
    op: Literal["remove_node"] = "remove_node"
    node: Ref


AnyOp = Annotated[AddNode | UpdateConfig | Connect | Disconnect | RemoveNode, Field(discriminator="op")]


@dataclass
class Issue:
    code: str
    message: str
    node: str | None = None
    field: str | None = None

    def public(self) -> dict[str, Any]:
        return {k: v for k, v in vars(self).items() if v is not None}


class EditRejected(ValueError):
    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


@dataclass
class Working:
    """The stored base, the edited copy and the ref table for one turn."""

    base: Graph
    graph: Graph
    refs: dict[str, str] = field(default_factory=dict)
    #: Node ids created during this turn; only these may be removed.
    created: set[str] = field(default_factory=set)
    #: Node ids whose type the assistant may not touch.
    locked: set[str] = field(default_factory=set)

    @classmethod
    def start(cls, base: Graph, locked: set[str] | None = None) -> "Working":
        refs = {f"n{i}": n["id"] for i, n in enumerate(base.get("nodes", []))}
        graph = deepcopy({**base, "nodes": base.get("nodes", []), "edges": base.get("edges", [])})
        return cls(base, graph, refs, set(), locked or set())

    def ref_of(self, node_id: str) -> str:
        return next(r for r, i in self.refs.items() if i == node_id)


def labels() -> dict[str, str]:
    return {s.id: s.label for s in get_registry().node_specs()}


def materialize(work: Working, ops: list[AnyOp]) -> tuple[Working, set[str]]:
    """Apply ops to a copy. Returns the new state and the ids of nodes added or reconfigured."""
    graph = deepcopy(work.graph)
    refs, created = dict(work.refs), set(work.created)
    nodes = {n["id"]: n for n in graph["nodes"]}
    touched: set[str] = set()
    names = labels()
    issues: list[Issue] = []

    def node_id(ref: str, op: str) -> str | None:
        if ref not in refs or refs[ref] not in nodes:
            issues.append(Issue("bad_ref", f"{op}: unknown node.", ref))
            return None
        if refs[ref] in work.locked:
            issues.append(Issue("locked_node", f"{op}: this node cannot be edited by the assistant.", ref))
            return None
        return refs[ref]

    for item in ops:
        if isinstance(item, AddNode):
            if item.ref in refs:
                issues.append(Issue("bad_ref", "add_node: the ref is already in use.", item.ref))
                continue
            if item.type not in names:
                issues.append(Issue("policy", "add_node: unavailable node type.", item.ref))
                continue
            new_id = uuid4().hex
            new: Graph = {
                "id": new_id,
                "type": item.type,
                "position": {"x": 0, "y": 0},
                "data": {"label": names[item.type], "config": deepcopy(item.config)},
            }
            graph["nodes"].append(new)
            nodes[new_id] = new
            refs[item.ref] = new_id
            created.add(new_id)
            touched.add(new_id)
        elif isinstance(item, UpdateConfig):
            target = node_id(item.node, "update_config")
            if target:
                cfg = nodes[target]["data"]["config"]
                for key in item.unset:
                    cfg.pop(key, None)
                cfg.update(deepcopy(item.set))
                touched.add(target)
        elif isinstance(item, Connect):
            source, target = node_id(item.source, "connect"), node_id(item.target, "connect")
            if source and target:
                edge = {
                    "source": source,
                    "target": target,
                    "sourceHandle": item.source_port,
                    "targetHandle": item.target_port,
                }
                edge = {"id": editor_edge_id(edge), **edge}
                if any(e["id"] == edge["id"] for e in graph["edges"]):
                    issues.append(Issue("bad_port", "connect: this connection already exists.", item.target))
                else:
                    graph["edges"].append(edge)
        elif isinstance(item, Disconnect):
            source, target = node_id(item.source, "disconnect"), node_id(item.target, "disconnect")
            if source and target:
                kept = [
                    e
                    for e in graph["edges"]
                    if not (
                        e["source"] == source
                        and e["target"] == target
                        and item.target_port in (None, e.get("targetHandle") or "in")
                    )
                ]
                if len(kept) == len(graph["edges"]):
                    issues.append(Issue("bad_port", "disconnect: no such connection.", item.target))
                graph["edges"] = kept
        else:
            target = node_id(item.node, "remove_node")
            if target and target not in created:
                issues.append(Issue("policy", "remove_node: only nodes added in this turn can be removed.", item.node))
            elif target:
                graph["nodes"] = [n for n in graph["nodes"] if n["id"] != target]
                graph["edges"] = [e for e in graph["edges"] if target not in (e["source"], e["target"])]
                del nodes[target]
                created.discard(target)
                touched.discard(target)
    if issues:
        raise EditRejected(issues)
    return Working(work.base, graph, refs, created, work.locked), touched


def layout(work: Working) -> None:
    """Place nodes created this turn in layers: depth × 230 across, branch × 150 down."""
    nodes = work.graph["nodes"]
    parents: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in work.graph["edges"]:
        parents[e["target"]].append(e["source"])
    depth: dict[str, int] = {}

    def level(node: str, seen: frozenset[str] = frozenset()) -> int:
        if node not in depth:
            depth[node] = 1 + max((level(p, seen | {node}) for p in parents[node] if p not in seen), default=-1)
        return depth[node]

    rows: dict[int, int] = {}
    for n in nodes:
        d = level(n["id"])
        branch = rows.get(d, 0)
        rows[d] = branch + 1
        if n["id"] in work.created:
            n["position"] = {"x": 80 + d * 230, "y": 120 + branch * 150}


def diff(work: Working) -> Graph:
    """Delta from the stored base to the working graph."""
    before = {n["id"]: n for n in work.base.get("nodes", [])}
    after = {n["id"]: n for n in work.graph["nodes"]}
    old_edges = [e["id"] for e in work.base.get("edges", [])]
    new_edges = {e["id"] for e in work.graph["edges"]}
    delta: Graph = {
        "added": [n for i, n in after.items() if i not in before],
        "changed": [
            n
            for i, n in after.items()
            if i in before
            and [n["data"].get("config"), n["data"].get("label")]
            != [before[i]["data"].get("config"), before[i]["data"].get("label")]
        ],
        "connected": [e for e in work.graph["edges"] if e["id"] not in old_edges],
        "disconnected": [i for i in old_edges if i not in new_edges],
    }
    removed = [i for i in before if i not in after]
    if removed:
        delta["removed"] = removed
    return delta
