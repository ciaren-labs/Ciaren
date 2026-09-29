"""HTTPS input connector example: parsing, URL safety, redirects, and limits."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "examples" / "plugins" / "https-input-connector-plugin"


class _Response:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        chunk_size: int | None = None,
    ) -> None:
        self._body = BytesIO(body)
        self.status = status
        self.headers = headers or {}
        self._chunk_size = chunk_size

    def getcode(self) -> int:
        return self.status

    def read(self, size: int = -1) -> bytes:
        if self._chunk_size is not None and size > self._chunk_size:
            size = self._chunk_size
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.requests: list[Any] = []
        self.timeouts: list[int] = []

    def open(self, request, timeout):  # noqa: ANN001, ANN201
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


@pytest.fixture(scope="module")
def plugin_module():
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.append(str(PLUGIN_DIR))
    from ciaren_https_input import plugin

    return plugin


@pytest.fixture
def runtime(plugin_module, monkeypatch):
    monkeypatch.setattr(
        plugin_module.socket,
        "getaddrinfo",
        lambda host, port, type=0: [(None, None, None, "", ("93.184.216.34", port))],
    )
    return plugin_module._HttpsInputRuntime()


def _mock_response(plugin_module, monkeypatch, response: _Response) -> _Opener:
    opener = _Opener(response)
    monkeypatch.setattr(plugin_module.urllib.request, "build_opener", lambda *handlers: opener)
    return opener


def test_reads_csv_success(plugin_module, runtime, monkeypatch):
    opener = _mock_response(plugin_module, monkeypatch, _Response(b"name,age\nAda,37\nBo,41\n"))

    df = runtime.read({"options": {"url": "https://data.example/users.csv", "format": "csv"}}, {})

    assert list(df["name"]) == ["Ada", "Bo"]
    assert opener.timeouts == [plugin_module.DEFAULT_TIMEOUT_SECONDS]


def test_reads_json_success(plugin_module, runtime, monkeypatch):
    _mock_response(plugin_module, monkeypatch, _Response(b'[{"name":"Ada"},{"name":"Bo"}]'))

    df = runtime.read({"options": {"url": "https://data.example/users.json", "format": "json"}}, {})

    assert list(df["name"]) == ["Ada", "Bo"]


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("http://data.example/users.csv", ["93.184.216.34"]),
        ("https://localhost/users.csv", ["127.0.0.1"]),
        ("https://data.example/users.csv", ["10.1.2.3"]),
        ("https://metadata.example/latest", ["169.254.169.254"]),
        ("https://reserved.example/users.csv", ["240.0.0.1"]),
        ("https://multicast.example/users.csv", ["224.0.0.1"]),
        ("https://unspecified.example/users.csv", ["0.0.0.0"]),
    ],
)
def test_rejects_unsafe_urls(plugin_module, runtime, monkeypatch, url, addresses):
    monkeypatch.setattr(
        plugin_module.socket,
        "getaddrinfo",
        lambda host, port, type=0: [(None, None, None, "", (address, port)) for address in addresses],
    )

    with pytest.raises(plugin_module.UnsafeUrlError):
        runtime.read({"options": {"url": url, "format": "csv"}}, {})


def test_rejects_redirect_and_validates_location(plugin_module, runtime, monkeypatch):
    def _resolve(host, port, type=0):
        address = "10.0.0.5" if host == "internal.example" else "93.184.216.34"
        return [(None, None, None, "", (address, port))]

    monkeypatch.setattr(plugin_module.socket, "getaddrinfo", _resolve)
    _mock_response(
        plugin_module,
        monkeypatch,
        _Response(status=302, headers={"Location": "https://internal.example/secret"}),
    )

    with pytest.raises(plugin_module.UnsafeUrlError, match="disallowed address"):
        runtime.read({"options": {"url": "https://data.example/users.csv", "format": "csv"}}, {})


def test_rejects_oversized_response(plugin_module, runtime, monkeypatch):
    _mock_response(plugin_module, monkeypatch, _Response(b"abcdef", chunk_size=2))

    with pytest.raises(plugin_module.ResponseTooLargeError):
        runtime.read({"options": {"url": "https://data.example/users.csv", "format": "csv", "max_bytes": 5}}, {})
