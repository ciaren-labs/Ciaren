"""The server can also serve the built web UI (single-URL `flowframe serve`)."""
import httpx

from app.core.config import get_settings


def _clear() -> None:
    get_settings.cache_clear()


def test_frontend_dist_path_prefers_configured(tmp_path, monkeypatch) -> None:
    from app.main import frontend_dist_path

    (tmp_path / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setenv("FLOWFRAME_FRONTEND_DIST", str(tmp_path))
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

    monkeypatch.setenv("FLOWFRAME_FRONTEND_DIST", str(tmp_path / "does-not-exist"))
    _clear()
    try:
        resolved = frontend_dist_path()
        assert resolved != tmp_path / "does-not-exist"
        if resolved is not None:
            assert (resolved / "index.html").is_file()
    finally:
        _clear()


async def test_serves_spa_and_keeps_api_json_404(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("// bundle", encoding="utf-8")

    monkeypatch.setenv("FLOWFRAME_FRONTEND_DIST", str(dist))
    monkeypatch.setenv("FLOWFRAME_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
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
            # static asset is served
            asset = await c.get("/assets/app.js")
            assert asset.status_code == 200 and "bundle" in asset.text
            # health + unknown API stay JSON (not the SPA shell)
            assert (await c.get("/health")).json() == {"status": "ok"}
            api404 = await c.get("/api/nope/x")
            assert api404.status_code == 404
            assert api404.json()["detail"]
    finally:
        _clear()
