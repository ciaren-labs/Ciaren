"""flowframe-client — thin HTTP client for the FlowFrame visual data and ML workflow server.

Sync usage::

    from flowframe_client import FlowFrame

    ff = FlowFrame("http://localhost:8055", webhook_secret="my-secret")
    run = ff.trigger("flow-id")
    print(run["status"])

Async usage::

    from flowframe_client import AsyncFlowFrame

    async with AsyncFlowFrame("http://localhost:8055", webhook_secret="my-secret") as ff:
        run = await ff.trigger("flow-id")
        async for line in ff.stream_logs(run["id"]):
            print(line)
"""

from flowframe_client._async import AsyncFlowFrame
from flowframe_client._sync import FlowFrame

__all__ = ["FlowFrame", "AsyncFlowFrame"]
