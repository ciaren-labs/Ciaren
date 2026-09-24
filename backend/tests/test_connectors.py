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
    monkeypatch.setenv("CIAREN_TEST_PW", "s3cret")
    assert resolve_secret("CIAREN_TEST_PW") == "s3cret"


def test_resolve_secret_none_when_no_var():
    assert resolve_secret(None) is None
    assert resolve_secret("") is None


def test_resolve_secret_unset_raises(monkeypatch):
    monkeypatch.delenv("CIAREN_MISSING", raising=False)
    with pytest.raises(ValidationError):
        resolve_secret("CIAREN_MISSING")


def test_scrub_redacts_secret():
    assert "s3cret" not in scrub("error: password=s3cret failed", "s3cret")
    assert scrub("plain", None) == "plain"


def test_scrub_redacts_url_encoded_secret():
    """Connector errors embed request URLs/DSNs where the secret is
    percent-encoded; the raw-value replace alone left a decodable copy."""
    import urllib.parse

    secret = "abc+def/123=&x y"  # typical base64/HMAC material
    for encoded in (urllib.parse.quote(secret, safe=""), urllib.parse.quote_plus(secret)):
        cleaned = scrub(f"HTTP 401 from https://api?key={encoded}.", secret)
        assert encoded not in cleaned
        assert secret not in urllib.parse.unquote_plus(cleaned)


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


# -- bounded samples for dialect detection -------------------------------------


