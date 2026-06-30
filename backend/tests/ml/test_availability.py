"""ML availability + feature-gate logic. No ML libraries are imported here, so
these pass whether or not the [ml] extra is installed."""

import pytest

from app.core.config import get_settings
from app.ml import availability
from app.ml.availability import (
    MLLibrary,
    install_hint,
    library_available,
    ml_core_available,
    ml_enabled,
    ml_extension_ready,
    ml_status,
    require_library,
)
from app.ml.models import model_catalog_status


@pytest.fixture
def ml_on(monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def ml_off(monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_library_available_for_stdlib():
    # A module that is always importable.
    assert library_available(MLLibrary("json", "json")) is True


def test_library_available_false_for_missing():
    assert library_available(MLLibrary("nope", "totally_not_a_real_module_xyz")) is False


def test_install_hint_points_at_extra():
    hint = install_hint(MLLibrary("XGBoost", "xgboost"))
    assert "flowframe[ml]" in hint
    assert "XGBoost" in hint


def test_require_library_raises_for_missing():
    with pytest.raises(RuntimeError, match="flowframe\\[ml\\]"):
        require_library(MLLibrary("Ghost", "totally_not_a_real_module_xyz"))


def test_require_library_passes_for_present():
    require_library(MLLibrary("json", "json"))  # no raise


def test_ml_enabled_reflects_setting(ml_on):
    assert ml_enabled() is True


def test_ml_enabled_off(ml_off):
    assert ml_enabled() is False


def test_extension_not_ready_when_disabled(ml_off, monkeypatch):
    # Even if every library were installed, the flag gates the feature.
    monkeypatch.setattr(availability, "ml_core_available", lambda: True)
    assert ml_extension_ready() is False


def test_extension_ready_requires_both(ml_on, monkeypatch):
    monkeypatch.setattr(availability, "ml_core_available", lambda: True)
    assert ml_extension_ready() is True
    monkeypatch.setattr(availability, "ml_core_available", lambda: False)
    assert ml_extension_ready() is False


def test_ml_status_shape(ml_off):
    status = ml_status()
    assert set(status) == {"enabled", "core_available", "ready", "libraries"}
    assert "sklearn" in status["libraries"]
    assert "xgboost" in status["libraries"]
    assert status["enabled"] is False
    # core_available reflects the real environment; just assert it's a bool.
    assert isinstance(status["core_available"], bool)


def test_ml_core_available_is_bool():
    assert isinstance(ml_core_available(), bool)


def test_model_catalog_status_marks_missing_optional_dependencies(monkeypatch):
    monkeypatch.setattr(availability, "library_available", lambda lib: lib.module != "xgboost")
    import app.ml.models as models

    monkeypatch.setattr(models, "library_available", lambda lib: lib.module != "xgboost")
    status = {row["model_type"]: row for row in model_catalog_status()}
    assert status["random_forest_classifier"]["available"] is True
    assert status["xgboost_classifier"]["available"] is False
    assert status["xgboost_classifier"]["missing"] == ["xgboost"]
    assert "flowframe[ml]" in status["xgboost_classifier"]["warning"]
