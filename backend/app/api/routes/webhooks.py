# SPDX-License-Identifier: AGPL-3.0-only
"""Webhook trigger endpoint.

POST /api/flows/{id}/trigger — starts a flow run authenticated by a
pre-shared secret (CIAREN_WEBHOOK_SECRET). Designed for CI/CD pipelines,
Airflow DAGs, and other HTTP-capable orchestrators that don't need the full
REST API.

The endpoint is disabled (returns 404) when CIAREN_WEBHOOK_SECRET is not
configured so there is no accidental open trigger surface on fresh installs.
"""

import hmac
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.api.deps import ExecutionServiceDep
from app.core.config import get_settings
from app.schemas.run import FlowRunCreate, FlowRunRead

logger = logging.getLogger("app.api.routes.webhooks")

router = APIRouter()


class WebhookStatus(BaseModel):
    configured: bool


class TriggerBody(BaseModel):
    engine: str | None = None
    parameters: dict[str, Any] | None = None


@router.get("/settings/webhook", response_model=WebhookStatus, tags=["webhook"])
async def webhook_status() -> WebhookStatus:
    """Returns whether the webhook trigger is configured (not the secret itself)."""
    return WebhookStatus(configured=get_settings().WEBHOOK_SECRET is not None)


@router.post("/flows/{flow_id}/trigger", response_model=FlowRunRead, tags=["webhook"])
async def trigger_flow(
    flow_id: str,
    service: ExecutionServiceDep,
    body: TriggerBody | None = None,
    x_ciaren_secret: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> FlowRunRead:
    """Trigger a flow run via webhook secret.

    Requires ``CIAREN_WEBHOOK_SECRET`` to be configured. The caller must
    supply the same value in the ``X-Ciaren-Secret`` request header.

    Blocks until the run completes and returns the resulting ``FlowRunRead``.
    An optional ``Idempotency-Key`` header, scoped per flow, makes a retry of
    the same trigger (e.g. after the caller times out waiting for this
    blocking response) return the original run instead of starting a second
    one — without it, every request always starts a fresh run.
    """
    settings = get_settings()
    if settings.WEBHOOK_SECRET is None:
        raise HTTPException(
            status_code=404,
            detail="Webhook trigger is not configured. Set CIAREN_WEBHOOK_SECRET to enable it.",
        )
    if x_ciaren_secret is None or not hmac.compare_digest(x_ciaren_secret.encode(), settings.WEBHOOK_SECRET.encode()):
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing X-Ciaren-Secret header.",
        )

    if idempotency_key:
        existing = await service.find_by_webhook_idempotency_key(flow_id, idempotency_key)
        if existing is not None:
            return existing

    run_create = FlowRunCreate(
        engine=body.engine if body else None,
        parameters=body.parameters if body else None,
    )
    try:
        return await service.run(flow_id, run_create, trigger="webhook", webhook_idempotency_key=idempotency_key)
    except IntegrityError:
        # A concurrent duplicate delivery won the race between our pre-check
        # above and the insert inside run() — the loser's session needs a
        # rollback before it's usable again; the winner's run is what a
        # retrying caller actually wants back, not a 500.
        await service.db.rollback()
        if idempotency_key:
            existing = await service.find_by_webhook_idempotency_key(flow_id, idempotency_key)
            if existing is not None:
                return existing
        raise
