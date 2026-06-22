from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLOWFRAME_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    APP_NAME: str = "FlowFrame"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite+aiosqlite:///./flowframe.db"
    DATA_DIR: str = ".data"

    # Default dataframe engine for runs that don't request one explicitly.
    # "polars" is faster on medium data; "pandas" remains fully supported.
    DEFAULT_ENGINE: str = "polars"

    # How the synchronous flow compute is offloaded off the event loop.
    # "thread" (default) shares the GIL; "process" uses a ProcessPoolExecutor
    # for true multi-core parallelism.
    EXECUTION_MODE: str = "thread"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    MAX_UPLOAD_SIZE_MB: int = 100

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

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
