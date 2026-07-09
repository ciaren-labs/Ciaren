# SPDX-License-Identifier: AGPL-3.0-only
"""HTTP middleware wiring (CORS, gzip, security headers).

Register on the app with :func:`register_middleware`. Kept out of ``app.main`` so
the middleware stack is described in one readable place.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware


def register_middleware(app: FastAPI, settings: object) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=getattr(settings, "CORS_ORIGINS", []),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Ciaren-Secret", "X-Ciaren-Token"],
    )
    # Compress responses (the served JS/CSS bundle and large JSON payloads).
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
