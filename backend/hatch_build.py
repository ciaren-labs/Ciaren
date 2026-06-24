"""Hatchling build hook: bundle the built web UI into the wheel.

Runs only for the ``wheel`` target (not editable installs), so a regular
``pip install flowframe`` ships the frontend and ``flowframe serve`` serves it
with no Node on the user's machine. Editable/dev installs skip this and fall back
to serving the live ``frontend/dist`` (see app.main.frontend_dist_path).

The frontend must be built first (``npm run build`` in ``frontend/``). If a build
isn't present and npm is available, the hook builds it; otherwise it warns and the
wheel ships API-only.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBundleHook(BuildHookInterface):
    PLUGIN_NAME = "frontend-bundle"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        frontend = root.parent / "frontend"
        dist = frontend / "dist"
        target = root / "app" / "web"

        if not dist.is_dir():
            self._build_frontend(frontend)

        if not (dist / "index.html").is_file():
            self.app.display_warning(
                "frontend/dist not found — building wheel without the web UI "
                "(it will serve API-only). Run `npm run build` in frontend/ first."
            )
            return

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(dist, target)
        # Include the generated (VCS-ignored) files in the wheel.
        build_data.setdefault("artifacts", []).append("app/web/**")
        self.app.display_info(f"Bundled web UI into {target.relative_to(root)}")

    def _build_frontend(self, frontend: Path) -> None:
        if not frontend.is_dir():
            return
        npm = shutil.which("npm")
        if npm is None:
            self.app.display_warning("npm not found; cannot build the frontend.")
            return
        self.app.display_info("Building frontend (npm ci && npm run build)…")
        subprocess.run([npm, "ci"], cwd=frontend, check=True)
        subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
