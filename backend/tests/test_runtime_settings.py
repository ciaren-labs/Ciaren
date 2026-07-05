"""Unit tests for app.core.runtime_settings (validation + override lifecycle).

The API-level behavior lives in tests/api/test_settings.py; this file covers
the pieces that also run outside a request: spec validation rules and the
worker-side sync (`apply_overrides(..., reset_missing=True)`) that process-pool
workers use to mirror the parent's effective settings.
"""

import pytest

from app.core.config import get_settings
from app.core.runtime_settings import (
    REGISTRY,
    SettingSpec,
    apply_overrides,
    clear_override,
    get_active_overrides,
    set_override,
)


@pytest.fixture(autouse=True)
def _fresh_settings():
    """Each test gets a pristine Settings singleton (and drops mutations after)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---- coerce ----------------------------------------------------------------


def test_integer_rejects_bool_and_non_int():
    spec = REGISTRY["MAX_UPLOAD_SIZE_MB"]
    with pytest.raises(ValueError):
        spec.coerce(True)
    with pytest.raises(ValueError):
        spec.coerce("100")
    with pytest.raises(ValueError):
        spec.coerce(10.5)
    assert spec.coerce(100) == 100


def test_integer_bounds_inclusive():
    spec = REGISTRY["SCHEDULER_POLL_INTERVAL_SECONDS"]
    assert spec.coerce(1) == 1
    assert spec.coerce(3600) == 3600
    with pytest.raises(ValueError):
        spec.coerce(0)
    with pytest.raises(ValueError):
        spec.coerce(3601)


def test_select_rejects_unknown_choice_and_non_str():
    spec = REGISTRY["EXECUTION_MODE"]
    assert spec.coerce("thread") == "thread"
    assert spec.coerce("process") == "process"
    with pytest.raises(ValueError):
        spec.coerce("fibers")
    with pytest.raises(ValueError):
        spec.coerce(3)


def test_url_rules():
    # No registry key uses "url" today (NOTIFY_WEBHOOK_URL was deliberately
    # kept env-only — see the module docstring), but the type stays supported.
    spec = SettingSpec(key="X_URL", label="x", description="", category="t", value_type="url")
    assert spec.coerce("") == ""
    assert spec.coerce("  https://h.example/x  ") == "https://h.example/x"
    for bad in ("javascript:alert(1)", "ftp://h/x", "https://", "nope", 42):
        with pytest.raises(ValueError):
            spec.coerce(bad)
    with pytest.raises(ValueError):
        spec.coerce("https://h.example/" + "a" * 2000)


# ---- override lifecycle -----------------------------------------------------


def test_set_and_clear_override_roundtrip():
    assert get_active_overrides() == {}
    set_override("RUN_TIMEOUT_SECONDS", 90)
    assert get_settings().RUN_TIMEOUT_SECONDS == 90
    assert get_active_overrides() == {"RUN_TIMEOUT_SECONDS": 90}

    restored = clear_override("RUN_TIMEOUT_SECONDS")
    assert restored == 0
    assert get_settings().RUN_TIMEOUT_SECONDS == 0
    assert get_active_overrides() == {}


def test_set_override_unknown_key_raises():
    with pytest.raises(KeyError):
        set_override("API_TOKEN", "x")
    with pytest.raises(KeyError):
        clear_override("API_TOKEN")


def test_overrides_die_with_the_settings_cache():
    set_override("RUN_TIMEOUT_SECONDS", 90)
    get_settings.cache_clear()
    assert get_settings().RUN_TIMEOUT_SECONDS == 0
    assert get_active_overrides() == {}


def test_apply_overrides_skips_bad_entries():
    apply_overrides({"NOT_A_KEY": 1, "DEFAULT_ENGINE": "spark", "RUN_TIMEOUT_SECONDS": 60})
    s = get_settings()
    assert s.RUN_TIMEOUT_SECONDS == 60
    assert s.DEFAULT_ENGINE == "polars"
    assert get_active_overrides() == {"RUN_TIMEOUT_SECONDS": 60}


def test_reset_missing_mirrors_parent_state_on_reused_worker():
    """A process-pool worker is reused across runs: syncing run N's overrides
    must also undo run N-1's overrides that were cleared in the parent."""
    apply_overrides({"RUN_TIMEOUT_SECONDS": 60, "DEFAULT_ENGINE": "pandas"}, reset_missing=True)
    s = get_settings()
    assert (s.RUN_TIMEOUT_SECONDS, s.DEFAULT_ENGINE) == (60, "pandas")

    # Parent cleared the timeout override; next task ships a smaller map.
    apply_overrides({"DEFAULT_ENGINE": "pandas"}, reset_missing=True)
    s = get_settings()
    assert s.RUN_TIMEOUT_SECONDS == 0
    assert s.DEFAULT_ENGINE == "pandas"
    assert get_active_overrides() == {"DEFAULT_ENGINE": "pandas"}

    apply_overrides({}, reset_missing=True)
    assert get_settings().DEFAULT_ENGINE == "polars"
    assert get_active_overrides() == {}
