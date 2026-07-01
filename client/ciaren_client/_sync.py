"""Synchronous Ciaren client backed by httpx.Client."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import httpx


class Ciaren:
    """Synchronous client for the Ciaren API.

    Can be used as a context manager::

        with Ciaren(base_url, webhook_secret=secret) as ff:
            run = ff.trigger(flow_id)

    Or managed manually::

        ff = Ciaren(base_url)
        ff.close()
    """

    def __init__(
        self,
        base_url: str,
        *,
        webhook_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = webhook_secret
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Ciaren:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    def list_flows(self) -> list[dict[str, Any]]:
        r = self._client.get("/api/flows")
        r.raise_for_status()
        return r.json()

    def get_flow(self, flow_id: str) -> dict[str, Any]:
        r = self._client.get(f"/api/flows/{flow_id}")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def list_runs(
        self,
        *,
        flow_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if flow_id:
            params["flow_id"] = flow_id
        r = self._client.get("/api/runs", params=params)
        r.raise_for_status()
        return r.json()

    def get_run(self, run_id: str) -> dict[str, Any]:
        r = self._client.get(f"/api/runs/{run_id}")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Webhook trigger
    # ------------------------------------------------------------------

    def _trigger_headers(self) -> dict[str, str]:
        if self._secret is None:
            raise ValueError(
                "webhook_secret is required to call trigger(). "
                "Pass it when constructing Ciaren(webhook_secret=...)."
            )
        return {"X-Ciaren-Secret": self._secret}

    def trigger(
        self,
        flow_id: str,
        *,
        engine: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger a flow run via the webhook endpoint.

        Returns the completed run dict (blocks until the server finishes).
        """
        body: dict[str, Any] = {}
        if engine:
            body["engine"] = engine
        if parameters:
            body["parameters"] = parameters
        r = self._client.post(
            f"/api/flows/{flow_id}/trigger",
            json=body or None,
            headers=self._trigger_headers(),
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # SSE log streaming
    # ------------------------------------------------------------------

    def stream_logs(self, run_id: str) -> Generator[dict[str, Any], None, None]:
        """Yield log entry dicts from GET /api/runs/{id}/logs/stream (SSE).

        Yields each ``data:`` event payload as a dict. Stops after the
        ``event: done`` frame arrives (that frame itself is not yielded).
        """
        import json

        with self._client.stream("GET", f"/api/runs/{run_id}/logs/stream") as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    try:
                        yield json.loads(payload)
                    except Exception:
                        yield {"raw": payload}
                elif line.startswith("event: done"):
                    return
