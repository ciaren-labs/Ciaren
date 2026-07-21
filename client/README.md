# ciaren-client

`ciaren-client` is the lightweight Python SDK for Ciaren. It talks to the
Ciaren REST API without installing the full application.

> Status: alpha (pre-1.0), `0.2.0`. Breaking changes are expected before `1.0.0`.

## Install

```bash
python -m pip install ciaren-client
```

For local development from this repository:

```bash
pip install -e path/to/Ciaren/client
```

## Quick Start

```python
from ciaren_client import Ciaren

with Ciaren("http://localhost:8055", webhook_secret="my-secret") as client:
    run = client.trigger("flow-id", parameters={"date": "2026-07-01"})
    print(run["status"])
```

Async usage is available through `AsyncCiaren`:

```python
from ciaren_client import AsyncCiaren

async with AsyncCiaren("http://localhost:8055", webhook_secret="my-secret") as client:
    run = await client.trigger("flow-id")
```

## What It Covers

The client includes typed sync and async methods for projects, datasets, flows,
runs, schedules, connections (including OS-keychain secrets), catalog metadata,
transformations, runtime app settings, ML helpers, plugins, marketplace
endpoints, webhook triggers, and SSE run logs.

Use `api_token` when the server is configured with `CIAREN_API_TOKEN`.
Use `webhook_secret` only for `trigger()`, which calls the webhook endpoint.

License: Apache-2.0.

See the [SDK documentation](https://ciaren.com/docs/guide/sdk).
