"""The server can also serve the built web UI (single-URL `ciaren serve`)."""

import mimetypes

import httpx
import pytest

from app.core.config import get_settings


def _clear() -> None:
    get_settings.cache_clear()


@pytest.fixture
def _restore_js_mime():
    """Snapshot/restore the global ``.js`` mimetype so a test can safely simulate a
    Windows registry that maps ``.js`` to ``text/plain`` without leaking to others."""
    saved = mimetypes.types_map.get(".js")
    try:
        yield
    finally:
        mimetypes.types_map.pop(".js", None)
        if saved is not None:
            mimetypes.add_type(saved, ".js")


def test_ensure_web_mime_types_overrides_registry_js_mapping(_restore_js_mime) -> None:
    # Simulate Windows, where the registry frequently maps .js -> text/plain and
    # browsers then refuse the module scripts (blank SPA).
    from app.main import _ensure_web_mime_types

    mimetypes.add_type("text/plain", ".js")
    assert mimetypes.guess_type("bundle.js")[0] == "text/plain"

    _ensure_web_mime_types()

    assert mimetypes.guess_type("bundle.js")[0] == "text/javascript"
    assert mimetypes.guess_type("index.mjs")[0] == "text/javascript"
    assert mimetypes.guess_type("styles.css")[0] == "text/css"


def test_frontend_dist_path_prefers_configured(tmp_path, monkeypatch) -> None:
    from app.main import frontend_dist_path

    (tmp_path / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setenv("CIAREN_FRONTEND_DIST", str(tmp_path))
    _clear()
    try:
        assert frontend_dist_path() == tmp_path
    finally:
        _clear()


def test_frontend_dist_path_falls_back_when_configured_invalid(tmp_path, monkeypatch) -> None:
    # A configured path without an index.html is skipped; resolution falls through
    # to the bundled/repo dist. Either a real dist is found, or None — never the
    # bogus configured path.
    from app.main import frontend_dist_path

    monkeypatch.setenv("CIAREN_FRONTEND_DIST", str(tmp_path / "does-not-exist"))
    _clear()
    try:
        resolved = frontend_dist_path()
        assert resolved != tmp_path / "does-not-exist"
        if resolved is not None:
            assert (resolved / "index.html").is_file()
    finally:
        _clear()


async def test_serves_spa_and_keeps_api_json_404(tmp_path, monkeypatch, _restore_js_mime) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("// bundle", encoding="utf-8")

    # Reproduce the Windows failure mode end-to-end: poison .js -> text/plain before
    # the app mounts its static handler. Serving the JS as text/plain is what makes
    # browsers refuse the module and render a blank page; the fix must override it.
    mimetypes.add_type("text/plain", ".js")

    monkeypatch.setenv("CIAREN_FRONTEND_DIST", str(dist))
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    _clear()
    try:
        from app.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # root serves the SPA shell
            root = await c.get("/")
            assert root.status_code == 200 and "id='root'" in root.text
            # client-side route falls back to index.html
            spa = await c.get("/flows/abc-123")
            assert spa.status_code == 200 and "id='root'" in spa.text
            # static asset is served with a JS content-type (not text/plain), so the
            # browser accepts it as a module script.
            asset = await c.get("/assets/app.js")
            assert asset.status_code == 200 and "bundle" in asset.text
            assert "javascript" in asset.headers["content-type"]
            # health + unknown API stay JSON (not the SPA shell)
            assert (await c.get("/health")).json() == {"status": "ok"}
            api404 = await c.get("/api/nope/x")
            assert api404.status_code == 404
            assert api404.json()["detail"]
    finally:
        _clear()


async def test_ready_reports_database_up() -> None:
    # Override the DB dependency with a fresh in-memory engine so the check is
    # deterministic regardless of the ambient DATABASE_URL.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.database import get_db
    from app.main import create_app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with maker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/ready")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok", "database": "up"}
    finally:
        await engine.dispose()


async def test_ready_returns_503_when_database_unreachable() -> None:
    from app.core.database import get_db
    from app.main import create_app

    class _BrokenSession:
        async def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("database unreachable")

    async def _override_get_db():
        yield _BrokenSession()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/ready")
        assert resp.status_code == 503
        assert resp.json() == {"status": "unavailable", "database": "down"}
