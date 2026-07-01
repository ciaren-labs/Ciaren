"""Browser-origin (CSRF / DNS-rebinding) guard for mutating /api requests.

Without an API token, a malicious website could fire cross-site "simple" POSTs
(multipart uploads, bodyless POSTs) at the local API — reaching plugin install
and enable, i.e. code execution. The guard refuses unsafe /api requests whose
Origin is neither a CORS_ORIGINS entry nor a local/trusted hostname.
"""

import pytest

from app.core.config import get_settings


def _clear_token(monkeypatch) -> None:
    monkeypatch.delenv("CIAREN_API_TOKEN", raising=False)
    get_settings.cache_clear()


async def test_cross_site_post_refused(client, monkeypatch):
    """The attack vector: a POST from a foreign website's origin is refused."""
    _clear_token(monkeypatch)
    resp = await client.post("/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403, resp.text
    assert "Cross-origin" in resp.json()["detail"]


async def test_cross_site_plugin_enable_refused(client, monkeypatch):
    """The bodyless plugin-enable POST (a no-preflight 'simple' request) is guarded."""
    _clear_token(monkeypatch)
    resp = await client.post("/api/plugins/some.plugin/enable", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403, resp.text


async def test_dns_rebinding_origin_refused(client, monkeypatch):
    """Under DNS rebinding the page's origin is the attacker's hostname even though
    the socket reaches localhost — hostname trust must still refuse it."""
    _clear_token(monkeypatch)
    resp = await client.post(
        "/api/projects",
        json={"name": "x"},
        headers={"Origin": "http://rebind.evil.example:8000", "Host": "rebind.evil.example:8000"},
    )
    assert resp.status_code == 403, resp.text


async def test_null_origin_refused(client, monkeypatch):
    """'Origin: null' (sandboxed iframe / data: page) is not a trustable origin."""
    _clear_token(monkeypatch)
    resp = await client.post("/api/projects", json={"name": "x"}, headers={"Origin": "null"})
    assert resp.status_code == 403, resp.text


async def test_no_origin_header_allowed(client, monkeypatch):
    """Origin-less requests are non-browser clients (CLI/curl) — CSRF can't forge
    them, so they pass. This also keeps the rest of the test suite green."""
    _clear_token(monkeypatch)
    resp = await client.post("/api/projects", json={"name": "csrf-no-origin"})
    assert resp.status_code in (200, 201), resp.text


async def test_cors_origin_allowed(client, monkeypatch):
    """The configured dev-frontend origin stays allowed."""
    _clear_token(monkeypatch)
    origin = get_settings().CORS_ORIGINS[0]
    resp = await client.post("/api/projects", json={"name": "csrf-cors-origin"}, headers={"Origin": origin})
    assert resp.status_code in (200, 201), resp.text


@pytest.mark.parametrize("origin", ["http://localhost:9999", "http://127.0.0.1:8055", "https://localhost"])
async def test_local_hostname_origins_allowed(client, monkeypatch, origin):
    """Any local-hostname origin passes regardless of port — a malicious page is
    never served from the victim's own loopback (and the Vite proxy forwards an
    arbitrary-port localhost origin)."""
    _clear_token(monkeypatch)
    resp = await client.post("/api/projects", json={"name": f"csrf-{origin[-4:]}"}, headers={"Origin": origin})
    assert resp.status_code in (200, 201), resp.text


async def test_trusted_hosts_setting_allows_named_host(client, monkeypatch):
    _clear_token(monkeypatch)
    monkeypatch.setenv("CIAREN_TRUSTED_HOSTS", '["ciaren.lan"]')
    get_settings.cache_clear()
    resp = await client.post(
        "/api/projects", json={"name": "csrf-trusted-host"}, headers={"Origin": "http://ciaren.lan:8055"}
    )
    assert resp.status_code in (200, 201), resp.text


async def test_reads_not_guarded(client, monkeypatch):
    """GETs are left to CORS (side-effect-free); the guard only gates mutations."""
    _clear_token(monkeypatch)
    resp = await client.get("/api/projects", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 200, resp.text


async def test_guard_steps_aside_when_token_configured(client, monkeypatch):
    """With an API token, cross-site requests can't present it (custom headers need
    a preflight), so the token gate is the CSRF defense — the origin guard must not
    add false 403s for legit proxied clients."""
    monkeypatch.setenv("CIAREN_API_TOKEN", "s3cret-token")
    get_settings.cache_clear()
    resp = await client.post(
        "/api/projects",
        json={"name": "csrf-with-token"},
        headers={"Origin": "https://app.example", "X-Ciaren-Token": "s3cret-token"},
    )
    assert resp.status_code in (200, 201), resp.text
    # ... while a token-less cross-site request still fails (401 from the token gate).
    resp = await client.post("/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 401, resp.text
