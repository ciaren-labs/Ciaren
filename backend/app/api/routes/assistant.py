# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.deps import AssistantServiceDep
from app.core.assistant_keys import read_key, source, write_key
from app.core.assistant_profiles import Provider
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.schemas.assistant import Confirmation, Credential, Turn

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
