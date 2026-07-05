"""Runtime app settings (/api/settings): the Settings page contract.

Precedence under test: DB override > environment variable > built-in default.
Overrides apply to the live process immediately, persist in app_settings, and
"reset" (DELETE) falls back to whatever the environment says at that moment.
Only allowlisted keys are reachable — secrets and security guards must 404.
"""

from sqlalchemy import select

from app.core.config import get_settings
from app.core.runtime_settings import REGISTRY, load_and_apply_overrides
from app.db.models.app_setting import AppSetting


async def _get(client, key: str) -> dict:
    resp = await client.get("/api/settings")
    assert resp.status_code == 200, resp.text
    items = {item["key"]: item for item in resp.json()}
    assert key in items, f"{key} missing from /api/settings"
    return items[key]


# ---- listing ---------------------------------------------------------------


async def test_list_exposes_registry_with_metadata(client):
    resp = await client.get("/api/settings")
    assert resp.status_code == 200, resp.text
    items = {item["key"] for item in resp.json()}
    assert items == set(REGISTRY)
    engine = await _get(client, "DEFAULT_ENGINE")
    assert engine["value_type"] == "select"
    assert sorted(engine["choices"]) == ["pandas", "polars"]
    assert engine["env_var"] == "CIAREN_DEFAULT_ENGINE"
    timeout = await _get(client, "RUN_TIMEOUT_SECONDS")
    assert timeout["value_type"] == "integer"
    assert timeout["min_value"] == 0


async def test_list_never_exposes_secrets_or_guards(client):
    resp = await client.get("/api/settings")
    keys = {item["key"] for item in resp.json()}
    for forbidden in (
        "API_TOKEN",
        "WEBHOOK_SECRET",
        "NOTIFY_WEBHOOK_SECRET",
        "DATABASE_URL",
        "CORS_ORIGINS",
        "TRUSTED_HOSTS",
        "SECRET_ENV_ALLOWLIST",
        "STORAGE_ALLOWED_ROOTS",
        "PYTHON_TRANSFORM_STRICT",
        "PLUGIN_PERMISSION_ENFORCEMENT",
    ):
        assert forbidden not in keys


async def test_env_value_reported_as_env_source(client, monkeypatch):
    monkeypatch.setenv("CIAREN_DATASET_RETENTION_DAYS", "45")
    get_settings.cache_clear()
    item = await _get(client, "DATASET_RETENTION_DAYS")
    assert item["value"] == 45
    assert item["source"] == "env"
    assert item["default_value"] == 30
    assert item["env_value"] == 45


async def test_restart_required_flag_surfaces(client):
    item = await _get(client, "SCHEDULER_MAX_CONCURRENT_RUNS")
    assert item["restart_required"] is True
    item = await _get(client, "SCHEDULER_POLL_INTERVAL_SECONDS")
    assert item["restart_required"] is False


# ---- updating --------------------------------------------------------------


