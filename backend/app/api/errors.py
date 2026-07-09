# SPDX-License-Identifier: AGPL-3.0-only
"""Domain-exception → HTTP-response mapping.

Keeps the translation from internal exception types to status codes in one place,
out of ``app.main``. Register on the app with :func:`register_exception_handlers`.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConflictError,
    DatasetParseError,
    FileTooLargeError,
    MLNotEnabledError,
    NotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedFileTypeError)
    async def unsupported_type_handler(request: Request, exc: UnsupportedFileTypeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(FileTooLargeError)
    async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(DatasetParseError)
    async def parse_error_handler(request: Request, exc: DatasetParseError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Redact the echoed request input from validation errors. FastAPI's default
        # 422 body includes the offending `input` (and `ctx`) verbatim — for a body
        # carrying a plaintext secret (e.g. POST /api/connections/keyring) that would
        # leak the secret into a response. Keep loc/msg/type so clients still see
        # what failed, but never the submitted value.
        safe = [
            {"loc": list(err.get("loc", [])), "msg": str(err.get("msg", "")), "type": str(err.get("type", ""))}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": safe})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(MLNotEnabledError)
    async def ml_not_enabled_handler(request: Request, exc: MLNotEnabledError) -> JSONResponse:
        return JSONResponse(status_code=501, content={"detail": str(exc)})
