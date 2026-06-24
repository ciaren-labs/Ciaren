"""Model catalog: every supported model_type builds a working estimator, the seed
is injected where supported, and bad inputs are rejected clearly."""
import pytest

from app.ml.models import (
    CLASSIFICATION,
    CLUSTERING,
    MODEL_CATALOG,
    REGRESSION,
    build_estimator,
    get_model_spec,
)


def test_every_catalog_entry_builds():
    for model_type in MODEL_CATALOG:
        est = build_estimator(model_type, {}, seed=42)
        # sklearn-compatible estimators expose get_params.
        assert hasattr(est, "get_params")


def test_unknown_model_type_lists_supported():
    with pytest.raises(ValueError, match="Unknown model_type"):
        build_estimator("magic_model", {}, seed=1)


def test_seed_injected_for_random_forest():
    est = build_estimator("random_forest_classifier", {}, seed=7)
    assert est.get_params()["random_state"] == 7


def test_seed_not_forced_when_user_sets_it():
    est = build_estimator("random_forest_classifier", {"random_state": 99}, seed=7)
    assert est.get_params()["random_state"] == 99


def test_knn_has_no_seed_param():
    # KNeighborsClassifier has no random_state; building must not fail.
    est = build_estimator("knn_classifier", {"n_neighbors": 3}, seed=7)
    assert est.get_params()["n_neighbors"] == 3


def test_bad_hyperparameter_name_is_value_error():
    with pytest.raises(ValueError, match="Invalid hyperparameters"):
        build_estimator("logistic_regression", {"not_a_param": 5}, seed=1)


def test_injection_string_rejected_by_sanitizer():
    from app.ml.security import ModelSecurityError

    with pytest.raises(ModelSecurityError):
        build_estimator("random_forest_classifier", {"x": object()}, seed=1)


@pytest.mark.parametrize("model_type,task", [
    ("logistic_regression", CLASSIFICATION),
    ("xgboost_classifier", CLASSIFICATION),
    ("linear_regression", REGRESSION),
    ("lightgbm_regressor", REGRESSION),
    ("kmeans", CLUSTERING),
])
def test_task_classification(model_type, task):
    assert get_model_spec(model_type).task == task


def test_clustering_is_unsupervised():
    assert get_model_spec("kmeans").supervised is False
    assert get_model_spec("logistic_regression").supervised is True


def test_estimators_can_fit_predict():
    import numpy as np

    x = np.random.RandomState(0).rand(60, 3)
    y_clf = (x[:, 0] > 0.5).astype(int)
    clf = build_estimator("random_forest_classifier", {"n_estimators": 10}, seed=0)
    clf.fit(x, y_clf)
    assert clf.predict(x[:5]).shape == (5,)

    y_reg = x[:, 0] * 2
    reg = build_estimator("ridge", {}, seed=0)
    reg.fit(x, y_reg)
    assert reg.predict(x[:5]).shape == (5,)
