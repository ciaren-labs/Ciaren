# SPDX-License-Identifier: AGPL-3.0-only
"""Upload dialect handling end to end: auto-detection, explicit overrides,
normalized storage (both engines read the stored copy with defaults), and
exported code reproducing the ORIGINAL dialect.
"""

import io

import pandas as pd
from httpx import AsyncClient

# A European Excel-style export: semicolon separator, Latin-1 accents,
# decimal commas.
_EURO_CSV = "producto;precio;cantidad\ncafé;1,50;2\ntécnica;2,75;3\n".encode("latin-1")


async def _upload(client: AsyncClient, name: str, content: bytes, params: str = "") -> dict:
    r = await client.post(
        f"/api/datasets/upload{params}",
        files={"file": (name, content, "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_semicolon_latin1_upload_autodetects(client: AsyncClient) -> None:
    ds = await _upload(client, "ventas.csv", _EURO_CSV)
    assert [c["name"] for c in ds["column_schema"]] == ["producto", "precio", "cantidad"]
    types = {c["name"]: c["type"] for c in ds["column_schema"]}
    assert types["precio"] == "float"  # decimal comma parsed as a number
    assert types["cantidad"] == "integer"
    assert ds["data_sample"][0]["producto"] == "café"  # encoding survived
    assert ds["data_sample"][0]["precio"] == 1.5
    detected = ds["parse_options"]
    assert detected["delimiter"] == ";"
    assert detected["decimal"] == ","
    assert detected["encoding"] in ("cp1252", "latin-1")


async def test_normalized_copy_is_read_identically_by_both_engines(client: AsyncClient) -> None:
    """The stored file is normalized, so a run gives the same numbers on pandas
    and polars with plain default reads."""
    ds = await _upload(client, "ventas_run.csv", _EURO_CSV)
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {
                "id": "f",
                "type": "filterRows",
                "data": {"config": {"column": "precio", "operator": ">", "value": 2}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "f"},
            {"id": "e2", "source": "f", "target": "out"},
        ],
    }
    r = await client.post("/api/flows", json={"name": "euro", "graph_json": graph})
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    for engine in ("pandas", "polars"):
        r = await client.post(f"/api/flows/{flow_id}/runs", json={"engine": engine})
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["status"] == "success", run
        out = await client.get(f"/api/runs/{run['id']}/output", params={"node_id": "out"})
        assert out.status_code == 200
        df = pd.read_csv(io.BytesIO(out.content))
        assert list(df["producto"]) == ["técnica"], f"{engine}: {df}"
        assert list(df["precio"]) == [2.75]


async def test_explicit_overrides_beat_detection(client: AsyncClient) -> None:
    # Pipe-separated content that a sniffer could misread; the explicit option wins.
    content = b"a|b\n1|2\n3|4\n"
    ds = await _upload(client, "piped.csv", content, params="?delimiter=%7C")
    assert [c["name"] for c in ds["column_schema"]] == ["a", "b"]
    assert ds["parse_options"]["delimiter"] == "|"


async def test_invalid_options_are_clear_400s(client: AsyncClient) -> None:
    r = await client.post(
        "/api/datasets/upload?delimiter=%23%23",
        files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert r.status_code == 400, r.text
    assert "delimiter" in r.json()["detail"]

    r = await client.post(
        "/api/datasets/upload?sheet=Data",
        files={"file": ("x2.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert r.status_code == 400, r.text
    assert "sheet" in r.json()["detail"].lower()


async def test_default_dialect_records_no_options(client: AsyncClient) -> None:
    ds = await _upload(client, "plain.csv", b"a,b\n1,2\n")
    assert ds["parse_options"] is None


async def test_excel_sheet_selection(client: AsyncClient) -> None:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as writer:
        pd.DataFrame({"first": [1]}).to_excel(writer, sheet_name="Uno", index=False)
        pd.DataFrame({"second": [2], "extra": [3]}).to_excel(writer, sheet_name="Ventas", index=False)
    content = buf.getvalue()

    ds = await _upload(client, "libro.xlsx", content, params="?sheet=Ventas")
    assert [c["name"] for c in ds["column_schema"]] == ["second", "extra"]
    assert ds["parse_options"] == {"sheet": "Ventas"}

    ds2 = await _upload(client, "libro2.xlsx", content, params="?sheet=1")
    assert [c["name"] for c in ds2["column_schema"]] == ["second", "extra"]

    ds3 = await _upload(client, "libro3.xlsx", content)
    assert [c["name"] for c in ds3["column_schema"]] == ["first"]
    assert ds3["parse_options"] is None


async def test_excel_sheet_literally_named_a_digit_wins_over_index(client: AsyncClient) -> None:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as writer:
        pd.DataFrame({"first": [1]}).to_excel(writer, sheet_name="Uno", index=False)
        pd.DataFrame({"named_two": [2]}).to_excel(writer, sheet_name="2", index=False)
    ds = await _upload(client, "digitsheet.xlsx", buf.getvalue(), params="?sheet=2")
    assert [c["name"] for c in ds["column_schema"]] == ["named_two"]
    assert ds["parse_options"] == {"sheet": "2"}


async def test_tsv_with_encoding_and_decimal_exports_valid_polars(client: AsyncClient) -> None:
    """Audit repro: TSV + cp1252 + decimal commas must emit the tab separator
    in the polars decode wrapper (the decimal flag used to displace it)."""
    content = "producto\tprecio\ncafé\t1,50\ntécnica\t2,75\n".encode("cp1252")
    r = await client.post("/api/datasets/upload", files={"file": ("euro.tsv", content, "text/tab-separated-values")})
    assert r.status_code == 201, r.text
    ds = r.json()
    assert {c["name"]: c["type"] for c in ds["column_schema"]}["precio"] == "float"

    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }
    r = await client.post("/api/flows", json={"name": "tsv-export", "graph_json": graph})
    r = await client.post(f"/api/flows/{r.json()['id']}/export/python", json={})
    body = r.json()
    import pathlib
    import tempfile

    import polars as pl

    for key in ("polars", "polars_lazy"):
        code = body[key]
        # Either quoting of the tab separator is fine — what matters is that
        # the decimal flag didn't displace it (the audit's repro).
        assert "separator=" in code and "\\t" in code, code
        assert "decimal_comma=True" in code
        # The emitted read must actually parse the original file.
        ns: dict = {"pl": pl}
        with tempfile.TemporaryDirectory() as tmp:
            orig = pathlib.Path(tmp) / "euro.tsv"
            orig.write_bytes(content)
            snippet = code.replace("'euro.tsv'", repr(str(orig)))
            # Keep the exec focused on the read: drop the output write line.
            snippet = "\n".join(ln for ln in snippet.splitlines() if ".write_csv(" not in ln)
            exec(snippet, ns)  # noqa: S102 - executing generated code on the original file
            frame = ns["df_euro"]  # named after the euro.tsv dataset
            frame = frame.collect() if hasattr(frame, "collect") else frame
            assert frame["precio"].to_list() == [1.5, 2.75]


async def test_export_reproduces_original_dialect(client: AsyncClient) -> None:
    """Exported scripts read the user's ORIGINAL file by name, so they must
    carry the original dialect — pandas via keywords, polars via a decode
    wrapper (polars only reads UTF-8)."""
    ds = await _upload(client, "ventas_export.csv", _EURO_CSV)
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }
    r = await client.post("/api/flows", json={"name": "euro-export", "graph_json": graph})
    assert r.status_code == 201, r.text
    r = await client.post(f"/api/flows/{r.json()['id']}/export/python", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    pandas_code = body["code"]
    assert "sep=';'" in pandas_code
    assert "decimal=','" in pandas_code
    assert "encoding=" in pandas_code
    for key in ("polars", "polars_lazy"):
        code = body[key]
        assert "encoding=" in code and "pl.read_csv(_f.read().encode()" in code, code
        assert "separator=';'" in code
        assert "decimal_comma=True" in code
