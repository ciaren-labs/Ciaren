"""ciaren-client — thin HTTP client for the Ciaren visual data and ML workflow server.

Sync usage::

    from ciaren_client import Ciaren

    client = Ciaren("http://localhost:8055", webhook_secret="my-secret")
    run = client.trigger("flow-id")
    print(run["status"])

Async usage::

    from ciaren_client import AsyncCiaren

    async with AsyncCiaren("http://localhost:8055", webhook_secret="my-secret") as client:
        run = await client.trigger("flow-id")
        async for line in client.stream_logs(run["id"]):
            print(line)
"""

from ciaren_client._async import AsyncCiaren
from ciaren_client._sync import Ciaren

__all__ = ["Ciaren", "AsyncCiaren"]
