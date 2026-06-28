"""Backend-fed catalog: node / connector / category metadata for the editor.

The frontend renders what the backend (plus installed plugins) reports here
instead of hard-coding the node list, so a plugin that registers a node makes it
appear in the palette without a frontend rebuild. ML nodes are gated the same way
as ``GET /api/transformations`` — hidden unless the ML extension is ready.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.engine.node_metadata import CATEGORY_LABELS, CATEGORY_ORDER
from app.ml.availability import ml_extension_ready
from app.plugin_api import ConnectorSpec, ExporterSpec, NodeSpec
from app.plugins import get_registry

router = APIRouter()


class CategorySpec(BaseModel):
    id: str
    label: str


@router.get("/nodes", response_model=list[NodeSpec])
async def list_catalog_nodes(category: str | None = None) -> list[NodeSpec]:
    """The full node catalog. ML nodes are omitted unless the ML extension is
    ready; an optional ``category`` filter narrows to one palette group."""
    specs = get_registry().node_specs()
    if not ml_extension_ready():
        specs = [s for s in specs if not s.requires_ml]
    if category is not None:
        specs = [s for s in specs if s.category == category]
    return specs


@router.get("/connectors", response_model=list[ConnectorSpec])
async def list_catalog_connectors() -> list[ConnectorSpec]:
    """Connectors contributed by the core and any installed plugins, including
    driver availability and the connection-form metadata the UI needs."""
    return get_registry().connector_specs()


@router.get("/exporters", response_model=list[ExporterSpec])
async def list_catalog_exporters() -> list[ExporterSpec]:
    """Code/artifact exporters contributed by the core and any installed plugins
    (python, eager-polars, lazy-polars today)."""
    return get_registry().exporter_specs()


@router.get("/categories", response_model=list[CategorySpec])
async def list_catalog_categories() -> list[CategorySpec]:
    """Palette categories in display order."""
    return [CategorySpec(id=cid, label=CATEGORY_LABELS[cid]) for cid in CATEGORY_ORDER]
