"""Unit tests for the data-source connector layer and secret resolution."""

import pandas as pd
import pytest

from app.connectors import (
    ConnectionSpec,
    ConnectorError,
    get_connector,
    get_provider,
    list_providers,
    validate_identifier,
)
from app.connectors.local_storage import LocalStorageConnector
from app.connectors.storage_base import StorageSpec
from app.core.exceptions import ValidationError
from app.core.secrets import resolve_secret, scrub


def _sqlite_spec(tmp_path) -> ConnectionSpec:
    return ConnectionSpec(provider="sqlite", database=str(tmp_path / "test.db"))


def _sql_connector():
    return get_connector(get_provider("sqlite"))


def test_sql_connector_roundtrip(tmp_path):
    spec = _sqlite_spec(tmp_path)
    conn = _sql_connector()
    conn.test_connection(spec)
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    conn.write_table(spec, df, "people", None, "replace")

    tables = [t.name for t in conn.list_tables(spec)]
    assert "people" in tables

    df = conn.read_table(spec, "people", None, None)
    assert len(df) == 2
    assert list(df.columns) == ["a", "b"]

    q = conn.read_query(spec, "SELECT COUNT(*) AS n FROM people")
    assert int(q.iloc[0, 0]) == 2


def test_sql_write_modes(tmp_path):
    spec = _sqlite_spec(tmp_path)
    conn = _sql_connector()
    df = pd.DataFrame({"a": [1]})
    conn.write_table(spec, df, "t", None, "replace")
    conn.write_table(spec, df, "t", None, "append")
    assert len(conn.read_table(spec, "t", None, None)) == 2
    with pytest.raises(ConnectorError):
        conn.write_table(spec, df, "t", None, "fail")


def test_validate_identifier_rejects_injection():
    validate_identifier("good_name")
    for bad in ["bad name", "drop;table", "a-b", "1abc", ""]:
        with pytest.raises(ConnectorError):
            validate_identifier(bad)


def test_read_table_rejects_bad_identifier(tmp_path):
    spec = _sqlite_spec(tmp_path)
    with pytest.raises(ConnectorError):
        _sql_connector().read_table(spec, "bad; DROP", None, None)


def test_providers_report_availability():
    providers = {p["name"]: p for p in list_providers()}
    assert providers["sqlite"]["available"] is True  # stdlib, always available
    assert {"postgresql", "mysql", "mongodb"} <= set(providers)
    # Each provider advertises whether it supports custom queries.
    assert providers["mongodb"]["supports_query"] is False


def test_mongo_rejects_custom_query():
    conn = get_connector(get_provider("mongodb"))
    spec = ConnectionSpec(provider="mongodb", host="localhost", database="d")
    with pytest.raises(ConnectorError):
        conn.read_query(spec, "anything")


# -- secrets ------------------------------------------------------------


def test_resolve_secret_from_env(monkeypatch):
    monkeypatch.setenv("FF_TEST_PW", "s3cret")
    assert resolve_secret("FF_TEST_PW") == "s3cret"


def test_resolve_secret_none_when_no_var():
    assert resolve_secret(None) is None
    assert resolve_secret("") is None


def test_resolve_secret_unset_raises(monkeypatch):
    monkeypatch.delenv("FF_MISSING", raising=False)
    with pytest.raises(ValidationError):
        resolve_secret("FF_MISSING")


def test_scrub_redacts_secret():
    assert "s3cret" not in scrub("error: password=s3cret failed", "s3cret")
    assert scrub("plain", None) == "plain"


# -- local storage path-traversal security ---------------------------------


def _local_spec(tmp_path) -> StorageSpec:
    return StorageSpec(provider="local", bucket=str(tmp_path))


def test_local_storage_read_within_root_succeeds(tmp_path):
    """Reading a legitimate file within the root directory works."""
    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    conn = LocalStorageConnector()
    df = conn.read_file(_local_spec(tmp_path), "data.csv", "csv")
    assert list(df.columns) == ["a", "b"]


def test_local_storage_read_traversal_rejected(tmp_path):
    """Paths that escape the root via '..' are blocked."""
    conn = LocalStorageConnector()
    # Create a sentinel file one level above tmp_path to prove traversal would work.
    parent = tmp_path.parent
    sentinel = parent / "secret.csv"
    sentinel.write_text("secret,data\n1,2\n")
    try:
        with pytest.raises(ConnectorError, match="escapes the storage root"):
            conn.read_file(_local_spec(tmp_path), "../secret.csv", "csv")
    finally:
        sentinel.unlink(missing_ok=True)


def test_local_storage_write_traversal_rejected(tmp_path):
    """Write paths that escape the root are blocked before any file is created."""
    import pandas as pd

    conn = LocalStorageConnector()
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(ConnectorError, match="escapes the storage root"):
        conn.write_file(_local_spec(tmp_path), df, "../../injected.csv", "csv", "overwrite")


def test_local_storage_absolute_path_rejected(tmp_path):
    """An absolute path that doesn't start within root is blocked."""
    import sys

    conn = LocalStorageConnector()
    # Use a safe non-existent absolute path outside tmp_path.
    if sys.platform == "win32":
        evil_path = "C:/Windows/System32/drivers/etc/hosts"
    else:
        evil_path = "/etc/hosts"
    with pytest.raises(ConnectorError, match="escapes the storage root"):
        conn.read_file(_local_spec(tmp_path), evil_path, "csv")
