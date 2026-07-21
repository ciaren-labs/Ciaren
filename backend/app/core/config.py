# SPDX-License-Identifier: AGPL-3.0-only
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import Engine, ExecutionMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CIAREN_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Log output format. "auto" (default) prints ANSI-colored lines to a TTY and
    # plain text when redirected; "json" emits one JSON object per line for log
    # collectors (Docker/k8s/ELK); "text" forces plain lines regardless of TTY.
    LOG_FORMAT: str = "auto"

    DATABASE_URL: str = "sqlite+aiosqlite:///./ciaren.db"
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

    # Extra hostnames trusted by the browser-origin (CSRF) guard, beyond the
    # always-trusted local ones (localhost / 127.0.0.1 / ::1). A state-changing
    # /api request whose Origin header is neither a CORS_ORIGINS entry nor from
    # a trusted hostname is refused — this stops malicious websites from firing
    # cross-site POSTs at a local, unauthenticated Ciaren (which reaches plugin
    # install, i.e. code execution). Add the hostname here when serving the UI
    # from a non-local name without an API token (e.g. ["ciaren.lan"]); when
    # API_TOKEN is set the guard is unnecessary and steps aside. See app/core/csrf.py.
    TRUSTED_HOSTS: list[str] = []

    # Strict static checks for the pythonTransform node. Off by default so existing
    # scripts (e.g. `import numpy`) keep working. When on, a script is rejected at
    # save/preview/run time if it uses a dangerous import (os/sys/subprocess/…), a
    # code-exec builtin (eval/exec/open/__import__/…), or a dunder-traversal
    # attribute, and it runs with a restricted set of builtins. Defense in depth —
    # not a sandbox (Python can't be fully locked down in-process). See
    # Defense-in-depth for pythonTransform; not a Python sandbox.
    PYTHON_TRANSFORM_STRICT: bool = False

    # SSRF guard for outbound connector hosts. Off by default because the common
    # local-first setup legitimately connects to localhost / private-network
    # databases and object stores. Turn it ON for shared/networked deployments
    # where connection configs are not fully trusted: it refuses any SQL/Mongo host
    # or S3/Azure endpoint that resolves to a loopback, link-local (incl. the cloud
    # metadata endpoint 169.254.169.254), or private/RFC1918 address. See
    # Opt-in SSRF guard for connector hosts/endpoints.
    CONNECTOR_BLOCK_PRIVATE_HOSTS: bool = False

    # Which environment variables a connection's `password_env` may name. Empty
    # (default) allows any variable — the local-first posture, where the person
    # writing connections owns the process environment anyway. On shared
    # deployments set it to the vars (or prefixes ending in `*`, e.g.
    # ["CIAREN_SECRET_*", "PG_PASSWORD"]) that hold connection secrets: without
    # it, anyone who can save a connection can point `password_env` at ANY env
    # var and exfiltrate its value to a host they control (the connector sends
    # it as a password/API key). Ciaren's own config vars (CIAREN_API_TOKEN, …)
    # are always refused, allowlist or not. Entries match case-sensitively —
    # on Windows (case-insensitive env vars) list the exact spelling users put
    # in `password_env`. Applies to `env:`/bare references only; `keyring:` is
    # namespaced to the ciaren service and `file:` has SECRET_FILE_DIRS.
    # See app/core/secrets.py.
    SECRET_ENV_ALLOWLIST: list[str] = []

    # Folders a `file:` secret reference may read from (Docker/K8s secrets).
    # Empty (default) allows `<DATA_DIR>/secrets` and `/run/secrets`. Always
    # enforced — unlike STORAGE_ALLOWED_ROOTS there is no unrestricted mode,
    # because a free-form file reference would let any connection author read
    # arbitrary server files. See app/core/secrets.py.
    SECRET_FILE_DIRS: list[str] = []

    # Optional confinement for connector-reachable filesystem paths. Empty
    # (default) keeps the historical behavior: a Local Storage connection may
    # point at any folder the server process can access. When set to one or more
    # absolute directories, a Local Storage connection's root — and the database
    # file of file-based SQL connections (SQLite / DuckDB) — must resolve *inside*
    # one of them, otherwise the connection is refused. Use this on
    # shared/networked deployments to stop a connection from reading or writing
    # arbitrary server files (e.g. /etc, ~/.aws, Ciaren's own database).
    STORAGE_ALLOWED_ROOTS: list[str] = []

    # Path to the built frontend (frontend/dist). When set/auto-detected, the
    # server also serves the web UI so `ciaren serve` is a single URL. None +
    # no auto-detected dist = API only (run the Vite dev server separately).
    FRONTEND_DIST: str | None = None

    # Days a soft-deleted dataset's files are retained before `purge-expired`
    # removes them. Until then the dataset can be restored and historical runs
    # that referenced it still resolve.
    DATASET_RETENTION_DAYS: int = 30

    # On first boot (when no "Demo" project exists yet) seed a built-in demo
    # project with sample datasets and example flows so the app isn't empty.
    # Idempotent and skippable via `ciaren serve --no-demo`.
    SEED_DEMO: bool = True

    # After the demo project is first seeded, run every demo flow once so run
    # history (and MLflow models for the ML flows) aren't empty out of the box.
    # Off by default because it adds startup time.
    # Enable with `ciaren serve --run-seed-flows` or this env var.
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

    # -- Failure notifications ---------------------------------------------------

    # When set, Ciaren POSTs a JSON document to this URL whenever a run fails or
    # a schedule auto-disables (see app/core/notifications.py). Point it at a
    # Slack/Discord webhook bridge, an ntfy topic, or any internal endpoint.
    NOTIFY_WEBHOOK_URL: str = ""
    # Optional shared secret, sent as `X-Ciaren-Secret` so receivers can reject
    # posts that didn't come from this Ciaren instance.
    NOTIFY_WEBHOOK_SECRET: str = ""

    # -- API authentication ----------------------------------------------------
    # Optional bearer token for the REST API. Unset (default) keeps Ciaren's
    # local-first, no-auth posture — safe when bound to 127.0.0.1. When set, every
    # /api/* request must present the token via `Authorization: Bearer <token>` or
    # the `X-Ciaren-Token` header (constant-time compared). The static web UI,
    # health probes, OpenAPI, and the webhook trigger (which has its own
    # X-Ciaren-Secret) are exempt. Set this whenever the API is reachable from a
    # network you don't fully trust — e.g. the Docker image binds 0.0.0.0. See
    # Optional shared-token gate for non-local deployments.
    # Use a long, high-entropy random value — e.g.
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    # It is the only auth gate when the server is network-exposed and there is
    # no built-in rate limiting, so a weak or guessable token can be brute-forced.
    API_TOKEN: str | None = None

    # -- Webhook trigger -------------------------------------------------------
    # When set, POST /api/flows/{id}/trigger is enabled and the caller must
    # provide this value in the X-Ciaren-Secret header. Uses constant-time
    # comparison (hmac.compare_digest) to prevent timing attacks. Unset by
    # default so the endpoint is disabled on fresh installs (no secret = 404).
    WEBHOOK_SECRET: str | None = None

    # -- Machine learning (core; see app/ml/availability.py) --------------------
    # Feature flag. scikit-learn, MLflow, and joblib are core dependencies, so a
    # plain `pip install ciaren` already has a working ML palette — this flag is
    # just an operator on/off switch. XGBoost/LightGBM model types stay gated on
    # the ``[ml]`` extra regardless of this flag. Set false to disable ML routes
    # and hide the palette entirely.
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
    # Soft cap on unbounded, compute-scaling hyperparameters (n_estimators,
    # max_iter, ...). A value like n_estimators=1_000_000 wedges a fit for hours
    # *before* the post-fit model-size cap can fire — a self-inflicted DoS on
    # scheduled/unattended flows. Values over this are rejected with a clear
    # error. Raise it for genuinely large local jobs. See app/ml/security.py.
    ML_MAX_HYPERPARAMETER_VALUE: int = 100_000

    # Source for the "Explore" plugin catalog. Today a local JSON file path (the
    # MarketplaceIndex shape); empty uses Ciaren's bundled community catalog
    # so users can try installing a plugin. Set to "none" to disable Explore.
    # A hosted index is a drop-in later — the same setting will accept an https://
    # URL once network fetch lands, with no change to the API contract or frontend.
    MARKETPLACE_INDEX: str = ""
    # Require a trusted signature for marketplace/UI installs (hand-installed
    # community plugins via the CLI can still opt out). Off by default to keep
    # unsigned community plugins installable.
    REQUIRE_TRUSTED_PLUGINS: bool = False
    # Ed25519 public keys (raw 32-byte hex) of license-token issuers to trust,
    # e.g. '["<hex>"]'. When set, the core registers a TokenLicenseProvider for
    # each key at startup, so a license_required plugin loads once a token signed
    # by one of these issuers is cached locally (see app/plugins/licensing.py).
    # A list so an old and a new key can overlap during issuer key rotation.
    # Official marketplace issuer keys will ship pinned in code instead
    # (OFFICIAL_LICENSE_ISSUER_KEYS); this setting is for self-hosted issuers.
    MARKETPLACE_LICENSE_ISSUER_KEYS: list[str] = []

    # Runtime enforcement of the permissions a plugin was granted, via a CPython
    # audit hook (PEP 578) active only while a plugin node executes. Off by
    # default: it adds a small per-audit-event cost process-wide once installed,
    # and Ciaren's posture is that enabling a plugin already trusts its code.
    #   "off"     — no hook installed (zero overhead); permissions stay advisory.
    #   "warn"    — log when a plugin performs a network / filesystem-write /
    #               subprocess / shell action it was not granted (an audit trail;
    #               nothing is blocked).
    #   "enforce" — additionally raise PermissionError, aborting the ungranted
    #               action so the node fails with a clear message.
    # Hardening, not a sandbox: a determined plugin can still escape via threads,
    # a child process, or native code, and filesystem *reads* are never blocked
    # (the import system opens files). See app/plugins/permission_audit.py.
    PLUGIN_PERMISSION_ENFORCEMENT: str = "off"

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
