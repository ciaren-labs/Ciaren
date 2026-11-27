# SPDX-License-Identifier: AGPL-3.0-only
"""Bound assistant request bytes before JSON parsing, including chunked uploads."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class AssistantBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/assistant/") or scope["method"] not in {"PUT", "POST"}:
            await self.app(scope, receive, send)
            return
        size = 8192 if path.startswith("/api/assistant/credentials/") else 112000
        body = bytearray()
        while True:
            part = await receive()
            if part["type"] == "http.disconnect":
                return
            chunk = part.get("body", b"")
            if len(body) + len(chunk) > size:
                await JSONResponse({"detail": "Assistant request too large."}, status_code=413)(scope, receive, send)
                return
            body.extend(chunk)
            if not part.get("more_body"):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
