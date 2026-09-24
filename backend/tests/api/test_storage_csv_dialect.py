# SPDX-License-Identifier: AGPL-3.0-only
"""CSV dialect handling for ``storageInput`` end to end: detection shown by the
editor endpoint and applied to previews/runs, explicit overrides winning on both
engines and in exported code, graceful fallback, and path confinement.
"""

import io
import pathlib
from typing import Any

import pandas as pd
import polars as pl
import pytest
from httpx import AsyncClient

from app.connectors.local_storage import LocalStorageConnector
from app.engine.ingest import SNIFF_SAMPLE_BYTES

# A European Excel-style export: semicolons, cp1252 accents, decimal commas.
_EURO = "producto;precio\ncafé;1,50\ntécnica;2,75\n".encode("cp1252")
_NO_DIALECT = {"delimiter": None, "encoding": None, "decimal": None}


async def _local_connection(client: AsyncClient, root: pathlib.Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    r = await client.post(
        "/api/connections", json={"name": f"local-{root.name}", "provider": "local", "database": str(root)}
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _storage_flow(client: AsyncClient, conn_id: str, path: str, **dialect: Any) -> str:
    graph = {
        "nodes": [
            {
                "id": "st",
                "type": "storageInput",
                "data": {"config": {"connection_id": conn_id, "path": path, "format": "csv", **dialect}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "st", "target": "out"}],
    }
    r = await client.post("/api/flows", json={"name": f"storage-{path}", "graph_json": graph})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _detect(client: AsyncClient, conn_id: str, path: str) -> Any:
    return client.get(f"/api/connections/{conn_id}/objects/dialect", params={"path": path, "format": "csv"})


@pytest.mark.parametrize(
    ("content", "detected", "first_row"),
    [
        (_EURO, {"delimiter": ";", "encoding": "cp1252", "decimal": ","}, {"producto": "café", "precio": 1.5}),
        (b"producto\tprecio\ncafe\t1.5\n", {"delimiter": "\t", "encoding": "utf-8", "decimal": None}, None),
        (b"producto|precio\ncafe|1.5\n", {"delimiter": "|", "encoding": "utf-8", "decimal": None}, None),
        (
            "producto,precio\ncafé,1.5\n".encode("cp1252"),
            {"delimiter": ",", "encoding": "cp1252", "decimal": None},
            None,
        ),
    ],
    ids=["semicolon-cp1252", "tab", "pipe", "comma-cp1252"],
)
async def test_detected_dialect_is_reported_and_previewed_without_config(
    client: AsyncClient, tmp_path: pathlib.Path, content: bytes, detected: dict, first_row: dict | None
) -> None:
    root = tmp_path / "store"
    conn_id = await _local_connection(client, root)
    (root / "data.csv").write_bytes(content)

    r = await _detect(client, conn_id, "data.csv")
    assert r.status_code == 200, r.text
    assert r.json() == detected

    flow_id = await _storage_flow(client, conn_id, "data.csv")
    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "st"})
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["columns"] == ["producto", "precio"]
    assert preview["rows"][0] == (first_row or {"producto": "cafe" if b"cafe" in content else "café", "precio": 1.5})


@pytest.mark.parametrize("run_engine", ["pandas", "polars"])
@pytest.mark.parametrize(
    ("override", "columns", "precio"),
    [
        ({}, ["producto", "precio"], [1.5, 2.75]),  # detection alone
        ({"delimiter": "|"}, ["producto;precio"], None),  # override beats the detected ';'
        ({"decimal": "."}, ["producto", "precio"], ["1,50", "2,75"]),  # override beats the detected ','
    ],
    ids=["detected", "delimiter-override", "decimal-override"],
)
async def test_run_applies_detection_with_overrides_taking_precedence(
    client: AsyncClient, tmp_path: pathlib.Path, run_engine: str, override: dict, columns: list, precio: list | None
) -> None:
    root = tmp_path / "store"
    conn_id = await _local_connection(client, root)
    (root / "euro.csv").write_bytes(_EURO)
    flow_id = await _storage_flow(client, conn_id, "euro.csv", **override)

    r = await client.post(f"/api/flows/{flow_id}/runs", json={"engine": run_engine})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success", run
    out = await client.get(f"/api/runs/{run['id']}/output", params={"node_id": "out"})
    assert out.status_code == 200
    df = pd.read_csv(
        io.BytesIO(out.content), dtype={"precio": object} if precio and isinstance(precio[0], str) else None
    )
    assert list(df.columns) == columns
    if precio is not None:
        assert list(df["precio"]) == precio


@pytest.mark.parametrize(
    ("content", "detected", "columns"),
    [
        (b"", _NO_DIALECT, None),
        (b"PK\x03\x04\x00\x00\x14\x00binary;junk,\x00\x00", _NO_DIALECT, None),
        (b"a;b\n\x81\x8d;\x8f\x90\n", _NO_DIALECT, None),
        (b"justonecolumn\nvalue\n", {**_NO_DIALECT, "encoding": "utf-8"}, ["justonecolumn"]),
    ],
    ids=["empty", "binary", "undecodable", "single-column"],
)
async def test_detection_failure_reports_nothing_and_reads_with_defaults(
    client: AsyncClient, tmp_path: pathlib.Path, content: bytes, detected: dict, columns: list | None
) -> None:
    root = tmp_path / "store"
    conn_id = await _local_connection(client, root)
    (root / "odd.csv").write_bytes(content)

    r = await _detect(client, conn_id, "odd.csv")
    assert r.status_code == 200, r.text
    assert r.json() == detected
    if columns is not None:
        flow_id = await _storage_flow(client, conn_id, "odd.csv")
        r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "st"})
        assert r.status_code == 200, r.text
        assert r.json()["columns"] == columns


