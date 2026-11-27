# SPDX-License-Identifier: AGPL-3.0-only
"""Transactional receipts. Store structural facts and a narrow inverse, never graph snapshots."""

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import AssistantActivity, Flow
from app.services.assistant_graph import Graph, inspect
from app.services.assistant_inputs import InputVersion
from app.services.flow_revision import next_revision, update_one

FIELDS = {"on", "how", "columns", "column", "subset", "n", "offset", "ascending", "keep", "operator", "value"}
ENUMS = {
    "how": {"inner", "left", "any", "all"},
    "keep": {"first", "last"},
    "operator": {"==", "!=", ">", ">=", "<", "<=", "isnull", "notnull"},
}
CONFLICT = "A node, connection or parameter used by this change has since changed. The saved flow was left intact."
STALE = "The saved flow or an input changed. Reload the flow and preview the reversal again."


def digest(salt: str, data: object) -> str:
    return hashlib.sha256((salt + json.dumps(data, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()


def encoded(salt: str, cfg: Graph, key: str) -> Graph:
    if key not in cfg:
        return {"unset": True}
    value = cfg[key]
    if (
        type(value) is int
        and key in {"n", "offset"}
        and 0 <= value <= 1000000
        or type(value) is bool
        and key == "ascending"
        or isinstance(value, str)
        and value in ENUMS.get(key, set())
    ):
        return {"literal": value}
    if key in {"column", "columns", "on", "subset"}:
        cols = value if isinstance(value, list) else [value]
        if len(cols) <= 64 and all(isinstance(c, str) for c in cols):
            return {"columns": [digest(salt, c) for c in cols], "single": not isinstance(value, list)}
    return {"private": True}


def guard(
    graph: Graph, salt: str, roots: list[str], added: list[str], upstream_only: bool, updates: list[Graph]
) -> str:
    """Protect the touched connected component. Ignore presentation edits on retained nodes."""
    nodes, edges = inspect(graph)
    component = {n["id"] for n in nodes if digest(salt, n["id"]) in roots}
    for _ in nodes:
        prior = len(component)
        for e in edges:
            if e["target"] in component or (not upstream_only and e["source"] in component):
                component.update((e["source"], e["target"]))
        if len(component) == prior:
            break
    state = []
    for node in nodes:
        if node["id"] not in component:
            continue
        ref = digest(salt, node["id"])
        config = node["data"]["config"]
        # Offset and count are independent numeric controls. A reversal writes only
        # its changed fields; preserve later adjustments to the other control.
        fields = {u["field"] for u in updates if u["node"] == ref}
        if upstream_only and node["type"] == "limitRows" and fields:
            config = {k: v for k, v in config.items() if k in fields or k not in {"n", "offset"}}
        state.append((node["id"], node if ref in added else [node["type"], config]))
    wiring = [(e["id"], e) for e in edges if e["target"] in component]
    # A later unrelated flow parameter is independent of this edit.
    references = set(re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", json.dumps(state)))
    params = [p for p in graph.get("parameters") or [] if isinstance(p, dict) and p.get("name") in references]
    return digest(salt, [sorted(state), sorted(wiring), graph.get("engine"), params])


def editor_edge_id(edge: Graph) -> str:
    return f"e_{edge['source']}_{edge.get('sourceHandle') or 'out'}_{edge['target']}_{edge.get('targetHandle') or 'in'}"


def receipt(
    flow_id: str,
    project: str,
    before: Graph,
    after: Graph,
    delta: Graph,
    inputs: list[InputVersion],
    source: str,
    known_columns: set[str] | None = None,
) -> AssistantActivity:
    event = uuid4().hex
    old_nodes = {n["id"]: n for n in before.get("nodes", [])}
    kinds = {n["id"]: n["type"] for n in after["nodes"]}
    old_edges = {e["id"]: e for e in before.get("edges", [])}
    details: list[Graph] = []
    added = [digest(event, n["id"]) for n in delta["added"]]
    roots = list(added)
    updates = []
    restore = []
    reversible = True
    for n in delta["added"]:
        details.append({"action": "add_node", "kind": n["type"]})
    for n in delta["changed"]:
        ref = digest(event, n["id"])
        previous = old_nodes[n["id"]]["data"]["config"]
        current = n["data"]["config"]
        for field in sorted(previous.keys() | current.keys()):
            if (
                field in previous
                and field in current
                and previous[field] == current[field]
                and type(previous[field]) is type(current[field])
            ):
                continue
            if field not in FIELDS:
                reversible = False
                details.append({"action": "edit_field", "kind": n["type"], "field": "other settings"})
                continue
            old, new = encoded(event, previous, field), encoded(event, current, field)
            details.append(
                {
                    "action": "edit_field",
                    "kind": n["type"],
                    "field": field,
                    **({"before": old["literal"]} if "literal" in old else {}),
                    **({"after": new["literal"]} if "literal" in new else {}),
                }
            )
            if known_columns is not None and "columns" in old:
                original = previous[field]
                names = original if isinstance(original, list) else [original]
                reversible &= all(name in known_columns for name in names)
            reversible &= "private" not in old
            updates.append({"node": ref, "field": field, "old": old})
        roots.append(ref)
    for action, connections in (
        ("connect", delta["connected"]),
        ("disconnect", [old_edges[k] for k in delta["disconnected"]]),
    ):
        for e in connections:
            port = e.get("targetHandle")
            details.append(
                {
                    "action": action,
                    "from": kinds[e["source"]],
                    "to": kinds[e["target"]],
                    **({"port": port} if port in ("left", "right", "in") else {}),
                }
            )
            if action == "disconnect":
                # Only reproduce ordinary edges with generated IDs and known ports.
                if (
                    e["id"] != editor_edge_id(e)
                    and not re.fullmatch(r"(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})", e["id"])
                    or set(e) - {"id", "source", "target", "sourceHandle", "targetHandle"}
                    or e.get("sourceHandle") not in (None, "out")
                    or port not in (None, "in", "left", "right")
                ):
                    reversible = False
                else:
                    restore.append(
                        {
                            **e,
                            "id": None if e["id"] == editor_edge_id(e) else e["id"],
                            "source": digest(event, e["source"]),
                            "target": digest(event, e["target"]),
                            "index": before["edges"].index(e),
                        }
                    )
    upstream_only = (
        bool(updates)
        and not added
        and not delta["connected"]
        and all(
            n["type"] in {"join", "limitRows", "sortRows", "dropNulls", "removeDuplicates", "filterRows"}
            for n in delta["changed"]
        )
    )
    return AssistantActivity(
        id=event,
        flow_id=flow_id,
        project_id=project,
        source=source,
        details=details,
        inverse={
            "usable": reversible,
            "added": added,
            "updates": updates,
            "roots": roots,
            "restore": restore,
            "connections": [digest(event, e["id"]) for e in delta["connected"]],
            "upstream_only": upstream_only,
            "guard": guard(after, event, roots, added, upstream_only, updates),
            "inputs": [asdict(v) for v in inputs],
        },
    )


def reversed_details(details: list[Graph]) -> list[Graph]:
    opposite = {"add_node": "remove_node", "connect": "disconnect", "disconnect": "connect"}
    result = []
    for item in details:
        if item["action"] == "edit_field":
            result.append(
                {
                    **{k: v for k, v in item.items() if k not in {"before", "after"}},
                    **({"before": item["after"]} if "after" in item else {}),
                    **({"after": item["before"]} if "before" in item else {}),
                }
            )
        else:
            result.append({**item, "action": opposite[item["action"]]})
    return result


async def inverse_graph(db: AsyncSession, event: AssistantActivity, graph: Graph) -> Graph:
    inv = event.inverse
    if not inv.get("usable"):
        raise ConflictError(
            "This entry cannot be reversed automatically because the previous configuration cannot be restored safely."
        )
    if inv["guard"] != guard(graph, event.id, inv["roots"], inv["added"], inv["upstream_only"], inv["updates"]):
        raise ConflictError(CONFLICT)
    result = deepcopy(graph)
    nodes = {digest(event.id, n["id"]): n for n in result["nodes"]}
    known: dict[str, str] = {}
    for binding in inv["inputs"]:
        version = InputVersion(**binding)
        if not await db.scalar(select(version.available(event.project_id))):
            raise ConflictError(STALE)
        if any("columns" in u["old"] for u in inv["updates"]):
            schema = await db.scalar(select(DatasetVersion.schema_json).where(DatasetVersion.id == version.version_id))
            known.update({digest(event.id, c["name"]): c["name"] for c in schema or []})
    for u in inv["updates"]:
        cfg = nodes[u["node"]]["data"]["config"]
        key, value = u["field"], u["old"]
        if value.get("unset"):
            cfg.pop(key, None)
        elif "literal" in value:
            cfg[key] = value["literal"]
        else:
            if any(c not in known for c in value["columns"]):
                raise ConflictError("The original column cannot be recovered from the pinned input schema.")
            cols = [known[c] for c in value["columns"]]
            cfg[key] = cols[0] if value["single"] else cols
    result["nodes"] = [n for ref, n in nodes.items() if ref not in inv["added"]]
    result["edges"] = [e for e in result["edges"] if digest(event.id, e["id"]) not in inv["connections"]]
    for item in sorted(inv["restore"], key=lambda e: e["index"]):
        edge = {k: v for k, v in item.items() if k != "index"}
        edge.update(source=nodes[item["source"]]["id"], target=nodes[item["target"]]["id"])
        if edge["id"] is None:
            edge["id"] = editor_edge_id(edge)
        if any(e["id"] == edge["id"] for e in result["edges"]):
            raise ConflictError(CONFLICT)
        result["edges"].insert(item["index"], edge)
    inspect(result)
    return result


async def timeline(db: AsyncSession, flow_id: str, cursor: str | None) -> Graph:
    flow = await db.get(Flow, flow_id)
    if not flow:
        raise NotFoundError("Flow", flow_id)
    scope = (AssistantActivity.flow_id == flow_id, AssistantActivity.project_id == flow.project_id)
    stmt = select(AssistantActivity).where(*scope)
    if cursor:
        anchor = await db.scalar(stmt.where(AssistantActivity.id == cursor))
        if not anchor:
            raise NotFoundError("Activity", cursor)
        stmt = stmt.where(
            or_(
                AssistantActivity.created_at < anchor.created_at,
                (AssistantActivity.created_at == anchor.created_at) & (AssistantActivity.id < anchor.id),
            )
        )
    rows = list(
        await db.scalars(stmt.order_by(AssistantActivity.created_at.desc(), AssistantActivity.id.desc()).limit(21))
    )
    items = rows[:20]
    reversed_ids = set(
        await db.scalars(
            select(AssistantActivity.reverses).where(*scope, AssistantActivity.reverses.in_([e.id for e in items]))
        )
    )
    return {
        "entries": [
            {
                "id": e.id,
                "date": e.created_at.replace(tzinfo=UTC),
                "source": e.source,
                "reverses": e.reverses,
                "state": "reverted" if e.id in reversed_ids else "available" if e.inverse.get("usable") else "recorded",
                "details": e.details,
            }
            for e in items
        ],
        "next": items[-1].id if len(rows) > 20 else None,
    }


async def load_target(
    db: AsyncSession, flow_id: str, event_id: str, revision: datetime
) -> tuple[Flow, AssistantActivity]:
    flow = await db.get(Flow, flow_id)
    event = await db.scalar(
        select(AssistantActivity)
        .join(Flow, Flow.id == AssistantActivity.flow_id)
        .where(Flow.id == flow_id, AssistantActivity.project_id == Flow.project_id, AssistantActivity.id == event_id)
    )
    if not flow or not event:
        raise NotFoundError("Activity", event_id)
    if flow.updated_at != revision or flow.is_disabled:
        raise ConflictError(STALE)
    if event.reverses or await db.scalar(select(AssistantActivity.id).where(AssistantActivity.reverses == event.id)):
        raise ConflictError("This saved change has already been reversed or is itself a reversal.")
    return flow, event


async def save_reversal(db: AsyncSession, flow_id: str, event_id: str, revision: datetime) -> Graph:
    flow, event = await load_target(db, flow_id, event_id, revision)
    graph = await inverse_graph(db, event, flow.graph_json)
    now = next_revision(revision)
    saved = await update_one(
        db,
        update(Flow)
        .where(
            Flow.id == flow_id,
            Flow.updated_at == revision,
            Flow.project_id == event.project_id,
            Flow.is_disabled.is_(False),
            *(InputVersion(**v).available(event.project_id) for v in event.inverse["inputs"]),
        )
        .values(graph_json=graph, updated_at=now),
    )
    if not saved:
        await db.rollback()
        raise ConflictError(STALE)
    entry = AssistantActivity(
        id=uuid4().hex,
        flow_id=flow_id,
        project_id=event.project_id,
        created_at=now,
        source="revert",
        reverses=event.id,
        details=reversed_details(event.details),
        inverse={},
    )
    db.add(entry)
    await db.commit()
    return {"revision": now, "activity": entry.id}