async def test_put_applies_immediately_and_persists(client, db_session):
    resp = await client.put("/api/settings/DEFAULT_ENGINE", json={"value": "pandas"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["value"] == "pandas"
    assert body["source"] == "override"

    # Applied to the live process (what runs actually consume)...
    assert get_settings().DEFAULT_ENGINE == "pandas"
    # ...and persisted.
    row = (await db_session.execute(select(AppSetting).where(AppSetting.key == "DEFAULT_ENGINE"))).scalar_one()
    assert row.value_json == "pandas"


async def test_put_integer_affects_derived_property(client):
    resp = await client.put("/api/settings/MAX_UPLOAD_SIZE_MB", json={"value": 1})
    assert resp.status_code == 200, resp.text
    assert get_settings().max_upload_bytes == 1024 * 1024


async def test_put_twice_updates_same_row(client, db_session):
    await client.put("/api/settings/RUN_TIMEOUT_SECONDS", json={"value": 60})
    resp = await client.put("/api/settings/RUN_TIMEOUT_SECONDS", json={"value": 120})
    assert resp.status_code == 200, resp.text
    rows = (await db_session.execute(select(AppSetting))).scalars().all()
    assert len(rows) == 1
    assert rows[0].value_json == 120
    assert get_settings().RUN_TIMEOUT_SECONDS == 120


async def test_override_beats_env(client, monkeypatch):
    monkeypatch.setenv("CIAREN_DATASET_RETENTION_DAYS", "45")
    get_settings.cache_clear()
    resp = await client.put("/api/settings/DATASET_RETENTION_DAYS", json={"value": 7})
    assert resp.status_code == 200, resp.text
    item = await _get(client, "DATASET_RETENTION_DAYS")
    assert item["value"] == 7
    assert item["source"] == "override"
    assert item["env_value"] == 45  # what reset would restore
    assert get_settings().DATASET_RETENTION_DAYS == 7


async def test_overrides_survive_restart(client, db_session):
    """Simulate a restart: fresh settings from env, then startup re-apply."""
    await client.put("/api/settings/DEFAULT_ENGINE", json={"value": "pandas"})

    get_settings.cache_clear()  # "restart": a brand-new Settings from env
    assert get_settings().DEFAULT_ENGINE == "polars"

    await load_and_apply_overrides(db_session)  # what lifespan does
    assert get_settings().DEFAULT_ENGINE == "pandas"


# ---- update rejections -----------------------------------------------------


async def test_put_unknown_key_404(client):
    resp = await client.put("/api/settings/NO_SUCH_SETTING", json={"value": 1})
    assert resp.status_code == 404, resp.text


async def test_put_env_only_keys_404_and_do_not_change(client, db_session):
    """Secrets and security guards are not editable through this API.

    NOTIFY_WEBHOOK_URL is in this list deliberately: notifications.py sends the
    env-only NOTIFY_WEBHOOK_SECRET to whatever URL is configured (and skips the
    SSRF guard because the URL is operator-controlled), so a UI-editable URL
    would let any UI user redirect the operator's secret to their own host.
    """
    for key, value in (
        ("API_TOKEN", "sneaky"),
        ("WEBHOOK_SECRET", "sneaky"),
        ("NOTIFY_WEBHOOK_URL", "https://attacker.example/collect"),
        ("NOTIFY_WEBHOOK_SECRET", "sneaky"),
        ("CORS_ORIGINS", "https://evil.example"),
        ("PYTHON_TRANSFORM_STRICT", "false"),
        ("SECRET_ENV_ALLOWLIST", "AWS_*"),
    ):
        resp = await client.put(f"/api/settings/{key}", json={"value": value})
        assert resp.status_code == 404, f"{key}: {resp.text}"
    rows = (await db_session.execute(select(AppSetting))).scalars().all()
    assert rows == []
    assert get_settings().API_TOKEN is None


async def test_put_wrong_type_400(client):
    resp = await client.put("/api/settings/MAX_UPLOAD_SIZE_MB", json={"value": "big"})
    assert resp.status_code == 400, resp.text


async def test_put_bool_for_integer_rejected(client):
    """JSON true must not sneak in as 1."""
    resp = await client.put("/api/settings/MAX_UPLOAD_SIZE_MB", json={"value": True})
    assert resp.status_code in (400, 422), resp.text
    assert get_settings().MAX_UPLOAD_SIZE_MB == 100


async def test_put_out_of_range_400(client):
    resp = await client.put("/api/settings/MAX_UPLOAD_SIZE_MB", json={"value": 0})
    assert resp.status_code == 400, resp.text
    resp = await client.put("/api/settings/DATASET_RETENTION_DAYS", json={"value": -1})
    assert resp.status_code == 400, resp.text
    resp = await client.put("/api/settings/SCHEDULER_POLL_INTERVAL_SECONDS", json={"value": 999_999})
    assert resp.status_code == 400, resp.text


async def test_put_invalid_choice_400(client):
    resp = await client.put("/api/settings/DEFAULT_ENGINE", json={"value": "spark"})
    assert resp.status_code == 400, resp.text
    assert get_settings().DEFAULT_ENGINE == "polars"


async def test_put_missing_value_422(client):
    resp = await client.put("/api/settings/DEFAULT_ENGINE", json={})
    assert resp.status_code == 422, resp.text


async def test_webhook_url_never_listed(client):
    """The webhook URL is often a capability-bearing secret (Slack/Discord);
    the settings API must neither list nor accept it."""
    resp = await client.get("/api/settings")
    assert all(item["key"] != "NOTIFY_WEBHOOK_URL" for item in resp.json())


# ---- reset -----------------------------------------------------------------


async def test_delete_clears_override_and_row(client, db_session):
    await client.put("/api/settings/DEFAULT_ENGINE", json={"value": "pandas"})
    resp = await client.delete("/api/settings/DEFAULT_ENGINE")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["value"] == "polars"
    assert body["source"] == "default"
    assert get_settings().DEFAULT_ENGINE == "polars"
    rows = (await db_session.execute(select(AppSetting))).scalars().all()
    assert rows == []


async def test_delete_restores_env_value(client, monkeypatch):
    monkeypatch.setenv("CIAREN_DATASET_RETENTION_DAYS", "45")
    get_settings.cache_clear()
    await client.put("/api/settings/DATASET_RETENTION_DAYS", json={"value": 7})
    resp = await client.delete("/api/settings/DATASET_RETENTION_DAYS")
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == 45
    assert resp.json()["source"] == "env"
    assert get_settings().DATASET_RETENTION_DAYS == 45


async def test_delete_without_override_is_idempotent(client):
    resp = await client.delete("/api/settings/DEFAULT_ENGINE")
    assert resp.status_code == 200, resp.text
    assert resp.json()["source"] == "default"


async def test_delete_unknown_key_404(client):
    resp = await client.delete("/api/settings/NO_SUCH_SETTING")
    assert resp.status_code == 404, resp.text


# ---- startup robustness ----------------------------------------------------


async def test_startup_skips_corrupt_rows(client, db_session):
    """Rows written by another version (unknown key, now-invalid value) must be
    skipped at startup, not crash it or poison the live settings."""
    db_session.add(AppSetting(key="REMOVED_IN_V2", value_json=123))
    db_session.add(AppSetting(key="DEFAULT_ENGINE", value_json="spark"))
    db_session.add(AppSetting(key="RUN_TIMEOUT_SECONDS", value_json=90))
    await db_session.commit()

    await load_and_apply_overrides(db_session)

    assert get_settings().DEFAULT_ENGINE == "polars"  # invalid value ignored
    assert get_settings().RUN_TIMEOUT_SECONDS == 90  # valid one applied


# ---- security: same gates as the rest of /api ------------------------------


async def test_settings_api_respects_api_token(client, monkeypatch):
    monkeypatch.setenv("CIAREN_API_TOKEN", "s3cret")
    get_settings.cache_clear()

    resp = await client.get("/api/settings")
    assert resp.status_code == 401, resp.text
    resp = await client.put("/api/settings/DEFAULT_ENGINE", json={"value": "pandas"})
    assert resp.status_code == 401, resp.text

    resp = await client.get("/api/settings", headers={"Authorization": "Bearer s3cret"})
    assert resp.status_code == 200, resp.text


async def test_settings_put_blocked_for_cross_site_origin(client):
    """The browser-origin (CSRF) guard covers this state-changing route too."""
    resp = await client.put(
        "/api/settings/DEFAULT_ENGINE",
        json={"value": "pandas"},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 403, resp.text
    assert get_settings().DEFAULT_ENGINE == "polars"
