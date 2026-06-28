"""FlowFrame ``.flow`` schema package — the versioned, public flow-document
contract, its validation, and a migration framework. Importable without the
engine or FastAPI so external tooling can validate flow files.
"""

from app.flow_schema.document import (
    CURRENT_SCHEMA_VERSION,
    LEGACY_FORMAT,
    FlowGraph,
    FlowProject,
    FlowRequirements,
    FlowSchemaDocument,
    PluginRequirement,
)
from app.flow_schema.migrations import (
    MigrationError,
    clear_migrations,
    migrate,
    register_migration,
)
from app.flow_schema.validate import (
    FlowSchemaError,
    from_legacy_document,
    graph_structure_issues,
    missing_node_types,
    to_legacy_document,
    validate,
    validate_document,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "LEGACY_FORMAT",
    "FlowSchemaDocument",
    "FlowProject",
    "FlowGraph",
    "FlowRequirements",
    "PluginRequirement",
    "validate",
    "validate_document",
    "graph_structure_issues",
    "missing_node_types",
    "from_legacy_document",
    "to_legacy_document",
    "FlowSchemaError",
    "migrate",
    "register_migration",
    "clear_migrations",
    "MigrationError",
]
