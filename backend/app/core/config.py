from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import Engine, ExecutionMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLOWFRAME_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    APP_NAME: str = "FlowFrame"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Log output format. "auto" (default) prints ANSI-colored lines to a TTY and
    # plain text when redirected; "json" emits one JSON object per line for log
    # collectors (Docker/k8s/ELK); "text" forces plain lines regardless of TTY.
    LOG_FORMAT: str = "auto"

    DATABASE_URL: str = "sqlite+aiosqlite:///./flowframe.db"
    DATA_DIR: str = ".data"

    # Default dataframe engine for runs that don't request one explicitly.
    # "polars" is faster on medium data; "pandas" remains fully supported.
    # Kept as str (not the Engine enum) so a bad value is reported as a friendly
    # run-time 400 rather than crashing settings load; the default references the
    # enum as the single source of truth.
    DEFAULT_ENGINE: str = Engine.POLARS

    # How the synchronous flow compute is offloaded off the event loop.
    # "thread" (default) shares the GIL; "process" uses a ProcessPoolExecutor
    # for true multi-core parallelism.
    EXECUTION_MODE: str = ExecutionMode.THREAD

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    MAX_UPLOAD_SIZE_MB: int = 100

    # Path to the built frontend (frontend/dist). When set/auto-detected, the
    # server also serves the web UI so `flowframe serve` is a single URL. None +
    # no auto-detected dist = API only (run the Vite dev server separately).
    FRONTEND_DIST: str | None = None

    # Days a soft-deleted dataset's files are retained before `purge-expired`
    # removes them. Until then the dataset can be restored and historical runs
    # that referenced it still resolve.
    DATASET_RETENTION_DAYS: int = 30

    # On first boot (when no "Demo" project exists yet) seed a built-in demo
    # project with sample datasets and example flows so the app isn't empty.
    # Idempotent and skippable via `flowframe serve --no-demo`.
    SEED_DEMO: bool = True

    # After the demo project is first seeded, run every demo flow once so run
    # history (and MLflow models for the ML flows) aren't empty out of the box.
    # Off by default: it adds startup time and the ML flows need the [ml] extra.
    # Enable with `flowframe serve --run-seed-flows` or this env var.
    SEED_RUN_FLOWS: bool = False

    # Background cron scheduler. Disabled in tests (ASGITransport skips lifespan).
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_POLL_INTERVAL_SECONDS: int = 30
    SCHEDULER_MAX_CONCURRENT_RUNS: int = 1
    # Auto-disable a schedule after this many consecutive failed runs (0 = never).
    SCHEDULER_MAX_CONSECUTIVE_FAILURES: int = 5
    # Abandon a run (manual or scheduled) after this many seconds (0 = no limit).
    # In "process" execution mode the worker process is also recycled so the CPU
    # is reclaimed; in "thread" mode the run is abandoned but the thread finishes.
    RUN_TIMEOUT_SECONDS: int = 0

    # -- Webhook trigger -------------------------------------------------------
    # When set, POST /api/flows/{id}/trigger is enabled and the caller must
    # provide this value in the X-FlowFrame-Secret header. Uses constant-time
    # comparison (hmac.compare_digest) to prevent timing attacks. Unset by
    # default so the endpoint is disabled on fresh installs (no secret = 404).
    WEBHOOK_SECRET: str | None = None

    # -- Machine learning (optional extension; see docs/ml-architecture.md) ----
    # Feature flag. ML nodes/routes only activate when this is true AND the ``[ml]``
    # extra is installed — so this default is safe for the lean base install (no
    # [ml] = ML stays off regardless). Set false to force ML off even with [ml].
    ML_ENABLED: bool = True
    # MLflow tracking + registry. Local ``./mlruns`` needs no server; accepts any
    # URI MLflow understands (sqlite:///, http://host:5000, databricks, ...).
    MLFLOW_TRACKING_URI: str = "./mlruns"
    # Registry URI; None means "same as tracking URI".
    MLFLOW_REGISTRY_URI: str | None = None
    # Local root for model artifacts, resolved under DATA_DIR when relative.
    # mlPredict only loads local model paths that live under this directory.
    ML_ARTIFACT_DIR: str = "ml_artifacts"
    # Guardrails enforced before a training job consumes CPU (see §6.4).
    ML_MAX_MODEL_SIZE_MB: int = 500
    ML_MAX_TRAINING_ROWS: int = 5_000_000
    ML_MAX_FEATURE_COLUMNS: int = 500

    # Source for the "Explore" plugin catalog. Today a local JSON file path (the
    # MarketplaceIndex shape); empty disables the catalog. A hosted index is a
    # drop-in later — the same setting will accept an https:// URL once network
    # fetch lands, with no change to the API contract or the frontend.
    MARKETPLACE_INDEX: str = ""
    # Require a trusted signature for marketplace/UI installs (hand-installed
    # community plugins via the CLI can still opt out). Off by default to keep
    # unsigned community plugins installable.
    REQUIRE_TRUSTED_PLUGINS: bool = False

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def ml_artifact_path(self) -> str:
        """Absolute artifact root, resolved under DATA_DIR when given as a relative
        path. mlPredict validates user-supplied model URIs against this."""
        from pathlib import Path

        p = Path(self.ML_ARTIFACT_DIR)
        if not p.is_absolute():
            p = Path(self.DATA_DIR) / p
        return str(p.resolve())


@lru_cache
def get_settings() -> Settings:
    return Settings()
