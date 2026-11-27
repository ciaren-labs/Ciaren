"""Exercise real aiohttp OpenTelemetry instrumentation against a loopback provider double.

From backend, run with the dev environment plus opentelemetry-instrumentation-aiohttp-client.
"""

import asyncio
import json
import os
from dataclasses import replace
from unittest.mock import patch

import aiohttp
from aiohttp import web
from opentelemetry import trace
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr

from app.core.assistant_profiles import PROFILES
from app.core.config import get_settings
from app.services import assistant_provider


async def main():
    sentinel = "synthetic-instrumentation-fixture"
    exporter = InMemorySpanExporter()
    tracing = TracerProvider(sampler=ALWAYS_ON)
    tracing.add_span_processor(SimpleSpanProcessor(exporter))
    os.environ["OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_CLIENT_REQUEST"] = ".*"
    instrumentor = AioHttpClientInstrumentor()
    instrumentor.instrument(tracer_provider=tracing)

    async def provider(request):
        assert request.headers["Authorization"] == "Bearer " + sentinel
        assert "traceparent" not in request.headers
        return web.json_response(
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "{}"}],
                    }
                ],
            }
        )

    async def control(request):
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_post("/responses", provider)
    app.router.add_get("/control", control)
    async with aiohttp.test_utils.TestServer(app) as server:
        async with aiohttp.ClientSession() as client:
            async with client.get(server.make_url("/control")) as response:
                assert response.status == 200
        assert len(exporter.get_finished_spans()) == 1, (
            "positive control must produce an HTTP client span"
        )
        cfg = get_settings()
        spec = replace(PROFILES["openai"], url=str(server.make_url("/responses")))
        with (
            patch.dict(PROFILES, openai=spec),
            patch.object(cfg, "ASSISTANT_PROVIDER", "openai"),
            patch.object(
                assistant_provider, "read_key", return_value=SecretStr(sentinel)
            ),
        ):
            with trace.use_span(
                tracing.get_tracer(__name__).start_span("editor turn"), end_on_exit=True
            ):
                assert (
                    await assistant_provider.complete(
                        "openai", "Return JSON", {"question": "limit rows"}
                    )
                    == {}
                )
        spans = exporter.get_finished_spans()
        assert len(spans) == 2 and spans[-1].name == "editor turn"
        assert sentinel not in json.dumps([span.to_json() for span in spans])
    instrumentor.uninstrument()
    print(
        "Verified positive control, suppressed provider span and absent trace propagation."
    )


if __name__ == "__main__":
    import aiohttp.test_utils

    asyncio.run(main())
