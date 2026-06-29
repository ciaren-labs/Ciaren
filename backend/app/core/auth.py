"""Optional bearer-token authentication for the REST API.

FlowFrame is local-first and unauthenticated by default (safe bound to
``127.0.0.1``). Setting ``FLOWFRAME_API_TOKEN`` turns on a single shared-secret
gate so a network-exposed instance (e.g. the Docker image, which binds
``0.0.0.0``) isn't an open door to flow execution / plugin install — both of which
reach arbitrary code execution. See SECURITY-AUDIT.md (finding #1).

The check is wired as a global FastAPI dependency (``create_app``), so a rejection
is a normal ``HTTPException`` that still flows through the CORS middleware. The
token may be presented as ``Authorization: Bearer <token>`` or in the
``X-FlowFrame-Token`` header, and is compared in constant time.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

from app.core.config import get_settings

#: Header carrying the token, as an alternative to ``Authorization: Bearer``.
API_TOKEN_HEADER = "X-FlowFrame-Token"

#: Non-``/api`` paths plus these exact routes are always reachable without a token:
#: health/readiness probes and the API schema/docs (needed to load the UI and to
#: let orchestrators health-check the container).
_EXEMPT_PATHS = frozenset(
    {
        "/health",
        "/ready",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
)


def _is_exempt(path: str, method: str) -> bool:
    """Whether a request bypasses the API-token check.

    Exempt: CORS preflight (carries no auth header), the static web UI / SPA shell
    (everything outside ``/api/``), the health/docs endpoints, and the webhook
    surface — the trigger authenticates with its own ``X-FlowFrame-Secret`` and the
    status endpoint reveals only a boolean, so an orchestrator using just the
    webhook secret keeps working.
    """
    if method == "OPTIONS":
        return True
    if not path.startswith("/api/"):
        return True
    if path in _EXEMPT_PATHS:
        return True
    if path == "/api/settings/webhook":
        return True
    if path.startswith("/api/flows/") and path.endswith("/trigger"):
        return True
    return False


def _presented_token(request: Request) -> str | None:
    """Extract the token from the Authorization bearer header or the fallback
    header. Returns None when neither is present."""
    auth = request.headers.get("Authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    fallback = request.headers.get(API_TOKEN_HEADER)
    return fallback.strip() if fallback and fallback.strip() else None


async def verify_api_token(request: Request) -> None:
    """Global dependency: enforce the API token when one is configured.

    No-op when ``API_TOKEN`` is unset (the default local-first posture) or the
    request is exempt. Raises 401 otherwise.
    """
    token = get_settings().API_TOKEN
    if not token:
        return
    if _is_exempt(request.url.path, request.method):
        return
    presented = _presented_token(request)
    if presented is None or not hmac.compare_digest(presented, token):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
