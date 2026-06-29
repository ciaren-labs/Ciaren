"""SSRF guard for connector hosts/endpoints (finding #4).

Off by default (local-first connects to localhost); when
FLOWFRAME_CONNECTOR_BLOCK_PRIVATE_HOSTS is on, internal addresses are refused.
"""

import pytest

from app.connectors.base import ConnectionSpec, ConnectorError
from app.connectors.sql import SqlConnector
from app.connectors.ssrf import guard_endpoint, guard_host
from app.core.config import get_settings


def _set_guard(monkeypatch, enabled: bool) -> None:
    monkeypatch.setenv("FLOWFRAME_CONNECTOR_BLOCK_PRIVATE_HOSTS", "true" if enabled else "false")
    get_settings.cache_clear()


@pytest.fixture
def guard_on(monkeypatch):
    _set_guard(monkeypatch, True)
    yield
    get_settings.cache_clear()


# -- disabled by default ----------------------------------------------------


def test_guard_is_noop_when_disabled(monkeypatch):
    _set_guard(monkeypatch, False)
    try:
        guard_host("169.254.169.254")  # would be blocked if enabled
        guard_host("10.0.0.5")
        guard_endpoint("http://localhost:9000")
    finally:
        get_settings.cache_clear()


# -- blocked addresses when enabled -----------------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "localhost",
        "169.254.169.254",  # cloud metadata endpoint
        "10.1.2.3",
        "192.168.1.10",
        "172.16.0.1",
        "0.0.0.0",
        "[::1]",
    ],
)
def test_internal_hosts_blocked(guard_on, host):
    with pytest.raises(ConnectorError, match="private/internal address"):
        guard_host(host)


def test_internal_endpoint_blocked(guard_on):
    with pytest.raises(ConnectorError, match="private/internal address"):
        guard_endpoint("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(ConnectorError, match="private/internal address"):
        guard_endpoint("https://10.0.0.1:9000")  # private endpoint host
    with pytest.raises(ConnectorError, match="private/internal address"):
        guard_endpoint("http://127.0.0.1:9000/bucket")  # loopback endpoint


# -- public addresses allowed ------------------------------------------------


def test_public_ip_allowed(guard_on):
    guard_host("8.8.8.8")  # no raise


def test_unresolvable_host_is_not_blocked(guard_on):
    # The guard can't resolve it; let the driver surface the real DNS error rather
    # than masking it as a security block.
    guard_host("this-name-should-not-resolve.invalid")  # no raise


def test_empty_host_is_noop(guard_on):
    guard_host(None)
    guard_host("")
    guard_endpoint(None)


# -- wired into a connector --------------------------------------------------


def test_sql_connector_refuses_internal_host_when_enabled(guard_on):
    conn = SqlConnector()
    spec = ConnectionSpec(provider="postgresql", host="127.0.0.1", port=5432, database="d", username="u")
    with pytest.raises(ConnectorError, match="private/internal address"):
        conn.test_connection(spec)


def test_sqlite_has_no_host_so_guard_is_noop(guard_on, tmp_path):
    conn = SqlConnector()
    spec = ConnectionSpec(provider="sqlite", database=str(tmp_path / "x.db"))
    conn.test_connection(spec)  # file-based, no host — must not raise on the guard
