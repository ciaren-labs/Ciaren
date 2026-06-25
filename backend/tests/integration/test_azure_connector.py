"""Live round-trip tests for the Azure Blob Storage connector.

These exercise the real azure-storage-blob code path (``app/connectors/
azure_blob.py``) against the Azurite emulator — in CI (see ``.github/workflows/
connectors-integration.yml``) or locally.

The whole module self-skips unless ``FLOWFRAME_TEST_AZURE_ENDPOINT`` is set, so
the default infra-free suite is unaffected. To run locally against Azurite::

    docker run -d -p 10000:10000 mcr.microsoft.com/azure-storage/azurite \\
        azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck
    FLOWFRAME_TEST_AZURE_ENDPOINT=http://127.0.0.1:10000/devstoreaccount1 \\
        pytest tests/integration/test_azure_connector.py -m connectors

Defaults match Azurite's well-known development account; override the account /
key env vars to point at any Azure-compatible store.
"""

from __future__ import annotations

import os
import uuid

import pandas as pd
import pytest

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec

pytestmark = pytest.mark.connectors

# Azurite's well-known development credentials (public, not a secret).
_AZURITE_ACCOUNT = "devstoreaccount1"
_AZURITE_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="

_ENDPOINT = os.environ.get("FLOWFRAME_TEST_AZURE_ENDPOINT")
_ACCOUNT = os.environ.get("FLOWFRAME_TEST_AZURE_ACCOUNT", _AZURITE_ACCOUNT)
_KEY = os.environ.get("FLOWFRAME_TEST_AZURE_KEY", _AZURITE_KEY)

if not _ENDPOINT:
    pytest.skip(
        "FLOWFRAME_TEST_AZURE_ENDPOINT not set; skipping live Azure Blob connector tests.",
        allow_module_level=True,
    )

azure_blob = pytest.importorskip(
    "azure.storage.blob", reason="azure-storage-blob not installed (pip install flowframe[azure])"
)


def _spec(container: str) -> StorageSpec:
    return StorageSpec(
        provider="azure_blob",
        bucket=container,
        access_key=_ACCOUNT,
        secret=_KEY,
        endpoint_url=_ENDPOINT,
    )


@pytest.fixture
def container():
    """Create a unique container for the test and tear it down afterwards."""
    name = f"ff-test-{uuid.uuid4().hex[:12]}"
    svc = azure_blob.BlobServiceClient(account_url=_ENDPOINT, credential=_KEY)
    svc.create_container(name)
    try:
        yield name
    finally:
        try:
            svc.delete_container(name)
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


@pytest.fixture
def connector():
    from app.connectors.azure_blob import AzureBlobConnector

    return AzureBlobConnector()


def test_test_connection_succeeds_on_existing_container(connector, container):
    connector.test_connection(_spec(container))


def test_test_connection_fails_on_missing_container(connector):
    with pytest.raises(ConnectorError):
        connector.test_connection(_spec(f"missing-{uuid.uuid4().hex[:8]}"))


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_write_then_read_round_trip(connector, container, fmt):
    spec = _spec(container)
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    key = f"data/sample.{fmt}"

    connector.write_file(spec, df, key, fmt, "overwrite")
    out = connector.read_file(spec, key, fmt)

    assert list(out.columns) == ["a", "b"]
    assert out["a"].tolist() == [1, 2, 3]
    assert out["b"].tolist() == ["x", "y", "z"]


def test_list_objects_returns_written_keys(connector, container):
    spec = _spec(container)
    df = pd.DataFrame({"a": [1]})
    connector.write_file(spec, df, "prefix/one.csv", "csv", "overwrite")
    connector.write_file(spec, df, "prefix/two.csv", "csv", "overwrite")
    connector.write_file(spec, df, "other/three.csv", "csv", "overwrite")

    assert {"prefix/one.csv", "prefix/two.csv", "other/three.csv"} <= set(connector.list_objects(spec))
    assert set(connector.list_objects(spec, prefix="prefix/")) == {"prefix/one.csv", "prefix/two.csv"}


def test_write_error_mode_rejects_existing_blob(connector, container):
    spec = _spec(container)
    df = pd.DataFrame({"a": [1]})
    connector.write_file(spec, df, "guarded.csv", "csv", "overwrite")

    with pytest.raises(ConnectorError, match="already exists"):
        connector.write_file(spec, df, "guarded.csv", "csv", "error")


def test_overwrite_mode_replaces_existing_blob(connector, container):
    spec = _spec(container)
    connector.write_file(spec, pd.DataFrame({"a": [1]}), "r.csv", "csv", "overwrite")
    connector.write_file(spec, pd.DataFrame({"a": [1, 2, 3]}), "r.csv", "csv", "overwrite")

    assert len(connector.read_file(spec, "r.csv", "csv")) == 3


def test_read_missing_blob_raises(connector, container):
    with pytest.raises(ConnectorError):
        connector.read_file(_spec(container), "nope.csv", "csv")
