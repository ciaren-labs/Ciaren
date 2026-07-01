# SPDX-License-Identifier: AGPL-3.0-only
"""Browser-origin guard for state-changing API requests (CSRF / DNS rebinding).

Ciaren's default posture is local-first and unauthenticated: the API is safe
because it is only reachable from the user's own machine. But the user's own
*browser* is also on that machine — and any website it visits can fire
cross-site POSTs at ``http://127.0.0.1:<port>``. CORS does not help: it gates
*reading* responses, not causing side effects, and several sensitive endpoints
are reachable with "simple" requests that never trigger a preflight (multipart
uploads, bodyless POSTs). Left open, a malicious page could install and enable
a plugin — arbitrary code execution.

The guard: for every unsafe-method request to ``/api/*``, if the browser
attached an ``Origin`` header it must be one we trust —

- an origin listed in ``CORS_ORIGINS`` (the dev frontend), or
- an origin whose hostname is local (``localhost`` / ``127.0.0.1`` / ``::1``)
  or listed in ``TRUSTED_HOSTS``.

Trust is anchored to the *hostname*, not a same-origin match with the request's
Host, for two reasons: it is what actually distinguishes an attack (a malicious
page is served from the attacker's hostname — also true under DNS rebinding,
where page and request share ``evil.example``), and the Vite dev proxy rewrites
the Host header so a strict same-origin comparison would reject the legitimate
dev UI.

Requests without an ``Origin`` header pass — browsers always attach one to
cross-site unsafe requests, so an Origin-less request is a non-browser client
(CLI, curl, server-to-server) that plain CSRF cannot forge.

When ``API_TOKEN`` is set the guard steps aside: a cross-site request cannot
present the token (custom headers require a CORS preflight), so the token
already defeats CSRF — and skipping avoids false 403s behind TLS-terminating
proxies where the visible scheme/host differ.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.core.config import get_settings

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Hostnames the backend expects to serve the UI from in the local-first setup.
_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def _origin_is_trusted(origin: str) -> bool:
    settings = get_settings()
    if origin in settings.CORS_ORIGINS:
        return True
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    return hostname in _LOCAL_HOSTNAMES or hostname in {h.lower() for h in settings.TRUSTED_HOSTS}


async def verify_browser_origin(request: Request) -> None:
    """Global dependency: reject cross-site browser requests to mutating
    ``/api/*`` endpoints. No-op for safe methods, non-``/api`` paths,
    Origin-less (non-browser) clients, and token-protected deployments.
    """
    if request.method not in _UNSAFE_METHODS:
        return
    if not request.url.path.startswith("/api/"):
        return
    if get_settings().API_TOKEN:
        return  # the token gate already defeats cross-site requests
    origin = request.headers.get("Origin")
    if origin is None:
        return
    if not _origin_is_trusted(origin):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Cross-origin request from {origin!r} was refused. If this origin should "
                "be allowed, add it to CIAREN_CORS_ORIGINS; if you access Ciaren by a "
                "non-local hostname, add that host to CIAREN_TRUSTED_HOSTS or set "
                "CIAREN_API_TOKEN."
            ),
        )
