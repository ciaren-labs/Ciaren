# SPDX-License-Identifier: AGPL-3.0-only
"""Find registered models that depend on a dataset (for the deletion guard).

A model "depends on" a dataset when a registered version aliased ``production`` was
trained by an mlTrain run tagged with that dataset id (see the reproducibility tags
in mlTrain). Best-effort: any MLflow problem yields an empty result rather than
blocking a delete on an unreachable registry.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Versions carrying this alias are considered "live in Production".
_PRODUCTION_ALIAS = "production"


def production_models_for_dataset(dataset_id: str, tracking_uri: str | None = None) -> list[str]:
    """Return ``"name/version"`` for each Production-aliased model trained on
    ``dataset_id``. Empty when none, or when MLflow is unavailable."""
    try:
        from app.ml.tracking import configure_mlflow, mlflow_tracking_lock

        # configure_mlflow() mutates process-global MLflow SDK state, and the
        # bare MlflowClient() below reads it back implicitly (no explicit
        # tracking_uri) — locked so a concurrent training run's configure
        # can't land between these two lines and construct this client
        # against the wrong store. The client captures its store at
        # construction, so nothing after this block needs the lock.
        with mlflow_tracking_lock():
            mlflow = configure_mlflow(tracking_uri=tracking_uri)
            client = mlflow.tracking.MlflowClient()
    except Exception as exc:  # noqa: BLE001 - never block a delete on registry issues
        logger.warning("Production-dependency check skipped (MLflow unavailable: %s).", exc)
        return []

    found: list[str] = []
    try:
        for rm in client.search_registered_models():
            mv = _production_version(client, rm.name)
            if mv is None or not mv.run_id:
                continue
            if dataset_id in _run_dataset_ids(client, mv.run_id):
                found.append(f"{rm.name}/{mv.version}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Production-dependency check failed mid-scan (%s).", exc)
    return found


def _production_version(client: Any, name: str) -> Any:
    try:
        return client.get_model_version_by_alias(name, _PRODUCTION_ALIAS)
    except Exception:  # noqa: BLE001 - alias simply not set on this model
        return None


def _run_dataset_ids(client: Any, run_id: str) -> list[str]:
    try:
        run = client.get_run(run_id)
        raw = run.data.tags.get("ciaren_dataset_ids")
        return list(json.loads(raw)) if raw else []
    except Exception:  # noqa: BLE001 - missing run/tag or bad json -> no dependency
        return []
