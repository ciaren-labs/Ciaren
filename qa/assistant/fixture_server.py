"""Browser-test process only. The editor, API, DB and engine are real; keyring and provider are doubles."""

import asyncio
import sys
import time
from json import dumps, loads
from pathlib import Path
from unittest.mock import patch

import uvicorn

from app.core import assistant_keys
from app.engine.executor import FlowExecutor
from app.main import app
from app.services import assistant_provider


class Keychain(dict):
    def set_password(self, service, name, value):
        self[service, name] = value

    def get_password(self, service, name):
        return self.get((service, name))

    def delete_password(self, service, name):
        del self[service, name]


class ProviderResponse:
    status = 200

    def __init__(self, url, *, json, headers, allow_redirects):
        assert url == "https://api.openai.com/v1/responses" and not allow_redirects
        assert headers["Authorization"] == "Bearer synthetic-editor-key"
        self.data = loads(json["input"][0]["content"])
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        if self.data["question"] == "Wait for cancellation":
            Path("waiting").touch()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                Path("cancelled").touch()
                raise
        if "passages" in self.data:
            markers = {
                "How do I set up an API key?": "**New API key**",
                "Where can I see the history of assistant changes?": "**Preview reversal**",
            }
            marker = markers.get(self.data["question"], "left** handle")
            answer = {
                "passage": next((i for i, passage in enumerate(self.data["passages"]) if marker in passage), None)
            }
        elif "inputs" in self.data:
            left, right = self.data["inputs"]
            assert [left["side"], right["side"]] == ["left", "right"]

            def col(side, name):
                return next(c["index"] for c in side["columns"] if c["name"] == name)

            lk, rk = col(left, "sku"), col(right, "sku")
            assert [lk, rk] in self.data["shared_keys"]
            assert all(s not in dumps(self.data) for s in ("MISSING", "CABLE", "SLEEVE", "orders.csv", "catalog.csv"))
            answer = {
                "left": {"source": left["source"], "port": left["port"], "column": lk},
                "right": {
                    "source": right["source"],
                    "port": right["port"],
                    "column": rk,
                },
                "how": "left",
                "flag": {
                    "source": right["source"],
                    "column": col(right, "catalog_status"),
                    "equals": "active",
                    "name": "ready_to_fulfill",
                },
                "sort": {"source": left["source"], "column": col(left, "order_id")},
            }
        elif "join" in self.data:
            assert set(self.data) == {"question", "join", "how", "failure"} and self.data["how"] == "inner"
            answer = (
                {}
                if self.data["question"] == "Schedule a nightly refresh. Leave the Join unchanged."
                else {"join": self.data["join"], "how": "left"}
            )
        elif self.data["mode"] == "diagnose":
            assert "column" in self.data["last_failure"].lower()
            index = next(i for i, n in enumerate(self.data["nodes"]) if n["type"] == "sortRows")
            answer = {
                "replace": index,
                "steps": [{"kind": "sortRows", "columns": [0], "ascending": True}],
            }
        else:
            answer = {
                "steps": [
                    {"kind": "limitRows", "count": 10},
                    {"kind": "removeDuplicates"},
                ]
            }
        result = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": dumps(answer)}],
                }
            ],
        }
        yield dumps(result).encode()


# An E2E synchronisation point in the actual compute thread. Tests can edit the
# canvas while the real executor is in flight, then release it to process the CSVs.
execute = FlowExecutor.run_with_results


def controlled_compute(self, *args, **kwargs):
    if Path("hold-compute").is_file():
        Path("computing").touch()
        stop = time.monotonic() + 20
        while not Path("release-compute").is_file() and time.monotonic() < stop:
            time.sleep(0.03)
        if not Path("release-compute").is_file():
            raise TimeoutError("Editor did not release the test run")
    return execute(self, *args, **kwargs)


if __name__ == "__main__":
    keychain = Keychain()
    with (
        patch.object(FlowExecutor, "run_with_results", controlled_compute),
        patch.object(assistant_keys, "_backend", return_value=keychain),
        patch.object(
            assistant_provider.aiohttp.ClientSession,
            "post",
            side_effect=ProviderResponse,
        ),
    ):
        uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
