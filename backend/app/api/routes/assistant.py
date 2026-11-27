# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, Response

from app.api.deps import AssistantServiceDep
from app.core.assistant_keys import read_key, source, write_key
from app.core.assistant_profiles import Provider
from app.core.config import get_settings
from app.core.exceptions import ConflictError, ValidationError
from app.schemas.assistant import Confirmation, Credential, RevertPreview, Turn
from app.services import assistant_activity as activity

router = APIRouter()
_active: dict[tuple[str, UUID], asyncio.Event] = {}


@router.delete("/flows/{flow_id}/turns/{request_id}", status_code=204)
async def cancel(flow_id: str, request_id: UUID) -> Response:
    signal = _active.get((flow_id, request_id))
    if signal:
        signal.set()
    return Response(status_code=204)


@router.get("/status")
async def status() -> dict[str, Any]:
    cfg = get_settings()
    provider = cfg.ASSISTANT_PROVIDER
    if not cfg.ASSISTANT_ENABLED or provider == "off":
        return {"provider": "off"}
    try:
        state = "configured" if await asyncio.to_thread(read_key, provider) else "missing"
    except ValidationError:
        state = "unavailable"
    return {
        "provider": provider,
        "source": source(provider),
        "state": state,
        "model": getattr(cfg, f"ASSISTANT_{provider.upper()}_MODEL"),
    }


def _selected(provider: Provider) -> None:
    settings = get_settings()
    if not settings.ASSISTANT_ENABLED or provider != settings.ASSISTANT_PROVIDER:
        raise ValidationError("Choose this provider in Settings first.")


@router.put("/credentials/{provider}", status_code=204)
async def rotate(provider: Provider, body: Credential) -> Response:
    _selected(provider)
    await asyncio.to_thread(write_key, provider, body.key)
    return Response(status_code=204)


@router.delete("/credentials/{provider}", status_code=204)
async def revoke(provider: Provider) -> Response:
    _selected(provider)
    await asyncio.to_thread(write_key, provider, None)
    return Response(status_code=204)


@router.post("/flows/{flow_id}/turn")
async def turn(flow_id: str, body: Turn, service: AssistantServiceDep, request: Request) -> dict[str, Any]:
    identity = (flow_id, body.request_id)
    if identity in _active or len(_active) >= 8:
        raise ValidationError("Another assistant turn is active. Try again shortly.")
    signal = asyncio.Event()
    _active[identity] = signal
    task = asyncio.create_task(service.turn(flow_id, body))
    cancel_request = asyncio.create_task(signal.wait())

    async def watch_disconnect() -> None:
        while (await request.receive())["type"] != "http.disconnect":
            pass

    disconnect = asyncio.create_task(watch_disconnect())
    tasks = {task, cancel_request, disconnect}
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return await task
        raise ValidationError("Assistant request cancelled.")
    finally:
        _active.pop(identity, None)
        for pending in tasks:
            pending.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@router.post("/flows/{flow_id}/apply")
async def apply(flow_id: str, body: Confirmation, service: AssistantServiceDep) -> Any:
    return await service.apply(flow_id, body.proposal)


# Short-lived receipts tie human confirmation to the exact revision and activity previewed.
# Only references are retained. Restarting the process invalidates outstanding previews.
_reverts: dict[str, tuple[str, str, datetime]] = {}


@router.get("/flows/{flow_id}/activity")
async def history(flow_id: str, service: AssistantServiceDep, response: Response, cursor: str | None = None) -> Any:
    response.headers["Cache-Control"] = "no-store"
    return await activity.timeline(service.db, flow_id, cursor)


@router.post("/flows/{flow_id}/activity/{event_id}/preview")
async def preview_revert(flow_id: str, event_id: str, body: RevertPreview, service: AssistantServiceDep) -> Any:
    flow, event = await activity.load_target(service.db, flow_id, event_id, body.revision)
    await activity.inverse_graph(service.db, event, flow.graph_json)
    if len(_reverts) >= 64:
        raise ValidationError("Too many open reversal previews. Try again shortly.")
    token = uuid4().hex
    _reverts[token] = (flow_id, event_id, body.revision)
    asyncio.get_running_loop().call_later(180, _reverts.pop, token, None)
    return {"confirmation": token, "details": activity.reversed_details(event.details)}


@router.post("/flows/{flow_id}/activity/{event_id}/revert")
async def revert(flow_id: str, event_id: str, body: Confirmation, service: AssistantServiceDep) -> Any:
    ref = _reverts.get(body.proposal)
    if not ref or ref[:2] != (flow_id, event_id):
        raise ConflictError("Preview this reversal again before confirming.")
    result = await activity.save_reversal(service.db, flow_id, event_id, ref[2])
    _reverts.pop(body.proposal, None)
    return result
