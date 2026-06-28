"""
Dataset endpoint tests.

Happy path and edge cases for:
  POST /api/datasets/upload
  GET  /api/datasets
  GET  /api/datasets/{id}
  GET  /api/datasets/{id}/schema
  GET  /api/datasets/{id}/sample
"""

import io
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# File factories
# ---------------------------------------------------------------------------

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30, "score": 9.5, "active": True},
    {"name": "Bob", "age": 25, "score": 8.0, "active": False},
    {"name": "Charlie", "age": 35, "score": 7.5, "active": True},
]


def _csv(rows: list[dict] = ROWS) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _excel(rows: list[dict] = ROWS) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _parquet(rows: list[dict] = ROWS) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


async def _upload(
    client: AsyncClient,
    content: bytes,
    filename: str = "test.csv",
    content_type: str = "text/csv",
) -> dict:
    r = await client.post(
        "/api/datasets/upload",
        files={"file": (filename, content, content_type)},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# POST /api/datasets/upload — happy path
# ---------------------------------------------------------------------------


async def test_upload_csv(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    assert body["source_type"] == "csv"
    assert body["name"] == "test.csv"
    assert "id" in body
    assert "created_at" in body


async def test_upload_excel(client: AsyncClient) -> None:
    body = await _upload(client, _excel(), "data.xlsx", "application/vnd.ms-excel")
    assert body["source_type"] == "excel"
    assert body["name"] == "data.xlsx"


async def test_upload_parquet(client: AsyncClient) -> None:
    body = await _upload(client, _parquet(), "data.parquet", "application/octet-stream")
    assert body["source_type"] == "parquet"


async def test_upload_returns_column_schema(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    schema = body["column_schema"]
    assert isinstance(schema, list)
    names = [c["name"] for c in schema]
    assert names == ["name", "age", "score", "active"]


async def test_upload_infers_correct_types(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    schema = {c["name"]: c["type"] for c in body["column_schema"]}
    assert schema["name"] == "string"
    assert schema["age"] == "integer"
    assert schema["score"] == "float"
    assert schema["active"] == "boolean"


async def test_upload_returns_column_profile(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    profile = body["column_profile"]
    assert isinstance(profile, list)
    by_name = {p["name"]: p for p in profile}
    assert set(by_name) == {"name", "age", "score", "active"}
    assert by_name["age"]["dtype"] == "integer"
    assert by_name["age"]["null_count"] == 0
    assert by_name["age"]["min"] == 25
    assert by_name["age"]["max"] == 35


async def test_profile_endpoint_returns_stats(client: AsyncClient) -> None:
    ds = await _upload(client, _csv())
    r = await client.get(f"/api/datasets/{ds['id']}/profile")
    assert r.status_code == 200
    by_name = {p["name"]: p for p in r.json()}
    assert set(by_name) == {"name", "age", "score", "active"}
    assert by_name["age"]["dtype"] == "integer"


async def test_upload_returns_data_sample(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    sample = body["data_sample"]
    assert isinstance(sample, list)
    assert len(sample) == len(ROWS)
    assert sample[0]["name"] == "Alice"


async def test_upload_sample_capped_at_100_rows(client: AsyncClient) -> None:
    rows = [{"x": i} for i in range(200)]
    body = await _upload(client, _csv(rows))
    assert len(body["data_sample"]) == 100


async def test_upload_csv_with_nan_values(client: AsyncClient) -> None:
    rows = [{"a": 1, "b": None}, {"a": 2, "b": 3.0}]
    body = await _upload(client, _csv(rows))
    sample = body["data_sample"]
    assert sample[0]["b"] is None  # NaN serialised as None


async def test_upload_location_not_in_response(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    assert "location" not in body


async def test_upload_id_is_uuid_format(client: AsyncClient) -> None:
    import re

    body = await _upload(client, _csv())
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    assert uuid_re.match(body["id"])


async def test_upload_assigns_unique_ids(client: AsyncClient) -> None:
    b1 = await _upload(client, _csv(), "a.csv")
    b2 = await _upload(client, _csv(), "b.csv")
    assert b1["id"] != b2["id"]


async def test_upload_special_chars_in_filename(client: AsyncClient) -> None:
    body = await _upload(client, _csv(), "my file (copy).csv")
    assert body["name"] == "my file (copy).csv"


# ---------------------------------------------------------------------------
# POST /api/datasets/upload — error cases
# ---------------------------------------------------------------------------


async def test_upload_unsupported_type_returns_400(client: AsyncClient) -> None:
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400
    assert "unsupported" in r.json()["detail"].lower()


async def test_upload_txt_creates_text_dataset(client: AsyncClient) -> None:
    # .txt is a supported (text) format — one row per line, single "text" column.
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("notes.txt", b"line one\nline two", "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_type"] == "text"
    assert [f["name"] for f in body["column_schema"]] == ["text"]


async def test_upload_no_extension_returns_400(client: AsyncClient) -> None:
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("nodotfile", b"data", "application/octet-stream")},
    )
    assert r.status_code == 400


async def test_upload_corrupt_parquet_returns_400(client: AsyncClient) -> None:
    # Parquet files must start with the PAR1 magic bytes; anything else is rejected
    # by pyarrow with a reliable error — unlike CSV which accepts almost any bytes.
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("data.parquet", b"not valid parquet content", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "parse" in r.json()["detail"].lower()


async def test_upload_too_large_returns_413(client: AsyncClient, monkeypatch) -> None:
    from app.core.config import get_settings

    # Setting the env var and clearing the LRU cache ensures DatasetService picks
    # it up at request time. Using setattr on the module wouldn't work because
    # dataset_service.py already holds a direct reference to the original function.
    monkeypatch.setenv("FLOWFRAME_MAX_UPLOAD_SIZE_MB", "0")
    get_settings.cache_clear()

    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("big.csv", b"name\nAlice\n", "text/csv")},
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# POST /api/datasets/upload — versioning
# ---------------------------------------------------------------------------


async def test_first_upload_is_version_1(client: AsyncClient) -> None:
    body = await _upload(client, _csv(), "sales.csv")
    assert body["latest_version"] == 1
    assert body["version_count"] == 1


async def test_reupload_same_name_creates_new_version(client: AsyncClient) -> None:
    await _upload(client, _csv(), "sales.csv")
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", _csv(), "text/csv")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["latest_version"] == 2
    assert body["version_count"] == 2


async def test_reupload_does_not_create_second_dataset(client: AsyncClient) -> None:
    await _upload(client, _csv(), "sales.csv")
    await client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", _csv(), "text/csv")},
    )
    r = await client.get("/api/datasets")
    assert len(r.json()) == 1
    assert r.json()[0]["version_count"] == 2


async def test_reupload_name_match_is_case_insensitive(client: AsyncClient) -> None:
    await _upload(client, _csv(), "Sales.csv")
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", _csv(), "text/csv")},
    )
    assert r.json()["version_count"] == 2  # same logical dataset


async def test_same_stem_different_extension_are_separate_datasets(
    client: AsyncClient,
) -> None:
    # The dataset name is the full filename (incl. extension), so data.csv and
    # data.xlsx are independent datasets, each with its own version history.
    await _upload(client, _csv(), "data.csv")
    excel = await _upload(client, _excel(), "data.xlsx", "application/vnd.ms-excel")
    assert excel["source_type"] == "excel"
    r = await client.get("/api/datasets")
    assert len(r.json()) == 2


async def test_different_names_create_separate_datasets(client: AsyncClient) -> None:
    await _upload(client, _csv(), "a.csv")
    await _upload(client, _csv(), "b.csv")
    r = await client.get("/api/datasets")
    assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# GET /api/datasets/{id}/versions
# ---------------------------------------------------------------------------


async def test_list_versions_returns_all_newest_first(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "sales.csv")
    await client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", _csv(), "text/csv")},
    )
    r = await client.get(f"/api/datasets/{up['id']}/versions")
    assert r.status_code == 200
    versions = r.json()
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[0]["row_count"] == len(ROWS)


async def test_list_versions_is_paginated(client: AsyncClient) -> None:
    # Output datasets accrue a version per run; the endpoint must page (newest-first).
    up = await _upload(client, _csv(), "sales.csv")
    for _ in range(4):  # -> 5 versions total
        await client.post("/api/datasets/upload", files={"file": ("sales.csv", _csv(), "text/csv")})

    page1 = (await client.get(f"/api/datasets/{up['id']}/versions?limit=2")).json()
    assert [v["version_number"] for v in page1] == [5, 4]
    page2 = (await client.get(f"/api/datasets/{up['id']}/versions?limit=2&offset=2")).json()
    assert [v["version_number"] for v in page2] == [3, 2]
    # limit is bounded
    r = await client.get(f"/api/datasets/{up['id']}/versions?limit=0")
    assert r.status_code == 422


async def test_get_schema_for_specific_version(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "sales.csv")
    r = await client.get(f"/api/datasets/{up['id']}/schema?version=1")
    assert r.status_code == 200
    assert {"name": "name", "type": "string"} in r.json()


async def test_get_schema_unknown_version_404(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "sales.csv")
    r = await client.get(f"/api/datasets/{up['id']}/schema?version=99")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/datasets — list
# ---------------------------------------------------------------------------


async def test_list_datasets_empty(client: AsyncClient) -> None:
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_datasets_returns_uploaded(client: AsyncClient) -> None:
    await _upload(client, _csv(), "a.csv")
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_list_datasets_returns_all(client: AsyncClient) -> None:
    await _upload(client, _csv(), "a.csv")
    await _upload(client, _csv(), "b.csv")
    r = await client.get("/api/datasets")
    assert len(r.json()) == 2


async def test_list_datasets_ordered_by_created_at_desc(client: AsyncClient) -> None:
    first = await _upload(client, _csv(), "first.csv")
    second = await _upload(client, _csv(), "second.csv")
    r = await client.get("/api/datasets")
    ids = [d["id"] for d in r.json()]
    assert ids[0] == second["id"]
    assert ids[1] == first["id"]


# ---------------------------------------------------------------------------
# GET /api/datasets/{id} — retrieve
# ---------------------------------------------------------------------------


async def test_get_dataset(client: AsyncClient) -> None:
    uploaded = await _upload(client, _csv())
    r = await client.get(f"/api/datasets/{uploaded['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == uploaded["id"]
    assert r.json()["name"] == uploaded["name"]


async def test_get_dataset_not_found(client: AsyncClient) -> None:
    r = await client.get("/api/datasets/nonexistent-id")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


async def test_get_dataset_includes_schema_and_sample(client: AsyncClient) -> None:
    uploaded = await _upload(client, _csv())
    r = await client.get(f"/api/datasets/{uploaded['id']}")
    body = r.json()
    assert body["column_schema"] is not None
    assert body["data_sample"] is not None


# ---------------------------------------------------------------------------
# GET /api/datasets/{id}/schema
# ---------------------------------------------------------------------------


async def test_get_schema(client: AsyncClient) -> None:
    uploaded = await _upload(client, _csv())
    r = await client.get(f"/api/datasets/{uploaded['id']}/schema")
    assert r.status_code == 200
    schema = r.json()
    assert isinstance(schema, list)
    assert {"name": "name", "type": "string"} in schema
    assert {"name": "age", "type": "integer"} in schema


async def test_get_schema_not_found(client: AsyncClient) -> None:
    r = await client.get("/api/datasets/missing/schema")
    assert r.status_code == 404


async def test_get_schema_matches_upload_schema(client: AsyncClient) -> None:
    uploaded = await _upload(client, _csv())
    r_schema = await client.get(f"/api/datasets/{uploaded['id']}/schema")
    assert r_schema.json() == uploaded["column_schema"]


# ---------------------------------------------------------------------------
# GET /api/datasets/{id}/sample
# ---------------------------------------------------------------------------


async def test_get_sample(client: AsyncClient) -> None:
    uploaded = await _upload(client, _csv())
    r = await client.get(f"/api/datasets/{uploaded['id']}/sample")
    assert r.status_code == 200
    sample = r.json()
    assert isinstance(sample, list)
    assert len(sample) == len(ROWS)
    assert sample[0]["name"] == "Alice"


async def test_get_sample_not_found(client: AsyncClient) -> None:
    r = await client.get("/api/datasets/missing/sample")
    assert r.status_code == 404


async def test_get_sample_matches_upload_sample(client: AsyncClient) -> None:
    uploaded = await _upload(client, _csv())
    r_sample = await client.get(f"/api/datasets/{uploaded['id']}/sample")
    assert r_sample.json() == uploaded["data_sample"]


async def test_get_sample_parquet_roundtrip(client: AsyncClient) -> None:
    uploaded = await _upload(client, _parquet(), "data.parquet", "application/octet-stream")
    r = await client.get(f"/api/datasets/{uploaded['id']}/sample")
    assert r.status_code == 200
    names = [row["name"] for row in r.json()]
    assert names == ["Alice", "Bob", "Charlie"]


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_dataset_response_shape(client: AsyncClient) -> None:
    body = await _upload(client, _csv())
    expected_keys = {"id", "name", "source_type", "column_schema", "data_sample", "created_at", "updated_at"}
    assert expected_keys.issubset(body.keys())
    assert "location" not in body


# ---------------------------------------------------------------------------
# PATCH / DELETE / version download
# ---------------------------------------------------------------------------


async def test_patch_dataset_updates_is_disabled(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "old.csv")
    r = await client.patch(f"/api/datasets/{up['id']}", json={"is_disabled": False})
    assert r.status_code == 200, r.text
    assert r.json()["is_disabled"] is False


async def test_patch_dataset_disable_cascades_to_flows(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "sales.csv")
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": up["id"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()

    r = await client.patch(f"/api/datasets/{up['id']}", json={"is_disabled": True})
    assert r.status_code == 200, r.text

    refreshed = (await client.get(f"/api/flows/{flow['id']}")).json()
    assert refreshed["is_disabled"] is True


async def test_delete_dataset(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "tmp.csv")
    # Default delete is a soft-delete: the dataset is hidden from the list but
    # still fetchable (marked deleted) so historical runs resolve. ?purge=true
    # removes it for good. See tests/api/test_dataset_soft_delete.py.
    r = await client.delete(f"/api/datasets/{up['id']}")
    assert r.status_code == 204
    assert up["id"] not in [d["id"] for d in (await client.get("/api/datasets")).json()]
    r2 = await client.delete(f"/api/datasets/{up['id']}", params={"purge": True})
    assert r2.status_code == 204
    assert (await client.get(f"/api/datasets/{up['id']}")).status_code == 404


async def test_delete_dataset_not_found(client: AsyncClient) -> None:
    r = await client.delete("/api/datasets/missing")
    assert r.status_code == 404


async def test_download_dataset_version(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "sales.csv")
    r = await client.get(f"/api/datasets/{up['id']}/versions/1/download")
    assert r.status_code == 200
    assert b"Alice" in r.content


async def test_download_unknown_version_404(client: AsyncClient) -> None:
    up = await _upload(client, _csv(), "sales.csv")
    r = await client.get(f"/api/datasets/{up['id']}/versions/99/download")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests for pure helpers (no HTTP, no DB)
# ---------------------------------------------------------------------------


def test_validate_extension_csv() -> None:
    from app.services.dataset_service import _validate_extension

    assert _validate_extension("data.csv") == "csv"


def test_validate_extension_xlsx() -> None:
    from app.services.dataset_service import _validate_extension

    assert _validate_extension("report.xlsx") == "excel"


def test_validate_extension_xls() -> None:
    from app.services.dataset_service import _validate_extension

    assert _validate_extension("old.xls") == "excel"


def test_validate_extension_parquet() -> None:
    from app.services.dataset_service import _validate_extension

    assert _validate_extension("dump.parquet") == "parquet"


def test_validate_extension_case_insensitive() -> None:
    from app.services.dataset_service import _validate_extension

    assert _validate_extension("DATA.CSV") == "csv"


def test_validate_extension_unsupported_raises() -> None:
    from app.core.exceptions import UnsupportedFileTypeError
    from app.services.dataset_service import _validate_extension

    with pytest.raises(UnsupportedFileTypeError):
        _validate_extension("report.pdf")


def test_validate_extension_no_extension_raises() -> None:
    from app.core.exceptions import UnsupportedFileTypeError
    from app.services.dataset_service import _validate_extension

    with pytest.raises(UnsupportedFileTypeError):
        _validate_extension("nodotfile")


def test_extract_schema_types() -> None:
    from app.services.dataset_service import _extract_schema

    df = pd.DataFrame(
        {
            "s": ["a", "b"],
            "i": pd.array([1, 2], dtype="int64"),
            "f": [1.0, 2.5],
            "b": [True, False],
        }
    )
    schema = {c["name"]: c["type"] for c in _extract_schema(df)}
    assert schema["s"] == "string"
    assert schema["i"] == "integer"
    assert schema["f"] == "float"
    assert schema["b"] == "boolean"


def test_extract_schema_preserves_column_order() -> None:
    from app.services.dataset_service import _extract_schema

    df = pd.DataFrame({"z": [1], "a": [2], "m": [3]})
    names = [c["name"] for c in _extract_schema(df)]
    assert names == ["z", "a", "m"]


def test_df_to_records_nan_becomes_none() -> None:
    from app.services.dataset_service import _df_to_records

    df = pd.DataFrame({"x": [1, None, 3]})
    records = _df_to_records(df, 10)
    assert records[1]["x"] is None


def test_df_to_records_respects_limit() -> None:
    from app.services.dataset_service import _df_to_records

    df = pd.DataFrame({"x": range(50)})
    assert len(_df_to_records(df, 10)) == 10


def test_storage_filename_sanitises_spaces() -> None:
    from app.services.dataset_service import _storage_filename

    result = _storage_filename("abc-123", "my file (v2).csv")
    assert " " not in result
    assert "(" not in result
    assert result.startswith("abc-123_")
    assert result.endswith(".csv")
