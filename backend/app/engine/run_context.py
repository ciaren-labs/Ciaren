"""Per-run context (flow id, run id, input dataset ids) made available to nodes
during execution without threading it through every signature.

The execution service sets this around a run; ML nodes read it to tag their MLflow
runs (reproducibility back-pointers, and the dataset link the registry-dependency
check relies on). It is a ``ContextVar`` so it is correct under concurrent runs and
is copied into the worker thread by ``asyncio.to_thread``; for process execution
the dict is passed explicitly and re-established in the worker.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_run_context: ContextVar[dict[str, Any] | None] = ContextVar("flowframe_run_context", default=None)


def current_run_context() -> dict[str, Any] | None:
    return _run_context.get()


@contextmanager
def run_context(
    *, flow_id: str | None, run_id: str | None, dataset_ids: list[str]
) -> Iterator[None]:
    token = _run_context.set({"flow_id": flow_id, "run_id": run_id, "dataset_ids": dataset_ids})
    try:
        yield
    finally:
        _run_context.reset(token)
