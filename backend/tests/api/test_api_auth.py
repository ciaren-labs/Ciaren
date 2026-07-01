"""API token authentication (CIAREN_API_TOKEN), finding #1.

Unset (default) keeps the unauthenticated local-first posture; set, it gates every
/api/* request while leaving health/docs, the static UI, and the webhook (its own
secret) reachable.
"""

import pytest

from app.core.config import get_settings


def _set_token(monkeypatch, token: str | None) -> None:
    if token is None:
        monkeypatch.delenv("CIAREN_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("CIAREN_API_TOKEN", token)
    get_settings.cache_clear()


async def test_no_token_configured_api_is_open(client, monkeypatch):
    """Default posture: no token set, /api works unauthenticated."""
    _set_token(monkeypatch, None)
    resp = await client.get("/api/projects")
    assert resp.status_code == 200, resp.text


async def test_token_required_when_configured(client, monkeypatch):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get("/api/projects")
    assert resp.status_code == 401, resp.text
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


async def test_bearer_token_accepted(client, monkeypatch):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get("/api/projects", headers={"Authorization": "Bearer s3cret-token"})
    assert resp.status_code == 200, resp.text


async def test_x_ciaren_token_header_accepted(client, monkeypatch):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get("/api/projects", headers={"X-Ciaren-Token": "s3cret-token"})
    assert resp.status_code == 200, resp.text


async def test_wrong_token_rejected(client, monkeypatch):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get("/api/projects", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401, resp.text


@pytest.mark.parametrize("path", ["/health", "/openapi.json"])
async def test_health_and_docs_exempt(client, monkeypatch, path):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get(path)
    assert resp.status_code == 200, resp.text


async def test_non_ascii_token_rejected_not_500(client, monkeypatch):
    """A malformed (non-ASCII) presented token must yield 401, not a TypeError
    from hmac.compare_digest (which rejects non-ASCII str input)."""
    _set_token(monkeypatch, "s3cret-token")
    # Sent as latin-1 bytes: that's what Starlette decodes raw header bytes as.
    resp = await client.get("/api/projects", headers={b"X-Ciaren-Token": "sécrét".encode("latin-1")})
    assert resp.status_code == 401, resp.text


async def test_lowercase_bearer_scheme_accepted(client, monkeypatch):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get("/api/projects", headers={"Authorization": "bearer s3cret-token"})
    assert resp.status_code == 200, resp.text


async def test_empty_bearer_falls_back_to_header(client, monkeypatch):
    """An empty Authorization value must not shadow a valid X-Ciaren-Token."""
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get(
        "/api/projects",
        headers={"Authorization": "Bearer ", "X-Ciaren-Token": "s3cret-token"},
    )
    assert resp.status_code == 200, resp.text


async def test_whitespace_only_fallback_header_rejected(client, monkeypatch):
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.get("/api/projects", headers={"X-Ciaren-Token": "   "})
    assert resp.status_code == 401, resp.text


async def test_cors_preflight_allows_token_header(client, monkeypatch):
    """A cross-origin browser client authenticating with X-Ciaren-Token needs the
    header allowed in the CORS preflight response."""
    _set_token(monkeypatch, "s3cret-token")
    resp = await client.options(
        "/api/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-ciaren-token",
        },
    )
    assert resp.status_code == 200, resp.text
    allowed = resp.headers.get("Access-Control-Allow-Headers", "").lower()
    assert "x-ciaren-token" in allowed


async def test_webhook_trigger_not_blocked_by_api_token(client, monkeypatch):
    """The webhook authenticates with its own X-Ciaren-Secret, so the API token
    must not shadow it. With no webhook secret configured the trigger returns 404
    (disabled) — crucially NOT 401."""
    _set_token(monkeypatch, "s3cret-token")
    monkeypatch.delenv("CIAREN_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    resp = await client.post("/api/flows/some-id/trigger")
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 401
