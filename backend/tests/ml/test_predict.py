"""mlPredict: scoring from a model handle or a config URI, feature-mismatch
handling, probabilities, batching, and the no-model error."""

import numpy as np
import pytest

from app.engine.transformations.ml.predict import MLPredictTransformation
from tests.ml.conftest import classification_df

NODE = MLPredictTransformation()


def _model_uri(model_ref_frame, engine):
    return engine.to_pandas(model_ref_frame).iloc[0]["model_uri"]


def test_predict_via_model_handle(trained_classifier):
    engine, model_ref, df = trained_classifier
    data = engine.from_pandas(df.drop(columns=["target"]))
    out, meta = NODE.execute_with_metadata(engine, {"in": data, "model": model_ref}, {})
    result = engine.to_pandas(out["out"])
    assert "prediction" in result.columns
    assert len(result) == len(df)
    assert meta.task_type == "classification"
    assert meta.model_uri


def test_predict_blank_uri_falls_back_to_wired_model(trained_classifier):
    """A blank model_uri (the UI's default value) must not shadow a wired model.

    Regression: the editor saves model_uri="" by default; the resolver used to
    only honor the wired model when model_uri was strictly None, so a wired flow
    failed at run time with "no model to load" even though the wire was present.
    """
    engine, model_ref, df = trained_classifier
    data = engine.from_pandas(df.drop(columns=["target"]))
    for blank in ("", "   "):
        out, meta = NODE.execute_with_metadata(engine, {"in": data, "model": model_ref}, {"model_uri": blank})
        result = engine.to_pandas(out["out"])
        assert "prediction" in result.columns
        assert meta.model_uri


def test_predict_via_config_uri(trained_classifier):
    engine, model_ref, df = trained_classifier
    uri = _model_uri(model_ref, engine)
    data = engine.from_pandas(df.drop(columns=["target"]))
    out, _ = NODE.execute_with_metadata(engine, {"in": data}, {"model_uri": uri, "output_column": "yhat"})
    assert "yhat" in engine.to_pandas(out["out"]).columns


def test_predict_probabilities(trained_classifier):
    engine, model_ref, df = trained_classifier
    data = engine.from_pandas(df.drop(columns=["target"]))
    out, _ = NODE.execute_with_metadata(
        engine,
        {"in": data, "model": model_ref},
        {"output_proba_columns": ["proba_0", "proba_1"]},
    )
    result = engine.to_pandas(out["out"])
    assert {"proba_0", "proba_1"}.issubset(result.columns)
    # probabilities sum to 1
    np.testing.assert_allclose(result["proba_0"] + result["proba_1"], 1.0, atol=1e-6)


def test_extra_columns_dropped_for_prediction(trained_classifier):
    engine, model_ref, df = trained_classifier
    # df still has 'target' (extra at predict time) + an unrelated column.
    noisy = df.copy()
    noisy["unrelated"] = "x"
    out, _ = NODE.execute_with_metadata(engine, {"in": engine.from_pandas(noisy), "model": model_ref}, {})
    assert "prediction" in engine.to_pandas(out["out"]).columns


def test_missing_feature_raises(trained_classifier):
    engine, model_ref, df = trained_classifier
    data = engine.from_pandas(df[["x1", "target"]])  # missing x2
    with pytest.raises(ValueError, match="missing model features"):
        NODE.execute_with_metadata(engine, {"in": data, "model": model_ref}, {})


def test_no_model_no_uri_raises(trained_classifier):
    engine, _model_ref, df = trained_classifier
    data = engine.from_pandas(df.drop(columns=["target"]))
    with pytest.raises(ValueError, match="no model to load"):
        NODE.execute_with_metadata(engine, {"in": data}, {})


