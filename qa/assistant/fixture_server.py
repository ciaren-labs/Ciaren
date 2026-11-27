"""Browser-test process only. The editor, API, DB and engine are real; keyring and provider are doubles."""

import asyncio
from json import dumps, loads
import sys
from pathlib import Path
from unittest.mock import patch

import uvicorn

from app.core import assistant_keys
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
            answer = {
                "passage": next(
                    (
                        i
                        for i, p in enumerate(self.data["passages"])
                        if "left** handle" in p and "right** handle" in p
                    ),
                    None,
                )
            }
        elif "inputs" in self.data:
            left, right = self.data["inputs"]
            assert [left["side"], right["side"]] == ["left", "right"]

            def col(side, name):
                return next(c["index"] for c in side["columns"] if c["name"] == name)

            lk, rk = col(left, "sku"), col(right, "sku")
            assert [lk, rk] in self.data["shared_keys"]
            assert all(
                s not in dumps(self.data)
                for s in ("MISSING", "CABLE", "SLEEVE", "orders.csv", "catalog.csv")
            )
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
            assert (
                set(self.data) == {"question", "join", "how", "failure"}
                and self.data["how"] == "inner"
            )
            answer = {"join": self.data["join"], "how": "left"}
        elif self.data["mode"] == "diagnose":
            assert "column" in self.data["last_failure"].lower()
            index = next(
                i for i, n in enumerate(self.data["nodes"]) if n["type"] == "sortRows"
            )
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


if __name__ == "__main__":
    keychain = Keychain()
    with (
        patch.object(assistant_keys, "_backend", return_value=keychain),
        patch.object(
            assistant_provider.aiohttp.ClientSession,
            "post",
            side_effect=ProviderResponse,
        ),
    ):
        uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
