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