def test_batched_matches_unbatched(trained_classifier):
    engine, model_ref, df = trained_classifier
    data = engine.from_pandas(df.drop(columns=["target"]))
    full, _ = NODE.execute_with_metadata(engine, {"in": data, "model": model_ref}, {})
    batched, _ = NODE.execute_with_metadata(engine, {"in": data, "model": model_ref}, {"batch_size": 7})
    assert (
        engine.to_pandas(full["out"])["prediction"].tolist() == engine.to_pandas(batched["out"])["prediction"].tolist()
    )


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_predict_on_both_engines(ml_env, engine_name):
    from app.engine.backends import get_engine
    from app.engine.transformations.ml.train import MLTrainTransformation

    engine = get_engine(engine_name)
    df = classification_df()
    out_train, _ = MLTrainTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(df)},
        {"model_type": "logistic_regression", "target_column": "target", "seed": 1},
    )
    data = engine.from_pandas(df.drop(columns=["target"]))
    out, _ = NODE.execute_with_metadata(engine, {"in": data, "model": out_train["model"]}, {})
    assert "prediction" in engine.to_pandas(out["out"]).columns


def test_validate_config_rejects_bad_batch_and_proba():
    with pytest.raises(ValueError, match="batch_size"):
        NODE.validate_config({"batch_size": 0})
    with pytest.raises(ValueError, match="output_proba_columns"):
        NODE.validate_config({"output_proba_columns": "proba"})


# -- feature alignment fallback for models without feature_names_in_ (F2) -----


class _NoNamesModel:
    """A fitted model that carries no ``feature_names_in_`` (e.g. fit on a numpy
    array or an external model)."""

    def predict(self, x):
        return np.zeros(len(x))


def test_align_features_falls_back_to_recorded_features():
    import pandas as pd

    pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4], "target": [0, 1], "extra": [9, 9]})
    # Model has no feature_names_in_; recorded feature_columns come from the ref.
    x = NODE._align_features(_NoNamesModel(), pdf, ["a", "b"])
    # Subset to the recorded training features — target/extra are dropped, not fed.
    assert list(x.columns) == ["a", "b"]


def test_align_features_recorded_missing_feature_still_errors():
    import pandas as pd

    pdf = pd.DataFrame({"a": [1, 2]})  # missing recorded feature 'b'
    with pytest.raises(ValueError, match="missing model features"):
        NODE._align_features(_NoNamesModel(), pdf, ["a", "b"])


def test_align_features_no_names_no_recorded_passes_through():
    import pandas as pd

    pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    # Neither feature_names_in_ nor recorded features → rare external-model case,
    # keep prior behavior and pass the frame through unchanged.
    x = NODE._align_features(_NoNamesModel(), pdf, [])
    assert list(x.columns) == ["a", "b"]


def test_resolve_model_extracts_recorded_features():
    import json

    import pandas as pd

    from app.engine.backends import get_engine

    engine = get_engine("pandas")
    frame = engine.from_pandas(
        pd.DataFrame(
            [
                {
                    "model_uri": "runs:/abc/model",
                    "task_type": "classification",
                    "feature_columns_json": json.dumps(["x1", "x2"]),
                }
            ]
        )
    )
    uri, task, feats = NODE._resolve_model(engine, {"model": frame}, {})
    assert uri == "runs:/abc/model"
    assert task == "classification"
    assert feats == ["x1", "x2"]


# -- output-column collision warnings (F3) ------------------------------------


def test_output_column_collision_warns(trained_classifier, caplog):
    engine, model_ref, df = trained_classifier
    noisy = df.drop(columns=["target"]).copy()
    noisy["prediction"] = "original"  # would be silently clobbered
    with caplog.at_level("WARNING"):
        out, _ = NODE.execute_with_metadata(engine, {"in": engine.from_pandas(noisy), "model": model_ref}, {})
    assert "already exists in the input" in caplog.text
    # The prediction column was (intentionally) overwritten with model output.
    assert "prediction" in engine.to_pandas(out["out"]).columns


def test_proba_column_collision_warns(trained_classifier, caplog):
    engine, model_ref, df = trained_classifier
    noisy = df.drop(columns=["target"]).copy()
    noisy["proba_1"] = 0.0  # collides with a requested probability column
    with caplog.at_level("WARNING"):
        NODE.execute_with_metadata(
            engine,
            {"in": engine.from_pandas(noisy), "model": model_ref},
            {"output_proba_columns": ["proba_0", "proba_1"]},
        )
    assert "already exist in the input" in caplog.text
