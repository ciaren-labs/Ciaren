"""Node-catalog contract: the backend is the single source of truth for node
metadata (label, category, handles, default config), and the frontend keeps a static
fallback in ``frontend/src/lib/nodeCatalog.ts`` for offline/first-paint.

This snapshots the built-in (``ciaren.core``) catalog so:
  * a backend metadata change (relabel, recategorize, handle/default change, add/remove
    node) shows up as a reviewable diff instead of silently diverging from the frontend;
  * the committed JSON is the fixture a frontend contract test compares its static
    fallback against (see frontend/src/lib/__tests__/nodeCatalog.contract.test.ts).

Regenerate after an intentional change:

    CIAREN_UPDATE_NODE_CATALOG_SNAPSHOT=1 pytest tests/test_node_catalog_contract.py

Then reconcile the frontend fallback (the frontend test will fail until it matches).
"""

import json
import os
from pathlib import Path
from typing import Any

from app.plugins import ensure_plugins_loaded, get_registry

# The snapshot lives under the frontend so its contract test can import it directly;
# this backend test owns generating and guarding it.
_SNAPSHOT = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "__tests__" / "backendNodeCatalog.snapshot.json"
)


def _core_catalog() -> list[dict[str, Any]]:
    """The built-in node specs (provider ``ciaren.core``), sorted by id.

    Filtering to ``ciaren.core`` keeps this deterministic regardless of ML
    availability or which plugins happen to be enabled in the test process."""
    ensure_plugins_loaded()
    specs = [s.model_dump(mode="json") for s in get_registry().node_specs()]
    return sorted((s for s in specs if s.get("provider") == "ciaren.core"), key=lambda s: s["id"])


def test_core_node_catalog_snapshot_matches() -> None:
    current = _core_catalog()
    if os.getenv("CIAREN_UPDATE_NODE_CATALOG_SNAPSHOT"):
        _SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        _SNAPSHOT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return

    expected = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    cur_ids = [s["id"] for s in current]
    exp_ids = [s["id"] for s in expected]
    assert cur_ids == exp_ids, (
        f"core node set changed — added {sorted(set(cur_ids) - set(exp_ids))}, "
        f"removed {sorted(set(exp_ids) - set(cur_ids))}. "
        "Regenerate: CIAREN_UPDATE_NODE_CATALOG_SNAPSHOT=1 pytest tests/test_node_catalog_contract.py"
    )
    # Structural (key-order-independent) comparison per node.
    changed = [c["id"] for c, e in zip(current, expected, strict=True) if c != e]
    assert not changed, (
        f"core node metadata changed for {changed}. Regenerate the snapshot "
        "(CIAREN_UPDATE_NODE_CATALOG_SNAPSHOT=1) and reconcile frontend/src/lib/nodeCatalog.ts."
    )


def test_every_core_node_has_required_metadata() -> None:
    # Internal-consistency guard: a node with no label/category or malformed ports
    # would render broken in the palette.
    for spec in _core_catalog():
        assert spec["id"], spec
        assert spec["label"], f"{spec['id']} has no label"
        assert spec["category"], f"{spec['id']} has no category"
        for port in [*spec["inputs"], *spec["outputs"]]:
            assert port.get("id"), f"{spec['id']} has a port with no id"
