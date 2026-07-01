"""End-to-end test for a storage-backed flow run.

This is the integration layer *above* the connector unit tests: it drives a full
flow through the HTTP API — ``storageInput -> filterRows -> storageOutput`` — and
proves that ``app/services/storage_resolver.py`` correctly wires storage
connections into the execution engine. Specifically it exercises:

* ``materialize_storage_inputs`` — download the S3 object into the executor
* the executor running the transform off the event loop
* ``push_storage_outputs`` — upload the result back to S3

It runs against MinIO (the same emulator as test_s3_connector) and self-skips
unless ``CIAREN_TEST_S3_ENDPOINT`` is set, under the ``connectors`` marker.
"""

from __future__ import annotations

import io
import os
import uuid

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connection import Connection

pytestmark = pytest.mark.connectors

_ENDPOINT = os.environ.get("CIAREN_TEST_S3_ENDPOINT")
_ACCESS_KEY = os.environ.get("CIAREN_TEST_S3_ACCESS_KEY", "minioadmin")
_SECRET_KEY = os.environ.get("CIAREN_TEST_S3_SECRET_KEY", "minioadmin")
_REGION = os.environ.get("CIAREN_TEST_S3_REGION", "us-east-1")

if not _ENDPOINT:
    pytest.skip(
        "CIAREN_TEST_S3_ENDPOINT not set; skipping storage-backed flow test.",
        allow_module_level=True,
    )

boto3 = pytest.importorskip("boto3", reason="boto3 not installed (pip install ciaren[s3])")


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
        region_name=_REGION,
    )


@pytest.fixture
def bucket():
    """A unique MinIO bucket, removed (with its objects) after the test."""
    name = f"ciaren-flow-{uuid.uuid4().hex[:12]}"
    client = _s3_client()
    client.create_bucket(Bucket=name)
    try:
        yield name
    finally:
        try:
            for obj in client.list_objects_v2(Bucket=name).get("Contents", []):
                client.delete_object(Bucket=name, Key=obj["Key"])
            client.delete_bucket(Bucket=name)
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


async def _make_connection(db: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: str) -> str:
    """Insert an S3 storage Connection pointing at MinIO; return its id.

    The secret is resolved from an env var at call time (never persisted), so we
    point ``password_env`` at a variable we set here.
    """
    monkeypatch.setenv("FF_TEST_FLOW_S3_SECRET", _SECRET_KEY)
    conn = Connection(
        name=f"minio-{uuid.uuid4().hex[:8]}",
        provider="s3",
        host=_ENDPOINT,  # -> StorageSpec.endpoint_url
        database=bucket,  # -> StorageSpec.bucket
        username=_ACCESS_KEY,  # -> StorageSpec.access_key
        password_env="FF_TEST_FLOW_S3_SECRET",
        options_json={"region": _REGION},
    )
    db.add(conn)
    await db.commit()
    return conn.id


async def test_storage_backed_flow_round_trips_through_s3(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: str
) -> None:
    # 1. Seed the input object in the bucket.
    raw = pd.DataFrame({"name": ["a", "b", "c", "d"], "score": [40, 60, 90, 55]})
    buf = io.BytesIO()
    raw.to_csv(buf, index=False)
    _s3_client().put_object(Bucket=bucket, Key="input/people.csv", Body=buf.getvalue())

    # 2. A storage Connection the flow's nodes reference.
    connection_id = await _make_connection(db_session, monkeypatch, bucket)

    # 3. storageInput -> filterRows(score >= 60) -> storageOutput.
    graph = {
        "nodes": [
            {
                "id": "in",
                "type": "storageInput",
                "data": {"config": {"connection_id": connection_id, "path": "input/people.csv", "format": "csv"}},
            },
            {
                "id": "flt",
                "type": "filterRows",
                "data": {"config": {"column": "score", "operator": ">=", "value": 60}},
            },
            {
                "id": "out",
                "type": "storageOutput",
                "data": {
                    "config": {
                        "connection_id": connection_id,
                        "path": "output/result.csv",
                        "format": "csv",
                        "if_exists": "overwrite",
                    }
                },
            },
        ],
        "edges": [
            {"id": "in->flt", "source": "in", "target": "flt"},
            {"id": "flt->out", "source": "flt", "target": "out"},
        ],
    }

    flow = (await client.post("/api/flows", json={"name": "storage-flow", "graph_json": graph})).json()

    # 4. Run it through the full HTTP path; the run executes synchronously in tests.
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"engine": "pandas"})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success", run.get("error_message")

    # 5. The transformed result must have been pushed back to S3 by push_storage_outputs.
    body = _s3_client().get_object(Bucket=bucket, Key="output/result.csv")["Body"].read()
    result = pd.read_csv(io.BytesIO(body))

    # filterRows(score >= 60) keeps b(60) and c(90) only.
    assert sorted(result["name"].tolist()) == ["b", "c"]
    assert sorted(result["score"].tolist()) == [60, 90]
