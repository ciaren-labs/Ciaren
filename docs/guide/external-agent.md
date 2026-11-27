---
title: Connect your own agent to the Ciaren node catalog
description: "Learn which agent interfaces Ciaren supports and use a read-only Python SDK function to discover the Join input ports on a local server."
search: external AI agent MCP Model Context Protocol Python SDK REST node catalog Join ports
---

# Connect your own agent to the Ciaren node catalog

## Does Ciaren provide an MCP server?

Ciaren does not ship a Model Context Protocol (MCP) server, a stdio command for MCP clients or an MCP registration URL. The editor's Flow Assistant uses internal typed operations. Choosing a model provider in Settings configures that editor feature.

For an agent you maintain, the supported integration interfaces are the Ciaren REST API and the Python SDK. A small catalog lookup lets an agent answer a question about the installed nodes without reading a dataset or executing a pipeline.

## Give an agent one read-only lookup

Start your local Ciaren server with `ciaren serve`. Install the client from the same checkout with `python -m pip install ./client`. Save this as `join_ports.py` and run `python join_ports.py`:

```python
import os

from ciaren_client import Ciaren


def join_input_ports() -> list[str]:
    """List the installed Join node's input port IDs."""
    with Ciaren(
        "http://127.0.0.1:8055",
        api_token=os.environ.get("CIAREN_API_TOKEN"),
    ) as client:
        join = next(node for node in client.list_catalog_nodes() if node["id"] == "join")
        return [port["id"] for port in join["inputs"]]


if __name__ == "__main__":
    print(join_input_ports())
```

The expected result is `['left', 'right']`. Register only this fixed function with your own agent host. It calls `GET /api/catalog/nodes` and returns two port IDs. This lookup works with the editor assistant switched off and needs no model provider or provider key.

If your installation requires authentication, supply the Ciaren server token to the host process via its environment. Keep it out of prompts and tool results. The installation token can authorize other operations; the fixed function limits what this particular tool exposes. Keep writes, arbitrary requests and run submission outside that tool. The editor’s proposal review and Activity history apply to the built-in assistant.

See the [Python SDK guide](sdk.md), [REST API reference](../api/rest-api.md) and [Flow Assistant tutorial](flow-assistant-quick-start.md).
