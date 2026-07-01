"""Live round-trip tests for the Google Cloud Storage connector.

These exercise the real google-cloud-storage code path (``app/connectors/
gcs.py``) against the fake-gcs-server emulator — in CI (see ``.github/workflows/
connectors-integration.yml``) or locally.

The connector reaches the emulator via the ``STORAGE_EMULATOR_HOST`` env var,
which the google-cloud-storage client honours (anonymous credentials). The whole
module self-skips unless that var is set, so the default infra-free suite is
unaffected. To run locally::

    docker run -d -p 4443:4443 fsouza/fake-gcs-server \\
        -scheme http -port 4443 -public-host 127.0.0.1:4443
    STORAGE_EMULATOR_HOST=http://127.0.0.1:4443 \\
        pytest tests/integration/test_gcs_connector.py -m connectors
"""

from __future__ import annotations

import os
import uuid

import pandas as pd
import pytest

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec

pytestmark = pytest.mark.connectors

# Set by the test harness / CI to point the GCS client at the emulator.
_EMULATOR = os.environ.get("STORAGE_EMULATOR_HOST")
_PROJECT = os.environ.get("CIAREN_TEST_GCS_PROJECT", "test-project")

if not _EMULATOR:
    pytest.skip(
        "STORAGE_EMULATOR_HOST not set; skipping live GCS connector tests.",
        allow_module_level=True,
    )

storage = pytest.importorskip(
    "google.cloud.storage", reason="google-cloud-storage not installed (pip install ciaren[gcs])"
)


def _spec(bucket: str) -> StorageSpec:
    return StorageSpec(provider="gcs", bucket=bucket, extra={"project_id": _PROJECT})


@pytest.fixture
def bucket():
    """Create a unique bucket in the emulator and tear it down afterwards."""
    name = f"ff-test-{uuid.uuid4().hex[:12]}"
    client = storage.Client(project=_PROJECT)  # uses STORAGE_EMULATOR_HOST + anonymous creds
    client.create_bucket(name)
    try:
        yield name
    finally:
        try:
            b = client.bucket(name)
            for blob in client.list_blobs(name):
                blob.delete()
            b.delete()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


@pytest.fixture
def connector():
    from app.connectors.gcs import GCSConnector

    return GCSConnector()


def test_test_connection_succeeds_on_existing_bucket(connector, bucket):
    connector.test_connection(_spec(bucket))


def test_test_connection_fails_on_missing_bucket(connector):
    with pytest.raises(ConnectorError):
        connector.test_connection(_spec(f"missing-{uuid.uuid4().hex[:8]}"))


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_write_then_read_round_trip(connector, bucket, fmt):
    spec = _spec(bucket)
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    key = f"data/sample.{fmt}"

    connector.write_file(spec, df, key, fmt, "overwrite")
    out = connector.read_file(spec, key, fmt)

    assert list(out.columns) == ["a", "b"]
    assert out["a"].tolist() == [1, 2, 3]
    assert out["b"].tolist() == ["x", "y", "z"]


def test_list_objects_returns_written_keys(connector, bucket):
    spec = _spec(bucket)
    df = pd.DataFrame({"a": [1]})
    connector.write_file(spec, df, "prefix/one.csv", "csv", "overwrite")
    connector.write_file(spec, df, "prefix/two.csv", "csv", "overwrite")
    connector.write_file(spec, df, "other/three.csv", "csv", "overwrite")

    assert {"prefix/one.csv", "prefix/two.csv", "other/three.csv"} <= set(connector.list_objects(spec))
    assert set(connector.list_objects(spec, prefix="prefix/")) == {"prefix/one.csv", "prefix/two.csv"}


def test_write_error_mode_rejects_existing_object(connector, bucket):
    spec = _spec(bucket)
    df = pd.DataFrame({"a": [1]})
    connector.write_file(spec, df, "guarded.csv", "csv", "overwrite")

    with pytest.raises(ConnectorError, match="already exists"):
        connector.write_file(spec, df, "guarded.csv", "csv", "error")


def test_overwrite_mode_replaces_existing_object(connector, bucket):
    spec = _spec(bucket)
    connector.write_file(spec, pd.DataFrame({"a": [1]}), "r.csv", "csv", "overwrite")
    connector.write_file(spec, pd.DataFrame({"a": [1, 2, 3]}), "r.csv", "csv", "overwrite")

    assert len(connector.read_file(spec, "r.csv", "csv")) == 3


def test_read_missing_object_raises(connector, bucket):
    with pytest.raises(ConnectorError):
        connector.read_file(_spec(bucket), "nope.csv", "csv")
