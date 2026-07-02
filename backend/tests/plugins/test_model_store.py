"""MlflowModelStore — the permission-gated persistence/loading service handed to
plugin node runtimes. Loading deserializes pickled code, so every load path must
be behind an explicit permission grant; persistence goes to MLflow only."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.ml.availability import ml_core_available
from app.plugin_api import ModelRef, Permission
from app.plugins.model_store import MlflowModelStore, ModelStoreError

pytestmark = pytest.mark.skipif(not ml_core_available(), reason="ML core libraries not installed")


@pytest.fixture
def ml_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _fitted_estimator():
    from sklearn.tree import DecisionTreeClassifier

    rng = np.random.RandomState(0)
    x = pd.DataFrame({"a": rng.normal(size=40), "b": rng.normal(size=40)})
    y = (x["a"] > 0).astype(int)
    return DecisionTreeClassifier(max_depth=2, random_state=0).fit(x, y), x


def test_log_sklearn_model_returns_loadable_ref(ml_env):
    est, x = _fitted_estimator()
    store = MlflowModelStore("community.p", frozenset({Permission.local_model_load}))
    ref = store.log_sklearn_model(
        est,
        model_type="stub_tree",
        task_type="classification",
        target_column="y",
        feature_columns=("a", "b"),
        params={"max_depth": 2},
        metrics={"train_accuracy": 1.0},
    )
    assert isinstance(ref, ModelRef)
    assert ref.model_uri and ref.mlflow_run_id
    assert ref.training_config["plugin_id"] == "community.p"

    model = store.load_model(ref)
    assert len(model.predict(x)) == len(x)


def test_load_requires_a_grant_for_mlflow_uris(ml_env):
    store = MlflowModelStore("community.p", frozenset())
    with pytest.raises(ModelStoreError, match="permission"):
        store.load_model("runs:/abc/model")


def test_load_local_path_requires_joblib_load(ml_env):
    # local_model_load alone is not enough for a raw joblib file — that is the
    # pickle-load grant specifically.
    store = MlflowModelStore("community.p", frozenset({Permission.local_model_load}))
    with pytest.raises(ModelStoreError, match="joblib_load"):
        store.load_model(str(ml_env / "artifacts" / "m.joblib"))


def test_load_local_path_with_grant_still_confined_to_artifact_root(ml_env, tmp_path):
    store = MlflowModelStore("community.p", frozenset({Permission.joblib_load}))
    outside = tmp_path / "elsewhere" / "m.joblib"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"not a model")
    from app.ml.security import ModelSecurityError

    with pytest.raises(ModelSecurityError, match="artifact"):
        store.load_model(str(outside))


def test_load_pickle_suffix_always_refused(ml_env):
    store = MlflowModelStore("community.p", frozenset({Permission.joblib_load}))
    artifact_root = ml_env / "artifacts"
    artifact_root.mkdir(exist_ok=True)
    pkl = artifact_root / "m.pkl"
    pkl.write_bytes(b"payload")
    from app.ml.security import ModelSecurityError

    with pytest.raises(ModelSecurityError, match="pickle"):
        store.load_model(str(pkl))


def test_definition_only_ref_gives_clear_error(ml_env):
    store = MlflowModelStore("community.p", frozenset({Permission.joblib_load}))
    ref = ModelRef(task_type="classification", model_type="x")  # no model_uri
    with pytest.raises(ModelStoreError, match="model_uri"):
        store.load_model(ref)


def test_oversized_model_is_refused_before_logging(ml_env, monkeypatch):
    est, _x = _fitted_estimator()
    monkeypatch.setenv("CIAREN_ML_MAX_MODEL_SIZE_MB", "0")
    get_settings.cache_clear()
    store = MlflowModelStore("community.p", frozenset())
    with pytest.raises(ModelStoreError, match="ML_MAX_MODEL_SIZE_MB"):
        store.log_sklearn_model(est, model_type="t", task_type="classification")
