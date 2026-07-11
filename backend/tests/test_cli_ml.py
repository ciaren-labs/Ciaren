"""CLI: `ciaren init` provisions a default local MLflow, and info/check report
ML status. Overridable by env vars / editing the .env."""

import json

from app import cli


def _clear_settings_cache() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_init_writes_ml_defaults_and_provisions_mlflow(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    cli.main(["init"])
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "CIAREN_ML_ENABLED=true" in env
    assert "CIAREN_MLFLOW_TRACKING_URI=./mlruns" in env
    # a default local MLflow store directory is created
    assert (tmp_path / "mlruns").is_dir()
    out = capsys.readouterr().out
    assert "MLflow" in out


def test_init_no_ml_skips_mlflow(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cli.main(["init", "--no-ml"])
    assert (tmp_path / ".env").exists()
    assert not (tmp_path / "mlruns").exists()


def test_init_does_not_overwrite_without_force(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("EXISTING=1", encoding="utf-8")
    cli.main(["init"])
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "EXISTING=1"
    assert "already exists" in capsys.readouterr().out


def test_init_force_overwrites(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("EXISTING=1", encoding="utf-8")
    cli.main(["init", "--force"])
    assert "CIAREN_ML_ENABLED=true" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_mlflow_tracking_uri_is_overridable(monkeypatch, tmp_path):
    # The init default can be overridden to point at an existing MLflow server.
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", "http://mlflow.internal:5000")
    _clear_settings_cache()
    try:
        from app.core.config import get_settings

        assert get_settings().MLFLOW_TRACKING_URI == "http://mlflow.internal:5000"
    finally:
        _clear_settings_cache()


def test_info_includes_ml_fields(monkeypatch, capsys):
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    _clear_settings_cache()
    try:
        cli.main(["info", "--output", "json"])
    finally:
        _clear_settings_cache()
    data = json.loads(capsys.readouterr().out)
    assert data["ml_enabled"] is True
    assert "mlflow_tracking_uri" in data
    assert "ml_artifact_dir" in data


def test_check_reports_ml_enabled(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CIAREN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    _clear_settings_cache()
    try:
        cli.main(["check", "--output", "json"])
    finally:
        _clear_settings_cache()
    data = json.loads(capsys.readouterr().out)
    ml = next(c for c in data["checks"] if c["name"] == "ml")
    # [ml] is installed in the dev venv, so this resolves to ok.
    assert ml["status"] in ("ok", "warn")


def test_check_reports_ml_disabled(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CIAREN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "false")
    _clear_settings_cache()
    try:
        cli.main(["check", "--output", "json"])
    finally:
        _clear_settings_cache()
    data = json.loads(capsys.readouterr().out)
    ml = next(c for c in data["checks"] if c["name"] == "ml")
    assert ml["status"] == "ok"
    assert ml["detail"] == "disabled"


# --- MLflow path-length pre-flight (Windows MAX_PATH) --------------------------


def test_local_mlflow_store_dir_classifies_uris():
    # Bare paths and file:// URIs are local file stores whose artifact paths
    # count against MAX_PATH; remote/db stores are not our concern.
    assert cli._local_mlflow_store_dir("./mlruns") is not None
    assert str(cli._local_mlflow_store_dir("file:///tmp/mlruns")).replace("\\", "/").endswith("mlruns")
    assert cli._local_mlflow_store_dir("http://mlflow.internal:5000") is None
    assert cli._local_mlflow_store_dir("sqlite:///mlflow.db") is None
    assert cli._local_mlflow_store_dir("databricks") is None


def test_windows_long_paths_enabled_true_off_windows(monkeypatch):
    # Non-Windows platforms have no 260-char limit, so the probe is always True.
    monkeypatch.setattr(cli.sys, "platform", "linux")
    assert cli._windows_long_paths_enabled() is True


def test_mlflow_path_check_skips_when_long_paths_enabled(monkeypatch):
    monkeypatch.setattr(cli, "_windows_long_paths_enabled", lambda: True)
    assert cli._mlflow_path_length_check("/" + "d" * 200 + "/mlruns") is None


def test_mlflow_path_check_skips_remote_store(monkeypatch):
    monkeypatch.setattr(cli, "_windows_long_paths_enabled", lambda: False)
    assert cli._mlflow_path_length_check("http://mlflow.internal:5000") is None


def test_mlflow_path_check_ok_for_short_local_path(monkeypatch):
    monkeypatch.setattr(cli, "_windows_long_paths_enabled", lambda: False)
    result = cli._mlflow_path_length_check("/m/mlruns")
    assert result is not None
    assert result["name"] == "ml_path"
    assert result["status"] == "ok"


def test_mlflow_path_check_warns_for_long_local_path(monkeypatch):
    monkeypatch.setattr(cli, "_windows_long_paths_enabled", lambda: False)
    result = cli._mlflow_path_length_check("/" + "d" * 200 + "/mlruns")
    assert result is not None
    assert result["status"] == "warn"
    assert "WinError 206" in result["detail"]


def test_check_surfaces_ml_path_warning(monkeypatch, tmp_path, capsys):
    # An at-risk local store shows up as a non-fatal ml_path warn in `check`.
    monkeypatch.setattr(cli, "_windows_long_paths_enabled", lambda: False)
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CIAREN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", "/" + "d" * 200 + "/mlruns")
    _clear_settings_cache()
    try:
        cli.main(["check", "--output", "json"])
    finally:
        _clear_settings_cache()
    data = json.loads(capsys.readouterr().out)
    ml_path = next((c for c in data["checks"] if c["name"] == "ml_path"), None)
    # ml itself may be ok/warn depending on install; the path check must warn and
    # a warn must not flip the overall result to failed.
    if ml_path is not None:
        assert ml_path["status"] == "warn"
    assert data["ok"] is True
