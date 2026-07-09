# SPDX-License-Identifier: AGPL-3.0-only
"""Load demo flow graphs from versioned JSON resource documents.

The demo flow *content* lives as reviewable JSON documents under
``resources/etl`` and ``resources/ml`` — one file per flow, numeric-prefixed so
the order the demo project presents them is fixed and explicit. This module
validates each document (``DemoFlowDocument``) and *hydrates* it into a
React-Flow graph the seeder can persist.

Two things are deliberately kept out of the JSON and injected here, because they
are not stable content:

* **dataset ids** — input nodes reference their dataset by CSV *file name* (a
  stable key). The concrete ``dataset_id`` only exists at seed time, so it is
  resolved here from the ``dataset_ids`` map.
* **node labels** — the human ``label`` is injected from the backend node
  catalog (:mod:`app.engine.node_metadata`) rather than baked into the JSON, so a
  catalog label change can never leave a demo node showing a raw camelCase type.

Keeping the graphs as data (not Python builders) means a visual tweak to a demo
flow is a small, reviewable JSON diff, and the documents can be validated as
artifacts in tests without running the seeder.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_metadata import NODE_META_BY_TYPE

# (name, description, graph) tuples are what the seeder persists.
DemoFlow = tuple[str, str, dict[str, Any]]

_RESOURCES = Path(__file__).parent / "resources"


class DemoResourceError(Exception):
    """A demo flow JSON document is missing, malformed, or references unknown data."""


class DemoPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int


class DemoNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    position: DemoPosition
    # Non-input nodes carry their editor config verbatim.
    config: dict[str, Any] = {}
    # Input nodes reference their dataset by CSV file name; the loader resolves
    # it to a concrete ``dataset_id`` at hydrate time. Mutually exclusive with
    # ``config`` (an input node's config is built from the dataset reference).
    dataset: str | None = None

    @model_validator(mode="after")
    def _check_input_shape(self) -> DemoNode:
        is_input = self.type in _INPUT_TYPES
        if self.dataset is not None:
            if not self.dataset.strip():
                raise ValueError(f"input node {self.id!r} has an empty `dataset` reference")
            if not is_input:
                raise ValueError(f"node {self.id!r} ({self.type}) sets `dataset` but is not an input node")
            if self.config:
                raise ValueError(f"input node {self.id!r} must use `dataset`, not `config`")
        elif is_input:
            raise ValueError(f"input node {self.id!r} must reference a dataset via `dataset`")
        return self


class DemoEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None


class DemoFlowDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    engine: Literal["pandas", "polars"] | None = None
    nodes: list[DemoNode]
    edges: list[DemoEdge]

    @model_validator(mode="after")
    def _check_wiring(self) -> DemoFlowDocument:
        if not self.nodes:
            raise ValueError("flow document has no nodes")
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("flow document has duplicate node ids")
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(f"edge source {edge.source!r} is not a node in this document")
            if edge.target not in node_ids:
                raise ValueError(f"edge target {edge.target!r} is not a node in this document")
        return self

    def referenced_datasets(self) -> set[str]:
        """CSV file names this flow's input nodes read from."""
        return {node.dataset for node in self.nodes if node.dataset is not None}


def _label_for(node_type: str) -> str:
    """Human-readable label for a node type, matching the editor's own
    node-creation default (``createFlowNode`` / ``nodeCatalog.ts``), sourced from
    the backend node catalog so a demo node never shows the raw camelCase type."""
    meta = NODE_META_BY_TYPE.get(node_type)
    return meta.label if meta is not None else node_type


def _edge_id(source: str, target: str, source_handle: str | None, target_handle: str | None) -> str:
    suffix = "".join(f"-{h}" for h in (source_handle, target_handle) if h)
    return f"e-{source}-{target}{suffix}"


def hydrate_document(doc: DemoFlowDocument, dataset_ids: dict[str, str]) -> DemoFlow:
    """Turn a validated demo document into a persistable React-Flow graph.

    ``dataset_ids`` maps CSV file name -> dataset id for every dataset the demo
    input nodes reference; a missing key raises :class:`DemoResourceError`.
    """
    nodes: list[dict[str, Any]] = []
    for node in doc.nodes:
        if node.dataset is not None:
            try:
                dataset_id = dataset_ids[node.dataset]
            except KeyError as exc:
                raise DemoResourceError(
                    f"demo flow {doc.name!r}: node {node.id!r} references unknown dataset {node.dataset!r}"
                ) from exc
            config: dict[str, Any] = {"dataset_id": dataset_id, "dataset_version": 1, "format": "csv"}
        else:
            # Deep-copy so each hydrated graph owns its config: the documents are
            # cached (shared instances), and a caller mutating a graph in place
            # must not poison the cache for later builds.
            config = copy.deepcopy(node.config)
        nodes.append(
            {
                "id": node.id,
                "type": node.type,
                "position": {"x": node.position.x, "y": node.position.y},
                "data": {"label": _label_for(node.type), "config": config},
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in doc.edges:
        hydrated: dict[str, Any] = {
            "id": _edge_id(edge.source, edge.target, edge.sourceHandle, edge.targetHandle),
            "source": edge.source,
            "target": edge.target,
        }
        if edge.sourceHandle is not None:
            hydrated["sourceHandle"] = edge.sourceHandle
        if edge.targetHandle is not None:
            hydrated["targetHandle"] = edge.targetHandle
        edges.append(hydrated)

    graph: dict[str, Any] = {"nodes": nodes, "edges": edges}
    if doc.engine is not None:
        graph["engine"] = doc.engine
    return (doc.name, doc.description, graph)


def _load_dir(subdir: str) -> list[DemoFlowDocument]:
    dir_path = _RESOURCES / subdir
    docs: list[DemoFlowDocument] = []
    for path in sorted(dir_path.glob("*.flow.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DemoResourceError(f"demo flow document {path.name} is not valid JSON: {exc}") from exc
        try:
            docs.append(DemoFlowDocument.model_validate(raw))
        except ValidationError as exc:
            raise DemoResourceError(f"invalid demo flow document {path.name}: {exc}") from exc
    return docs


@lru_cache(maxsize=None)
def load_demo_flow_documents(include_ml: bool = False) -> tuple[DemoFlowDocument, ...]:
    """All demo flow documents in presentation order (ETL first, then ML).

    Cached because the JSON never changes at runtime; returns a tuple of shared
    model instances. Do not mutate the returned documents — ``hydrate_document``
    deep-copies node config so the graphs it builds are independent of this
    cache.
    """
    docs = list(_load_dir("etl"))
    if include_ml:
        docs += _load_dir("ml")
    return tuple(docs)


def build_demo_flows(dataset_ids: dict[str, str], include_ml: bool = False) -> list[DemoFlow]:
    """Return every demo flow wired to the given dataset ids (by CSV file name).

    When ``include_ml`` is set (the ML extension is installed), the
    machine-learning example flows are appended — they reference the ``iris.csv``
    / ``house_prices.csv`` datasets that ``build_demo_frames`` adds in the same
    mode.
    """
    return [hydrate_document(doc, dataset_ids) for doc in load_demo_flow_documents(include_ml)]
