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
) -> FlowRunRead:
    """Trigger a flow run via webhook secret.

    Requires ``CIAREN_WEBHOOK_SECRET`` to be configured. The caller must
    supply the same value in the ``X-Ciaren-Secret`` request header.

    Blocks until the run completes and returns the resulting ``FlowRunRead``.
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

    run_create = FlowRunCreate(
        engine=body.engine if body else None,
        parameters=body.parameters if body else None,
    )
    return await service.run(flow_id, run_create, trigger="webhook")
