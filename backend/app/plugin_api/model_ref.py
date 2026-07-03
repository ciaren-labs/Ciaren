# SPDX-License-Identifier: Apache-2.0
"""The typed payload of a *model wire* — how trained models travel through a flow.

A train node never passes a raw estimator downstream. It emits a **model
reference**: a one-row dataframe pointing at a persisted artifact (an MLflow
``runs:/`` / ``models:/`` URI or a path inside the server's artifact root) plus
the metadata consumers need (task, model type, features). Passing references
instead of live objects keeps the graph serializable, keeps execution
engine-agnostic, and keeps model *loading* behind the host's security checks
(URI allowlist, artifact-root confinement, format allowlist) instead of letting
arbitrary pickled objects flow between nodes.

:class:`ModelRef` freezes that reference-frame layout as a public contract: the
core train nodes emit it, core consumers (``mlPredict``, ``featureImportance``,
``mlCrossValidate``) read it, and a plugin train node that emits
``ModelRef.to_frame()`` interoperates with all of them — and vice versa.

This module is part of the stable contract package: stdlib-only, with pandas
imported lazily inside the frame helpers (a plugin already has pandas as a data
plugin; the contract itself carries no hard dependency).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

#: Column layout of the one-row reference frame (order matters for stable frames).
MODEL_REF_COLUMNS = (
    "mlflow_run_id",
    "model_uri",
    "task_type",
    "model_type",
    "target_column",
    "feature_columns_json",
    "model_config_json",
)


@dataclass(frozen=True)
class ModelRef:
    """A reference to a trained (or defined) model.

    ``model_uri`` may be ``None`` for a *definition-only* reference (e.g. the
    Classifier Model nodes, or a preview placeholder) — consumers that need a
    loadable artifact must handle that case with a clear error.
    """

    task_type: str
    model_type: str
    mlflow_run_id: str | None = None
    model_uri: str | None = None
    target_column: str | None = None
    feature_columns: tuple[str, ...] = ()
    #: The training configuration (hyperparameters, preprocessing, seed, …).
    training_config: dict[str, Any] = field(default_factory=dict)

    # -- frame round-trip ------------------------------------------------------

    def to_row(self) -> dict[str, Any]:
        """The reference as a plain mapping using the public column layout."""
        return {
            "mlflow_run_id": self.mlflow_run_id,
            "model_uri": self.model_uri,
            "task_type": self.task_type,
            "model_type": self.model_type,
            "target_column": self.target_column,
            "feature_columns_json": json.dumps(list(self.feature_columns)),
            "model_config_json": json.dumps(self.training_config),
        }

    def to_frame(self) -> Any:
        """The one-row pandas DataFrame carried on a ``model`` output handle."""
        import pandas as pd

        return pd.DataFrame([self.to_row()])

    @classmethod
    def from_frame(cls, frame: Any) -> ModelRef:
        """Parse a reference from a model-wire frame.

        Tolerant of partial frames (older producers / hand-built references):
        missing columns fall back to defaults, NaN cells read as ``None``, and
        malformed JSON columns degrade to empty values rather than raising.
        Raises ``ValueError`` only when the frame is empty.
        """
        if frame is None or len(frame) == 0:
            raise ValueError("model reference frame is empty — no model to read")
        row = frame.iloc[0]

        def _get(column: str) -> Any:
            if column not in frame.columns:
                return None
            value = row[column]
            # A NaN float cell means "absent" in a frame that crossed an engine.
            if isinstance(value, float) and value != value:
                return None
            return value

        features: tuple[str, ...] = ()
        raw_features = _get("feature_columns_json")
        if isinstance(raw_features, str) and raw_features:
            try:
                parsed = json.loads(raw_features)
                if isinstance(parsed, list):
                    features = tuple(str(c) for c in parsed)
            except ValueError:
                pass

        config: dict[str, Any] = {}
        raw_config = _get("model_config_json")
        if isinstance(raw_config, str) and raw_config:
            try:
                parsed_config = json.loads(raw_config)
                if isinstance(parsed_config, dict):
                    config = parsed_config
            except ValueError:
                pass

        run_id = _get("mlflow_run_id")
        uri = _get("model_uri")
        target = _get("target_column")
        return cls(
            task_type=str(_get("task_type") or ""),
            model_type=str(_get("model_type") or ""),
            mlflow_run_id=str(run_id) if run_id is not None else None,
            model_uri=str(uri) if uri is not None else None,
            target_column=str(target) if target is not None else None,
            feature_columns=features,
            training_config=config,
        )


def is_model_ref_frame(frame: Any) -> bool:
    """Whether ``frame`` looks like a model-reference frame (cheap column check,
    used by consumers that accept either a model wire or a data wire)."""
    try:
        columns = set(frame.columns)
    except AttributeError:
        return False
    return {"model_uri", "task_type", "model_type"}.issubset(columns)
