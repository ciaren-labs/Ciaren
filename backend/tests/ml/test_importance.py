"""featureImportance: tree + linear models supported, SVM-rbf/KNN rejected."""
import pytest

from app.engine.backends import get_engine
from app.engine.transformations.ml.importance import FeatureImportanceTransformation
from app.engine.transformations.ml.train import MLTrainTransformation
from tests.ml.conftest import classification_df

NODE = FeatureImportanceTransformation()


def _train(model_type, engine, df, **extra):
    out, _ = MLTrainTransformation().execute_with_metadata(
        engine, {"in": engine.from_pandas(df)},
        {"model_type": model_type, "target_column": "target", "seed": 0, **extra},
    )
    return out["model"]


def test_tree_importance(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    model_ref = _train("random_forest_classifier", engine, df)
    out, meta = NODE.execute_with_metadata(engine, {"in": model_ref}, {})
    result = engine.to_pandas(out["out"])
    assert list(result.columns) == ["feature_name", "importance", "rank"]
    assert set(result["feature_name"]) == {"x1", "x2"}
    assert result["rank"].tolist() == [1, 2]  # sorted desc
    assert result["importance"].is_monotonic_decreasing


def test_linear_importance(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    model_ref = _train("logistic_regression", engine, df)
    out, _ = NODE.execute_with_metadata(engine, {"in": model_ref}, {})
    result = engine.to_pandas(out["out"])
    assert set(result["feature_name"]) == {"x1", "x2"}
    assert (result["importance"] >= 0).all()  # abs(coef_)


def test_top_n(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    df["x3"] = df["x1"] * 0.5
    model_ref = _train("random_forest_classifier", engine, df, feature_columns=["x1", "x2", "x3"])
    out, _ = NODE.execute_with_metadata(engine, {"in": model_ref}, {"top_n": 2})
    assert len(engine.to_pandas(out["out"])) == 2


def test_knn_unsupported(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    model_ref = _train("knn_classifier", engine, df)
    with pytest.raises(ValueError, match="does not support"):
        NODE.execute_with_metadata(engine, {"in": model_ref}, {})


def test_svm_rbf_unsupported(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    # default SVC kernel is rbf -> no coef_
    model_ref = _train("svm_classifier", engine, df)
    with pytest.raises(ValueError, match="does not support"):
        NODE.execute_with_metadata(engine, {"in": model_ref}, {})


def test_validate_top_n():
    with pytest.raises(ValueError, match="top_n"):
        NODE.validate_config({"top_n": 0})
