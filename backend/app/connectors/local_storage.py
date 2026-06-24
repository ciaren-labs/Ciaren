"""Local-folder storage connector.

Treats a directory as an object store: files inside it are objects, the
directory path is the "bucket". No credentials are required. The folder is
created on first use if it doesn't exist yet.

This connector is always available (no optional dependency) and is seeded
as the built-in "Local Storage" connection at server startup.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec


def _read_text(path: Path) -> pd.DataFrame:
    """Read a plain-text file as a single-column DataFrame (one row per line)."""
    return pd.read_csv(path, sep="\n", header=None, names=["text"], engine="python", dtype=str)


def _read_json(path: Path) -> pd.DataFrame:
    return pd.read_json(path)


_READERS: dict[str, Callable[..., pd.DataFrame]] = {
    "csv": pd.read_csv,
    "excel": pd.read_excel,
    "parquet": pd.read_parquet,
    "json": _read_json,
    "text": _read_text,
}


class LocalStorageConnector:
    provider_kind = "storage"

    def _root(self, spec: StorageSpec) -> Path:
        return Path(spec.bucket).expanduser().resolve()

    def _safe_path(self, spec: StorageSpec, path: str) -> Path:
        """Resolve *path* relative to root and raise if it escapes the root dir."""
        root = self._root(spec)
        full = (root / path).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            raise ConnectorError(
                f"Path {path!r} escapes the storage root — directory traversal is not allowed."
            ) from None
        return full

    def test_connection(self, spec: StorageSpec) -> None:
        root = self._root(spec)
        if not root.exists():
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ConnectorError(f"Cannot create folder {root}: {exc}") from None
        if not root.is_dir():
            raise ConnectorError(f"{root} exists but is not a directory.")
        probe = root / ".ff_probe"
        try:
            probe.touch()
            probe.unlink()
        except OSError as exc:
            raise ConnectorError(f"Folder {root} is not writable: {exc}") from None

    def list_objects(self, spec: StorageSpec, prefix: str = "") -> list[str]:
        root = self._root(spec)
        if not root.exists():
            return []
        return sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_file() and (not prefix or p.relative_to(root).as_posix().startswith(prefix))
        )

    def read_file(self, spec: StorageSpec, path: str, fmt: str) -> pd.DataFrame:
        reader = _READERS.get(fmt)
        if reader is None:
            raise ConnectorError(f"Unsupported format {fmt!r}. Supported: csv, excel, parquet, json, text.")
        full = self._safe_path(spec, path)
        if not full.exists():
            raise ConnectorError(f"File not found: {full}")
        try:
            return reader(full)
        except Exception as exc:
            raise ConnectorError(f"Failed to read {full}: {exc}") from None

    def write_file(
        self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str
    ) -> None:
        full = self._safe_path(spec, path)
        full.parent.mkdir(parents=True, exist_ok=True)
        if full.exists() and if_exists == "error":
            raise ConnectorError(
                f"File already exists: {full}. Set 'if_exists' to 'overwrite' to replace it."
            )
        try:
            if fmt == "csv":
                df.to_csv(full, index=False)
            elif fmt == "excel":
                df.to_excel(full, index=False)
            elif fmt == "parquet":
                df.to_parquet(full, index=False)
            else:
                raise ConnectorError(f"Unsupported format {fmt!r}.")
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to write {full}: {exc}") from None
