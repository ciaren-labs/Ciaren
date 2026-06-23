import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    # StaticPool keeps the same connection alive so the in-memory DB is shared
    # across all operations within a single test.
    _engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest.fixture
async def db_session(engine):
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_session, tmp_path, monkeypatch):
    # Point DATA_DIR at a per-test temp directory so file uploads are isolated
    # and cleaned up automatically after each test.
    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_DATA_DIR", str(tmp_path))
    # Pin ML off by default for API tests so gating behavior is deterministic
    # regardless of the product default (which is now true). ML tests opt in by
    # setting FLOWFRAME_ML_ENABLED=true + clearing the settings cache.
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "false")
    get_settings.cache_clear()

    # ASGITransport does not send lifespan events, so create the data dirs manually.
    for subdir in ("uploads", "outputs", "previews"):
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()
