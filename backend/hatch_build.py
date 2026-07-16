"""Hatchling build hook: bundle the built web UI into the wheel.

Runs only for the ``wheel`` target (not editable installs), so a regular
``pip install ciaren`` ships the frontend and ``ciaren serve`` serves it
with no Node on the user's machine. Editable/dev installs skip this and fall back
to serving the live ``frontend/dist`` (see app.main.frontend_dist_path).

The frontend must be built first (``npm run build`` in ``frontend/``). If a build
isn't present and npm is available, the hook builds it. If the UI still is not
available, the wheel build fails: the published package promises that
``ciaren serve`` includes the web app.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBundleHook(BuildHookInterface):
    PLUGIN_NAME = "frontend-bundle"

    def initialize(self, version: str, build_data: dict) -> None:
        # Hatchling calls every wheel-target hook for both "standard" and "editable"
        # versions; editable installs (uv sync without --no-install-project) serve
        # frontend/dist directly (see app.main.frontend_dist_path) and never need this
        # bundling step, so skip it here rather than relying on the target alone.
        if version == "editable":
            return

        root = Path(self.root)
        frontend = self._frontend_dir(root)
        dist = frontend / "dist"
        target = root / "app" / "web"

        # Rebuild when dist is missing OR stale relative to the frontend source, so a
        # wheel never silently ships an out-of-date UI from a leftover local `dist`.
        # A clean CI checkout builds dist after checkout (fresh, not stale) and skips
        # the rebuild, so this stays cheap on the release path.
        if self._dist_is_stale(frontend, dist):
            self._build_frontend(frontend)

        if not (dist / "index.html").is_file():
            raise RuntimeError(
                "frontend/dist not found; refusing to build an API-only wheel. "
                "Run `npm ci && npm run build` in frontend/ first, or make npm "
                "available so the build hook can bundle the web UI."
            )

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(dist, target)
        # Include the generated (VCS-ignored) files in the wheel.
        build_data.setdefault("artifacts", []).append("app/web/**")
        self.app.display_info(f"Bundled web UI into {target.relative_to(root)}")

    def _dist_is_stale(self, frontend: Path, dist: Path) -> bool:
        """True if dist is missing, or any tracked frontend source is newer than the
        built index.html. Build inputs checked: package.json, the entry index.html,
        config files, and everything under src/ and public/."""
        index = dist / "index.html"
        if not index.is_file():
            return True
        built_at = index.stat().st_mtime
        inputs: list[Path] = [
            frontend / "package.json",
            frontend / "package-lock.json",
            frontend / "index.html",
        ]
        inputs.extend(frontend.glob("*.config.*"))
        inputs.extend(frontend.glob("tsconfig*.json"))
        for base in ("src", "public"):
            root = frontend / base
            if root.is_dir():
                inputs.extend(p for p in root.rglob("*") if p.is_file())
        return any(p.is_file() and p.stat().st_mtime > built_at for p in inputs)

    def _build_frontend(self, frontend: Path) -> None:
        if not frontend.is_dir():
            raise RuntimeError(f"frontend directory not found: {frontend}")
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("npm not found; cannot build the frontend for the wheel.")
        self.app.display_info("Building frontend (npm ci && npm run build)…")
        subprocess.run([npm, "ci"], cwd=frontend, check=True)
        subprocess.run([npm, "run", "build"], cwd=frontend, check=True)

    def _frontend_dir(self, root: Path) -> Path:
        """Frontend location in a source checkout or an unpacked sdist."""
        for candidate in (root.parent / "frontend", root / "frontend"):
            if candidate.is_dir():
                return candidate
        return root.parent / "frontend"
