"""featureImportance: tree + linear models supported, SVM-rbf/KNN rejected."""

import pytest

from app.engine.backends import get_engine
from app.engine.transformations.ml.importance import FeatureImportanceTransformation
from app.engine.transformations.ml.train import MLTrainTransformation
from tests.ml.conftest import classification_df

NODE = FeatureImportanceTransformation()


def _train(model_type, engine, df, **extra):
    out, _ = MLTrainTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(df)},
        {"model_type": model_type, "target_column": "target", "seed": 0, **extra},
    )
    return out["model"]


def test_tree_importance(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    model_ref = _train("random_forest_classifier", engine, df)
    out, meta = NODE.execute_with_metadata(engine, {"model": model_ref}, {})
    result = engine.to_pandas(out["out"])
    assert list(result.columns) == ["feature_name", "importance", "rank"]
    assert set(result["feature_name"]) == {"x1", "x2"}
    assert result["rank"].tolist() == [1, 2]  # sorted desc
    assert result["importance"].is_monotonic_decreasing


def test_linear_importance(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    model_ref = _train("logistic_regression", engine, df)
    out, _ = NODE.execute_with_metadata(engine, {"model": model_ref}, {})
    result = engine.to_pandas(out["out"])
    assert set(result["feature_name"]) == {"x1", "x2"}
    assert (result["importance"] >= 0).all()  # abs(coef_)


def test_top_n(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    df["x3"] = df["x1"] * 0.5
    model_ref = _train("random_forest_classifier", engine, df, feature_columns=["x1", "x2", "x3"])
    out, _ = NODE.execute_with_metadata(engine, {"model": model_ref}, {"top_n": 2})
    assert len(engine.to_pandas(out["out"])) == 2


def test_knn_unsupported(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    model_ref = _train("knn_classifier", engine, df)
    with pytest.raises(ValueError, match="does not support"):
        NODE.execute_with_metadata(engine, {"model": model_ref}, {})


def test_svm_rbf_unsupported(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    # default SVC kernel is rbf -> no coef_
    model_ref = _train("svm_classifier", engine, df)
    with pytest.raises(ValueError, match="does not support"):
        NODE.execute_with_metadata(engine, {"model": model_ref}, {})


def test_validate_top_n():
    with pytest.raises(ValueError, match="top_n"):
        NODE.validate_config({"top_n": 0})


# -- export fidelity ---------------------------------------------------------


def _train_with_categorical(engine, **extra):
    import numpy as np
    import pandas as pd

    rng = np.random.RandomState(0)
    n = 120
    df = pd.DataFrame(
        {
            "age": rng.randint(20, 70, n).astype(float),
            "color": rng.choice(["red", "green", "blue"], n),
            "target": rng.randint(0, 2, n),
        }
    )
    out, _ = MLTrainTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(df)},
        {
            "model_type": "random_forest_classifier",
            "target_column": "target",
            "feature_columns": ["age", "color"],
            "seed": 0,
            **extra,
        },
    )
    return out["model"]


def test_export_recovers_real_feature_names_and_rank(ml_env):
    # The exported code must label features with their real (post one-hot) names and
    # carry the rank column — not bare integer indices, which is what it used to emit.
    import pandas as pd

    from app.ml.loader import load_model

    engine = get_engine("pandas")
    model_ref = _train_with_categorical(engine)
    config: dict = {}
    executed = engine.to_pandas(NODE.execute_with_metadata(engine, {"model": model_ref}, config)[0]["out"])

    pipe = load_model(engine.to_pandas(model_ref).iloc[0]["model_uri"])
    code = NODE.to_python_code({"model": "model"}, {"out": "res"}, config)
    ns = {"pd": pd, "model": pipe}
    exec(code, ns)  # noqa: S102
    exported = ns["res"]

    assert list(exported.columns) == ["feature_name", "importance", "rank"]
    # one-hot expands color -> color_red/green/blue; names must not be integers
    assert list(exported["feature_name"]) == list(executed["feature_name"])
    assert not any(isinstance(name, int) for name in exported["feature_name"])
    assert exported.reset_index(drop=True).equals(executed.reset_index(drop=True))


def test_export_multiclass_linear_matches_execute(ml_env):
    # A 3-class logistic regression has a 2-D coef_ (n_classes x n_features); both
    # execute and export must reduce it the same way (mean of |coef| over classes).
    import numpy as np
    import pandas as pd

    from app.ml.loader import load_model

    engine = get_engine("pandas")
    rng = np.random.RandomState(0)
    n = 150
    df = pd.DataFrame(
        {
            "age": rng.randint(20, 70, n).astype(float),
            "color": rng.choice(["red", "green", "blue"], n),
            "target": rng.randint(0, 3, n),  # 3 classes -> coef_.ndim == 2
        }
    )
    out, _ = MLTrainTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(df)},
        {
            "model_type": "logistic_regression",
            "target_column": "target",
            "feature_columns": ["age", "color"],
            "seed": 0,
        },
    )
    executed = engine.to_pandas(NODE.execute_with_metadata(engine, {"model": out["model"]}, {})[0]["out"])
    pipe = load_model(engine.to_pandas(out["model"]).iloc[0]["model_uri"])
    ns = {"pd": pd, "model": pipe}
    exec(NODE.to_python_code({"model": "model"}, {"out": "res"}, {}), ns)  # noqa: S102
    exported = ns["res"]
    assert list(exported["feature_name"]) == list(executed["feature_name"])
    assert np.allclose(exported["importance"].to_numpy(), executed["importance"].to_numpy())


def test_export_honours_top_n(ml_env):
    import pandas as pd

    from app.ml.loader import load_model

    engine = get_engine("pandas")
    model_ref = _train_with_categorical(engine)
    pipe = load_model(engine.to_pandas(model_ref).iloc[0]["model_uri"])
    code = NODE.to_python_code({"model": "model"}, {"out": "res"}, {"top_n": 2})
    ns = {"pd": pd, "model": pipe}
    exec(code, ns)  # noqa: S102
    assert len(ns["res"]) == 2
