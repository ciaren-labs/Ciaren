# SPDX-License-Identifier: AGPL-3.0-only
"""Best-effort outbound failure notifications.

A scheduler whose failure mode is "retry quietly, then disable itself
silently" breaks the promise of unattended runs — the operator must be able
to hear about failures without watching the UI. When
``CIAREN_NOTIFY_WEBHOOK_URL`` is set, Ciaren POSTs a small JSON document
there whenever a run fails or a schedule auto-disables. Pointing it at a
Slack/Discord/Teams webhook bridge, ntfy topic, or any internal endpoint
covers alerting without Ciaren growing an SMTP stack.

Design constraints, in order:

- **Never harms the run path.** Delivery is fire-and-forget on a background
  task, network errors are logged (never raised), and the request has a hard
  timeout.
- **Operator-configured, not user-configured.** The URL comes from the
  environment, so it is not an SSRF vector for app users; the opt-in
  ``CONNECTOR_BLOCK_PRIVATE_HOSTS`` guard is still applied for consistency on
  hardened deployments.
- **Verifiable.** When ``CIAREN_NOTIFY_WEBHOOK_SECRET`` is set it is sent as
  ``X-Ciaren-Secret`` so the receiver can drop spoofed posts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("ciaren.notifications")

_TIMEOUT_SECONDS = 5.0

# Strong refs to in-flight delivery tasks (create_task results are otherwise
# garbage-collectable mid-flight).
_tasks: set[asyncio.Task[bool]] = set()


def webhook_configured() -> bool:
    from app.core.config import get_settings

    return bool(get_settings().NOTIFY_WEBHOOK_URL)


def _post(url: str, body: bytes, secret: str) -> None:
    headers = {"Content-Type": "application/json", "User-Agent": "ciaren-notify"}
    if secret:
        headers["X-Ciaren-Secret"] = secret
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS):  # noqa: S310 - scheme validated below
        pass


async def notify(event: str, payload: dict[str, Any]) -> bool:
    """Deliver one notification. Returns True when a POST was attempted and
    succeeded; False when unconfigured, blocked, or failed. Never raises."""
    from app.core.config import get_settings

    settings = get_settings()
    url = settings.NOTIFY_WEBHOOK_URL
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        logger.warning("NOTIFY_WEBHOOK_URL is not a valid http(s) URL; notification dropped")
        return False
    try:
        # Same opt-in private-host guard the connectors use (no-op by default).
        from app.connectors.base import ConnectorError
        from app.connectors.ssrf import guard_host

        try:
            guard_host(parsed.hostname)
        except ConnectorError as exc:
            logger.warning("Notification webhook host blocked: %s", exc)
            return False

        body = json.dumps(
            {"event": event, "timestamp": datetime.now(UTC).isoformat(), **payload},
            default=str,
        ).encode("utf-8")
        await asyncio.to_thread(_post, url, body, settings.NOTIFY_WEBHOOK_SECRET)
        return True
    except Exception as exc:  # noqa: BLE001 - alerting must never break the app
        logger.warning("Failed to deliver %s notification: %s", event, exc)
        return False


def notify_in_background(event: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget :func:`notify` — safe to call from request handlers and
    the scheduler; a cheap no-op when no webhook is configured."""
    if not webhook_configured():
        return
    task = asyncio.get_running_loop().create_task(notify(event, payload))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
