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
