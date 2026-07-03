"""ModelRef — the typed model-wire payload and its frame round-trip."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.plugin_api import MODEL_REF_COLUMNS, ModelRef, is_model_ref_frame


def _ref(**overrides) -> ModelRef:
    base = dict(
        task_type="classification",
        model_type="mlp_classifier",
        mlflow_run_id="run-123",
        model_uri="runs:/run-123/model",
        target_column="churn",
        feature_columns=("age", "tenure"),
        training_config={"hyperparameters": {"alpha": 0.001}, "seed": 42},
    )
    base.update(overrides)
    return ModelRef(**base)


def test_round_trips_through_a_frame():
    ref = _ref()
    frame = ref.to_frame()
    assert list(frame.columns) == list(MODEL_REF_COLUMNS)
    assert len(frame) == 1
    restored = ModelRef.from_frame(frame)
    assert restored == ref


def test_frame_layout_matches_core_train_output():
    """The columns are a public contract: core mlPredict reads model_uri/task_type
    from them and the core train nodes emit exactly this set."""
    row = _ref().to_row()
    assert set(row) == set(MODEL_REF_COLUMNS)
    assert json.loads(row["feature_columns_json"]) == ["age", "tenure"]
    assert json.loads(row["model_config_json"])["seed"] == 42


def test_from_frame_tolerates_partial_and_nan_frames():
    frame = pd.DataFrame(
        [
            {
                "model_uri": float("nan"),  # engine bridges turn None into NaN
                "task_type": "regression",
                "model_type": "ridge",
            }
        ]
    )
    ref = ModelRef.from_frame(frame)
    assert ref.model_uri is None
    assert ref.mlflow_run_id is None
    assert ref.task_type == "regression"
    assert ref.feature_columns == ()
    assert ref.training_config == {}


def test_from_frame_degrades_on_malformed_json():
    frame = pd.DataFrame(
        [
            {
                "task_type": "classification",
                "model_type": "x",
                "feature_columns_json": "{not json",
                "model_config_json": "[1, 2]",  # valid JSON but not an object
            }
        ]
    )
    ref = ModelRef.from_frame(frame)
    assert ref.feature_columns == ()
    assert ref.training_config == {}


def test_from_frame_rejects_empty_frames():
    with pytest.raises(ValueError, match="empty"):
        ModelRef.from_frame(pd.DataFrame())


def test_is_model_ref_frame():
    assert is_model_ref_frame(_ref().to_frame())
    assert not is_model_ref_frame(pd.DataFrame({"a": [1]}))
    assert not is_model_ref_frame(object())