class _FakeObjectStore:
    """Stand-in for the S3/GCS/Azure SDK objects: records the requested range and
    serves that slice of ``data``."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.ranges: list[tuple[int, int]] = []

    def serve(self, start: int, end_inclusive: int) -> bytes:
        self.ranges.append((start, end_inclusive))
        return self.data[start : end_inclusive + 1]

    # S3 client
    def get_object(self, Bucket: str, Key: str, Range: str) -> dict:  # noqa: N803 - boto3 keyword names
        start, end = Range.removeprefix("bytes=").split("-")
        payload = self.serve(int(start), int(end))
        return {"Body": type("Body", (), {"read": lambda _self: payload})()}

    # GCS client/bucket/blob chain
    def bucket(self, _name: str) -> "_FakeObjectStore":
        return self

    def blob(self, _path: str) -> "_FakeObjectStore":
        return self

    def download_as_bytes(self, start: int, end: int) -> bytes:
        return self.serve(start, end)

    # Azure service/blob client chain
    def get_blob_client(self, container: str, blob: str) -> "_FakeObjectStore":
        return self

    def download_blob(self, offset: int, length: int) -> object:
        payload = self.serve(offset, offset + length - 1)
        return type("Downloader", (), {"readall": lambda _self: payload})()


@pytest.mark.parametrize(
    ("module", "factory", "cls"),
    [
        ("s3", "_client", "S3Connector"),
        ("gcs", "_client", "GCSConnector"),
        ("azure_blob", "_service_client", "AzureBlobConnector"),
    ],
)
def test_cloud_read_sample_requests_only_the_bounded_range(monkeypatch, module, factory, cls):
    import importlib

    mod = importlib.import_module(f"app.connectors.{module}")
    store = _FakeObjectStore(b"a;b\n" * 1000)
    monkeypatch.setattr(mod, factory, lambda _spec: store)

    sample = getattr(mod, cls)().read_sample(StorageSpec(provider=module, bucket="b"), "x.csv", 10)

    assert sample == b"a;b\na;b\na;"
    assert store.ranges == [(0, 9)]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        # S3 answers any range on an empty object with 416 InvalidRange.
        ({"Error": {"Code": "InvalidRange"}}, b""),
        # Any other failure — including one without a usable ``response`` — is a
        # scrubbed ConnectorError, never an AttributeError/500.
        ({"Error": {"Code": "AccessDenied"}}, ConnectorError),
        (None, ConnectorError),
        ("absent", ConnectorError),
    ],
    ids=["invalid-range", "access-denied", "response-none", "no-response"],
)
def test_s3_read_sample_errors(monkeypatch, response, expected):
    from app.connectors import s3

    class _S3Error(Exception):
        pass

    exc = _S3Error("s3 failure with secret-value")
    if response != "absent":
        exc.response = response  # type: ignore[attr-defined]

    class _Client:
        def get_object(self, **_kwargs):
            raise exc

    monkeypatch.setattr(s3, "_client", lambda _spec: _Client())
    spec = StorageSpec(provider="s3", bucket="b", secret="secret-value")
    if expected is ConnectorError:
        with pytest.raises(ConnectorError) as info:
            s3.S3Connector().read_sample(spec, "x.csv", 10)
        assert "secret-value" not in str(info.value)
    else:
        assert s3.S3Connector().read_sample(spec, "x.csv", 10) == expected


def test_storage_connector_protocol_declares_every_connector_method():
    """Every built-in storage connector satisfies the full protocol, writes included."""
    from app.connectors.azure_blob import AzureBlobConnector
    from app.connectors.gcs import GCSConnector
    from app.connectors.s3 import S3Connector
    from app.connectors.storage_base import StorageConnector

    for method in ("test_connection", "list_objects", "read_file", "read_sample", "write_file"):
        assert callable(getattr(StorageConnector, method, None)), method
    for cls in (LocalStorageConnector, S3Connector, GCSConnector, AzureBlobConnector):
        assert isinstance(cls(), StorageConnector), cls.__name__


def test_local_read_sample_is_bounded_and_confined(tmp_path):
    (tmp_path / "big.csv").write_bytes(b"a;b\n" * 1000)
    conn = LocalStorageConnector()
    assert conn.read_sample(_local_spec(tmp_path), "big.csv", 10) == b"a;b\na;b\na;"
    with pytest.raises(ConnectorError, match="escapes the storage root"):
        conn.read_sample(_local_spec(tmp_path / "sub"), "../big.csv", 10)


# -- local storage root confinement (CIAREN_STORAGE_ALLOWED_ROOTS) -------


def test_local_storage_root_unrestricted_by_default(tmp_path, monkeypatch):
    """With no allow-list configured, any folder is a valid root (historical
    behavior — the connector's whole purpose is reading local folders)."""
    from app.core.config import get_settings

    monkeypatch.delenv("CIAREN_STORAGE_ALLOWED_ROOTS", raising=False)
    get_settings.cache_clear()
    try:
        outside = tmp_path / "anywhere"
        outside.mkdir()
        spec = StorageSpec(provider="local", bucket=str(outside))
        LocalStorageConnector().test_connection(spec)  # no raise
    finally:
        get_settings.cache_clear()


def test_local_storage_root_inside_allowlist_allowed(tmp_path, monkeypatch):
    from app.core.config import get_settings

    base = tmp_path / "allowed"
    base.mkdir()
    monkeypatch.setenv("CIAREN_STORAGE_ALLOWED_ROOTS", f'["{base.as_posix()}"]')
    get_settings.cache_clear()
    try:
        spec = StorageSpec(provider="local", bucket=str(base / "sub"))
        LocalStorageConnector().test_connection(spec)  # creates + probes, no raise
    finally:
        get_settings.cache_clear()


def test_local_storage_root_outside_allowlist_rejected(tmp_path, monkeypatch):
    from app.core.config import get_settings

    base = tmp_path / "allowed"
    base.mkdir()
    monkeypatch.setenv("CIAREN_STORAGE_ALLOWED_ROOTS", f'["{base.as_posix()}"]')
    get_settings.cache_clear()
    try:
        spec = StorageSpec(provider="local", bucket=str(tmp_path / "elsewhere"))
        with pytest.raises(ConnectorError, match="outside the allowed roots"):
            LocalStorageConnector().test_connection(spec)
    finally:
        get_settings.cache_clear()


# -- file-based SQL databases share the same confinement ---------------------


def test_sqlite_outside_allowlist_rejected(tmp_path, monkeypatch):
    """With allowed roots configured, a sqlite connection must not reach files
    outside them — otherwise it bypasses the Local Storage confinement."""
    from app.connectors.base import ConnectionSpec
    from app.connectors.sql import SqlConnector
    from app.core.config import get_settings

    base = tmp_path / "allowed"
    base.mkdir()
    monkeypatch.setenv("CIAREN_STORAGE_ALLOWED_ROOTS", f'["{base.as_posix()}"]')
    get_settings.cache_clear()
    try:
        spec = ConnectionSpec(provider="sqlite", database=str(tmp_path / "elsewhere" / "x.db"))
        with pytest.raises(ConnectorError, match="outside the allowed roots"):
            SqlConnector().test_connection(spec)
    finally:
        get_settings.cache_clear()


def test_sqlite_inside_allowlist_allowed(tmp_path, monkeypatch):
    from app.connectors.base import ConnectionSpec
    from app.connectors.sql import SqlConnector
    from app.core.config import get_settings

    base = tmp_path / "allowed"
    base.mkdir()
    monkeypatch.setenv("CIAREN_STORAGE_ALLOWED_ROOTS", f'["{base.as_posix()}"]')
    get_settings.cache_clear()
    try:
        spec = ConnectionSpec(provider="sqlite", database=str(base / "x.db"))
        SqlConnector().test_connection(spec)  # no raise
    finally:
        get_settings.cache_clear()


def test_sqlite_unrestricted_by_default(tmp_path, monkeypatch):
    from app.connectors.base import ConnectionSpec
    from app.connectors.sql import SqlConnector
    from app.core.config import get_settings

    monkeypatch.delenv("CIAREN_STORAGE_ALLOWED_ROOTS", raising=False)
    get_settings.cache_clear()
    try:
        spec = ConnectionSpec(provider="sqlite", database=str(tmp_path / "anywhere.db"))
        SqlConnector().test_connection(spec)  # no raise
    finally:
        get_settings.cache_clear()


def test_sqlite_memory_not_confined(monkeypatch, tmp_path):
    """An in-memory database touches no files, so confinement must not block it."""
    from app.connectors.base import ConnectionSpec
    from app.connectors.sql import SqlConnector
    from app.core.config import get_settings

    base = tmp_path / "allowed"
    base.mkdir()
    monkeypatch.setenv("CIAREN_STORAGE_ALLOWED_ROOTS", f'["{base.as_posix()}"]')
    get_settings.cache_clear()
    try:
        SqlConnector().test_connection(ConnectionSpec(provider="sqlite", database=":memory:"))  # no raise
    finally:
        get_settings.cache_clear()
