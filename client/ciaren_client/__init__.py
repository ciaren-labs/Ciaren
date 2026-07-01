"""ciaren-client — thin HTTP client for the Ciaren visual data and ML workflow server.

Sync usage::

    from ciaren_client import Ciaren

    ff = Ciaren("http://localhost:8055", webhook_secret="my-secret")
    run = ff.trigger("flow-id")
    print(run["status"])

Async usage::

    from ciaren_client import AsyncCiaren

    async with AsyncCiaren("http://localhost:8055", webhook_secret="my-secret") as ff:
        run = await ff.trigger("flow-id")
        async for line in ff.stream_logs(run["id"]):
            print(line)
"""

from ciaren_client._async import AsyncCiaren
from ciaren_client._sync import Ciaren

__all__ = ["Ciaren", "AsyncCiaren"]
