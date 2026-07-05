# SPDX-License-Identifier: AGPL-3.0-only
"""Heavy service work must not stall the event loop.

Upload parsing/profiling (up to MAX_UPLOAD_SIZE_MB of pandas work) runs in a
worker thread via ``asyncio.to_thread``. This regression test simulates a slow
parse and asserts that an unrelated request (``/health``) still answers while
the upload is in flight — if someone moves the parse back onto the event loop,
the health check is forced to wait out the sleep and the timing assertion
fails.
"""

import asyncio
import time
from typing import Any

import pandas as pd
from httpx import AsyncClient

# The blocking sleep is generous vs. the health-latency bound so scheduler
# jitter on a loaded CI box can't flake the assertion.
_SLOW_PARSE_SECONDS = 1.5
_HEALTH_LATENCY_BOUND = 0.8
# Long enough that the upload has certainly reached its parse before health
# wakes up and issues its request; short enough to keep margin to the bound.
_HEALTH_PRE_SLEEP = 0.25


def _slow_parse_and_describe(
    content: bytes, source_type: str, filename: str, options: dict[str, Any] | None = None
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    time.sleep(_SLOW_PARSE_SECONDS)  # blocking on purpose: must land in a worker thread
    df = pd.DataFrame({"a": [1]})
    return df, [{"name": "a", "type": "integer"}], [{"a": 1}], []


async def test_health_answers_while_upload_parses(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr("app.services.dataset_service._parse_and_describe", _slow_parse_and_describe)

    async def upload() -> int:
        r = await client.post(
            "/api/datasets/upload",
            files={"file": ("slow.csv", b"a\n1\n", "text/csv")},
        )
        return r.status_code

    async def health_latency() -> float:
        # The clock starts BEFORE yielding to the upload: if the parse blocks
        # the loop, this coroutine can't resume from its sleep until the parse
        # finishes, and the measured latency absorbs the whole stall. (A timer
        # started after the stall would measure a fast request and miss it.)
        started = time.perf_counter()
        await asyncio.sleep(_HEALTH_PRE_SLEEP)
        r = await client.get("/health")
        assert r.status_code == 200
        return time.perf_counter() - started

    # health_latency FIRST: tasks start in order, and the upload doesn't yield
    # to the loop before reaching the parse — if it ran first, a blocking parse
    # would finish before health's clock even started and go unnoticed.
    latency, upload_status = await asyncio.gather(health_latency(), upload())
    assert upload_status == 201
    assert latency < _HEALTH_LATENCY_BOUND, (
        f"/health took {latency:.2f}s while an upload was parsing — the parse is blocking the event loop"
    )
