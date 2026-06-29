"""Security guardrails: model URI path validation, pickle rejection, and
hyperparameter sanitization."""
import pytest

from app.ml.security import (
    ModelSecurityError,
    sanitize_hyperparameters,
    validate_model_file_suffix,
    validate_model_uri,
)

# -- validate_model_uri -----------------------------------------------------


@pytest.mark.parametrize("uri", ["runs:/abc123/model", "models:/churn/Production", "models:/m/1"])
def test_mlflow_uris_pass_through(uri, tmp_path):
    assert validate_model_uri(uri, str(tmp_path)) == uri


def test_local_path_inside_artifact_root_allowed(tmp_path):
    model = tmp_path / "sub" / "model.joblib"
    model.parent.mkdir(parents=True)
    model.write_text("x")
    out = validate_model_uri(str(model), str(tmp_path))
    assert out == str(model.resolve())


def test_path_traversal_rejected(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    evil = root / ".." / ".." / "etc" / "passwd"
    with pytest.raises(ModelSecurityError, match="outside the allowed artifact"):
        validate_model_uri(str(evil), str(root))


def test_absolute_path_outside_root_rejected(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    other = tmp_path / "elsewhere" / "model.joblib"
    with pytest.raises(ModelSecurityError, match="outside the allowed artifact"):
        validate_model_uri(str(other), str(root))


def test_empty_uri_rejected(tmp_path):
    with pytest.raises(ModelSecurityError, match="non-empty"):
        validate_model_uri("   ", str(tmp_path))


# -- validate_model_file_suffix ---------------------------------------------


@pytest.mark.parametrize("name", ["model.joblib", "booster.json", "/a/b/c/model.JOBLIB"])
def test_allowed_suffixes(name):
    validate_model_file_suffix(name)  # no raise


@pytest.mark.parametrize("name", ["model.pkl", "model.pickle", "MODEL.PKL"])
def test_pickle_rejected(name):
    with pytest.raises(ModelSecurityError, match="pickle"):
        validate_model_file_suffix(name)


@pytest.mark.parametrize("name", ["model.bin", "model", "model.h5", "model.pt"])
def test_unknown_suffix_rejected(name):
    with pytest.raises(ModelSecurityError, match="unsupported model format"):
        validate_model_file_suffix(name)


# -- sanitize_hyperparameters -----------------------------------------------


def test_valid_hyperparameters_pass():
    params = {"n_estimators": 200, "max_depth": 10, "class_weight": "balanced",
              "alpha": 0.1, "fit_intercept": True, "missing": None,
              "weights": [1, 2, 3], "nested": {"a": 1}}
    assert sanitize_hyperparameters(params) == params


def test_none_becomes_empty_dict():
    assert sanitize_hyperparameters(None) == {}


def test_non_dict_rejected():
    with pytest.raises(ModelSecurityError, match="object"):
        sanitize_hyperparameters([1, 2, 3])


def test_non_string_key_rejected():
    with pytest.raises(ModelSecurityError, match="names must be strings"):
        sanitize_hyperparameters({1: "x"})


def test_callable_value_rejected():
    with pytest.raises(ModelSecurityError, match="non-JSON value"):
        sanitize_hyperparameters({"fn": lambda x: x})


def test_code_like_string_is_kept_as_literal():
    # A string that looks like code is NOT evaluated — it passes through verbatim,
    # leaving sklearn to reject it at fit time.
    out = sanitize_hyperparameters({"weird": "lambda x: x**2"})
    assert out["weird"] == "lambda x: x**2"


def test_nested_non_native_rejected():
    with pytest.raises(ModelSecurityError, match="non-JSON value"):
        sanitize_hyperparameters({"grid": [1, 2, object()]})


# -- loader size guard (ML_MAX_MODEL_SIZE_MB) -------------------------------


def test_load_model_rejects_oversized_joblib(tmp_path, monkeypatch):
    """A .joblib over the size cap is refused before the pickle-backed joblib
    deserializer runs (so this holds even without joblib installed)."""
    from app.core.config import get_settings
    from app.ml import loader

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    model = artifacts / "model.joblib"
    model.write_bytes(b"\x00" * (2 * 1024 * 1024))  # 2 MiB

    monkeypatch.setenv("FLOWFRAME_ML_ARTIFACT_DIR", str(artifacts))
    monkeypatch.setenv("FLOWFRAME_ML_MAX_MODEL_SIZE_MB", "1")  # 1 MiB cap < file
    get_settings.cache_clear()
    try:
        with pytest.raises(ModelSecurityError, match="over the .* MB limit"):
            loader.load_model(str(model))
    finally:
        get_settings.cache_clear()
