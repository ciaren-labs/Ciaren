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
from ciaren_client._types import (
    AppSetting,
    CodeExport,
    Connection,
    ConnectionTestResult,
    Dataset,
    DatasetVersion,
    Flow,
    FlowDocument,
    FlowMigrationResult,
    JsonDict,
    KeyringAvailability,
    KeyringSecretStatus,
    Project,
    Run,
    RunStatus,
    Schedule,
    WebhookStatus,
)

__version__ = "0.1.0-alpha.1"

__all__ = [
    "AppSetting",
    "AsyncCiaren",
    "Ciaren",
    "CodeExport",
    "Connection",
    "ConnectionTestResult",
    "Dataset",
    "DatasetVersion",
    "Flow",
    "FlowDocument",
    "FlowMigrationResult",
    "JsonDict",
    "KeyringAvailability",
    "KeyringSecretStatus",
    "Project",
    "Run",
    "RunStatus",
    "Schedule",
    "WebhookStatus",
]
