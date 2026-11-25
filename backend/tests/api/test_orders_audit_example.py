"""Run the shareable example through the editor's HTTP contract, not a hand-built graph."""

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.plugins import reset_registry

DEMO = Path(__file__).resolve().parents[3] / "examples" / "orders-audit"
VARIANTS = {"pandas": "code", "polars": "polars", "polars_lazy": "polars_lazy"}


@pytest.mark.parametrize("backend_name", ["pandas", "polars"])
async def test_import_run_and_export_orders_audit(client, tmp_path, monkeypatch, backend_name):
    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(DEMO.parent / "plugins"))
    reset_registry()
    response = await client.post("/api/plugins/community.validator/grant", json={"permissions": []})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "loaded"

    doc = json.loads((DEMO / "orders-audit.flow.json").read_text())
    imported = await client.post("/api/flows/import", json=doc)
    assert imported.status_code == 201, imported.text
    flow = imported.json()
    graph = flow["graph_json"]
    for node in graph["nodes"]:
        if node["type"] == "fileInput":
            csv = DEMO / f"{node['id']}.csv"
            dataset = await client.post(
                "/api/datasets/upload", files={"file": (csv.name, csv.read_bytes(), "text/csv")}
            )
            assert dataset.status_code == 201, dataset.text
            binding = dataset.json()
            node["data"]["config"].update(dataset_id=binding["id"], dataset_version=binding["latest_version"])

    url = f"/api/flows/{flow['id']}"
    saved = await client.put(url, json={"graph_json": graph})
    assert saved.status_code == 200, saved.text
    run = await client.post(f"{url}/runs", json={"engine": backend_name})
    assert run.status_code == 201, run.text
    assert run.json()["status"] == "success", run.text
    assert run.json()["engine"] == backend_name
    out = await client.get(f"/api/runs/{run.json()['id']}/output", params={"node_id": "audit"})
    assert out.status_code == 200, out.text
    runtime = pd.read_csv(io.BytesIO(out.content))
    assert_frame_equal(runtime, pd.read_csv(DEMO / "expected.csv"), check_exact=True)

    exports = await client.post(f"{url}/export/python")
    assert exports.status_code == 200, exports.text
    for variant, field in VARIANTS.items():
        if (variant == "pandas") != (backend_name == "pandas"):
            continue
        work = tmp_path / variant
        work.mkdir()
        for name in ("orders.csv", "catalog.csv"):
            shutil.copyfile(DEMO / name, work / name)
        script = work / f"audit_{variant}.py"
        code = exports.json()[field]
        script.write_text(code)
        assert code == (DEMO / "exported" / script.name).read_text()
        # CI uses its existing dependencies offline. The documented independent
        # check supplies fresh engine-only interpreters; reject an accidental app install.
        executable = os.environ.get(f"CIAREN_DEMO_{backend_name.upper()}_PYTHON")
        if executable:
            probe = (
                "from importlib.util import find_spec; "
                "assert all(find_spec(m) is None for m in ('app', 'ciaren_validator'))"
            )
            subprocess.run([executable, "-I", "-c", probe], cwd=work, check=True, timeout=30)
        else:
            executable = sys.executable
        proc = subprocess.run([executable, "-I", str(script)], cwd=work, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        assert_frame_equal(pd.read_csv(work / "audit.csv"), runtime, check_exact=True)