@pytest.mark.parametrize("path", ["../secret.csv", "sub/../../secret.csv"])
async def test_detection_cannot_read_outside_the_connection_root(
    client: AsyncClient, tmp_path: pathlib.Path, path: str
) -> None:
    (tmp_path / "secret.csv").write_bytes(b"token;value\nabc;1\n")
    conn_id = await _local_connection(client, tmp_path / "store")

    r = await _detect(client, conn_id, path)
    assert r.status_code == 400, r.text
    assert "escapes the storage root" in r.json()["detail"]


async def test_detection_respects_storage_allowed_roots(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    root = tmp_path / "store"
    conn_id = await _local_connection(client, root)
    (root / "euro.csv").write_bytes(_EURO)
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("CIAREN_STORAGE_ALLOWED_ROOTS", f'["{allowed.as_posix()}"]')
    get_settings.cache_clear()

    r = await _detect(client, conn_id, "euro.csv")
    assert r.status_code == 400, r.text
    assert "outside the allowed roots" in r.json()["detail"]


async def test_detection_reads_only_a_bounded_sample(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "store"
    conn_id = await _local_connection(client, root)
    (root / "big.csv").write_bytes(b"a;b\n" + b"1;2\n" * 100_000)  # ~400 KB
    requested: list[int] = []
    original = LocalStorageConnector.read_sample

    def spy(self: LocalStorageConnector, spec: Any, path: str, max_bytes: int) -> bytes:
        requested.append(max_bytes)
        data = original(self, spec, path, max_bytes)
        assert len(data) <= max_bytes
        return data

    def no_full_read(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("detection must not read the whole file")

    monkeypatch.setattr(LocalStorageConnector, "read_sample", spy)
    monkeypatch.setattr(LocalStorageConnector, "read_file", no_full_read)

    r = await _detect(client, conn_id, "big.csv")
    assert r.status_code == 200, r.text
    assert r.json()["delimiter"] == ";"
    assert requested == [SNIFF_SAMPLE_BYTES]


async def test_detection_rejects_non_storage_connections(client: AsyncClient, tmp_path: pathlib.Path) -> None:
    r = await client.post(
        "/api/connections", json={"name": "db", "provider": "sqlite", "database": str(tmp_path / "x.db")}
    )
    assert r.status_code == 201, r.text
    r = await _detect(client, r.json()["id"], "x.csv")
    assert r.status_code == 400, r.text
    assert "not a storage connection" in r.json()["detail"]


@pytest.mark.parametrize("key", ["code", "polars", "polars_lazy"])
async def test_export_reads_the_original_file_with_the_node_dialect(
    client: AsyncClient, tmp_path: pathlib.Path, key: str
) -> None:
    conn_id = await _local_connection(client, tmp_path / "store")
    flow_id = await _storage_flow(client, conn_id, "exports/euro.csv", delimiter=";", encoding="cp1252", decimal=",")
    r = await client.post(f"/api/flows/{flow_id}/export/python", json={})
    assert r.status_code == 200, r.text
    code = r.json()[key]

    original = tmp_path / "euro.csv"
    original.write_bytes(_EURO)
    snippet = code.replace("'euro.csv'", repr(str(original)))
    # Keep the exec focused on the read: drop the output write line.
    snippet = "\n".join(ln for ln in snippet.splitlines() if ".to_csv(" not in ln and ".write_csv(" not in ln)
    ns: dict[str, Any] = {"pd": pd, "pl": pl}
    exec(snippet, ns)  # noqa: S102 - executing generated code on the original file
    frame = ns["df_euro"]
    frame = frame.collect() if hasattr(frame, "collect") else frame
    assert list(frame["producto"]) == ["café", "técnica"]
    assert list(frame["precio"]) == [1.5, 2.75]


async def test_invalid_override_is_a_clear_400_before_reading(client: AsyncClient, tmp_path: pathlib.Path) -> None:
    conn_id = await _local_connection(client, tmp_path / "store")
    flow_id = await _storage_flow(client, conn_id, "missing.csv", delimiter="abc")

    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "st"})
    assert r.status_code == 400, r.text
    assert "delimiter must be one of" in r.json()["detail"]
    r = await client.post(f"/api/flows/{flow_id}/export/python", json={})
    assert r.status_code == 400, r.text


async def test_parameterized_delimiter_still_exports(client: AsyncClient, tmp_path: pathlib.Path) -> None:
    conn_id = await _local_connection(client, tmp_path / "store")
    graph = {
        "nodes": [
            {
                "id": "st",
                "type": "storageInput",
                "data": {
                    "config": {"connection_id": conn_id, "path": "euro.csv", "format": "csv", "delimiter": "{{ sep }}"}
                },
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "st", "target": "out"}],
        "parameters": [{"name": "sep", "type": "string", "default": ";"}],
    }
    r = await client.post("/api/flows", json={"name": "param-sep", "graph_json": graph})
    assert r.status_code == 201, r.text
    r = await client.post(f"/api/flows/{r.json()['id']}/export/python", json={})
    assert r.status_code == 200, r.text
    assert "sep=';'" in r.json()["code"]
