# SPDX-License-Identifier: AGPL-3.0-only
"""The host-side :class:`~app.plugin_api.node_runtime.ModelStore` implementation.

Handed to plugin node runtimes via their :class:`NodeContext`, this is the
sanctioned persistence path for plugin-trained models: log the fitted estimator
to MLflow and pass the returned :class:`ModelRef` downstream, so raw estimators
(and raw pickles) never travel through the graph or the filesystem.

Loading is permission-gated per the plugin's *granted* permissions and always
funnels through :mod:`app.ml.loader` — the same URI allowlist, artifact-root
confinement, suffix allowlist, and size caps that protect core mlPredict.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

from app.plugin_api import ModelRef, Permission

logger = logging.getLogger("app.plugins.model_store")

#: Loading an MLflow-logged sklearn model deserializes cloudpickle; loading a
#: local ``.joblib`` deserializes a pickle. Both execute code on load, so both
#: require an explicit grant.
_LOAD_PERMISSIONS = frozenset({Permission.local_model_load, Permission.joblib_load})


class ModelStoreError(RuntimeError):
    """A model could not be persisted or loaded through the plugin ModelStore."""


class MlflowModelStore:
    """MLflow-backed model persistence for one plugin."""

    def __init__(self, plugin_id: str, granted_permissions: frozenset[Permission]) -> None:
        self._plugin_id = plugin_id
        self._granted = frozenset(granted_permissions)

    # -- logging ---------------------------------------------------------------

    def log_sklearn_model(
        self,
        model: Any,
        *,
        model_type: str,
        task_type: str,
        target_column: str | None = None,
        feature_columns: tuple[str, ...] = (),
        params: dict[str, Any] | None = None,
        metrics: dict[str, float] | None = None,
        input_example: Any = None,
        experiment: str | None = None,
    ) -> ModelRef:
        """Persist a fitted sklearn-compatible model and return its reference.

        Unlike the core train nodes (which tolerate MLflow failures and continue
        untracked), this raises :class:`ModelStoreError` when the model cannot be
        persisted — a plugin node exists to produce the artifact, and silently
        emitting a reference that points nowhere would lose the model.
        """
        self._enforce_size_limit(model, model_type)
        try:
            from app.ml.tracking import configure_mlflow

            mlflow = configure_mlflow()
            import mlflow.sklearn  # noqa: F811 - load the submodule onto the configured client

            mlflow.set_experiment(experiment or "ciaren")
            with mlflow.start_run() as run:
                # Params/metrics/tags are secondary — never fail the save over them.
                try:
                    if params:
                        mlflow.log_params(params)
                    if metrics:
                        mlflow.log_metrics(metrics)
                    mlflow.set_tags({"ciaren_plugin_id": self._plugin_id, **self._run_context_tags()})
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ModelStore(%s): could not log params/metrics/tags (%s).", self._plugin_id, exc)
                info = mlflow.sklearn.log_model(
                    model,
                    name="model",
                    serialization_format="cloudpickle",
                    input_example=input_example,
                )
                run_id, model_uri = run.info.run_id, info.model_uri
        except Exception as exc:  # noqa: BLE001 — surface one clear error to the node
            raise ModelStoreError(f"could not persist model for plugin {self._plugin_id!r}: {exc}") from exc

        return ModelRef(
            task_type=task_type,
            model_type=model_type,
            mlflow_run_id=run_id,
            model_uri=model_uri,
            target_column=target_column,
            feature_columns=tuple(feature_columns),
            training_config={"hyperparameters": params or {}, "plugin_id": self._plugin_id},
        )

    # -- loading ----------------------------------------------------------------

    def load_model(self, ref_or_uri: ModelRef | str) -> Any:
        """Load a model after permission + security checks (see module docstring)."""
        uri = ref_or_uri.model_uri if isinstance(ref_or_uri, ModelRef) else ref_or_uri
        if not uri:
            raise ModelStoreError("model reference has no model_uri — it was a definition-only or preview reference")
        self._require_load_permission(str(uri))
        from app.ml.loader import load_model

        return load_model(str(uri))

    def _require_load_permission(self, uri: str) -> None:
        """Deserializing a model executes code (cloudpickle / joblib-pickle), so a
        plugin may only load models when the user granted it a load permission."""
        if uri.startswith(("runs:/", "models:/")):
            if self._granted & _LOAD_PERMISSIONS:
                return
            needed = " or ".join(sorted(p.value for p in _LOAD_PERMISSIONS))
        else:
            # A local artifact path is joblib territory; require the explicit
            # pickle-load grant (confinement to the artifact root is enforced by
            # app.ml.loader on top of this).
            if Permission.joblib_load in self._granted:
                return
            needed = Permission.joblib_load.value
        raise ModelStoreError(
            f"plugin {self._plugin_id!r} is not permitted to load models: loading "
            f"deserializes pickled code, which requires the {needed} permission to be granted"
        )

    # -- helpers ------------------------------------------------------------------

    def _enforce_size_limit(self, model: Any, model_type: str) -> None:
        import joblib

        from app.core.config import get_settings

        max_mb = get_settings().ML_MAX_MODEL_SIZE_MB
        buf = io.BytesIO()
        joblib.dump(model, buf)
        size_mb = buf.tell() / 1_000_000
        if size_mb > max_mb:
            raise ModelStoreError(
                f"{model_type}: trained model is {size_mb:.1f} MB, over the {max_mb} MB limit (ML_MAX_MODEL_SIZE_MB)."
            )

    def _run_context_tags(self) -> dict[str, str]:
        """Back-pointer tags linking the MLflow run to the Ciaren run/flow, matching
        what the core train nodes record (dataset-deletion guard, traceability)."""
        from app.engine.run_context import current_run_context

        ctx = current_run_context()
        if not ctx:
            return {}
        tags: dict[str, str] = {}
        if ctx.get("flow_id"):
            tags["ciaren_flow_id"] = str(ctx["flow_id"])
        if ctx.get("run_id"):
            tags["ciaren_run_id"] = str(ctx["run_id"])
        if ctx.get("dataset_ids"):
            tags["ciaren_dataset_ids"] = json.dumps(ctx["dataset_ids"])
        return tags
