# SPDX-License-Identifier: AGPL-3.0-only
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
from app.connectors.storage_base import FILE_FORMATS, StorageSpec


def _is_within(path: Path, base: Path) -> bool:
    """Whether *path* is contained in *base* (both already resolved)."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _read_text(path: Path) -> pd.DataFrame:
    """Read a plain-text file as a single-column DataFrame (one row per line).
    Uses splitlines() — newer pandas rejects sep="\\n"."""
    return pd.DataFrame({"text": path.read_text(encoding="utf-8").splitlines()})


def _read_json(path: Path) -> pd.DataFrame:
    return pd.read_json(path)


def _read_jsonl(path: Path) -> pd.DataFrame:
    return pd.read_json(path, lines=True)


def _read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t")


_READERS: dict[str, Callable[..., pd.DataFrame]] = {
    "csv": pd.read_csv,
    "tsv": _read_tsv,
    "excel": pd.read_excel,
    "parquet": pd.read_parquet,
    "json": _read_json,
    "jsonl": _read_jsonl,
    "text": _read_text,
}


def _allowed_roots() -> list[Path]:
    """Configured confinement directories for local storage, resolved absolute.
    Empty list means "no confinement" (the historical default)."""
    from app.core.config import get_settings

    roots: list[Path] = []
    for raw in get_settings().STORAGE_ALLOWED_ROOTS:
        raw = raw.strip()
        if raw:
            roots.append(Path(raw).expanduser().resolve())
    return roots


class LocalStorageConnector:
    provider_kind = "storage"

    def _root(self, spec: StorageSpec) -> Path:
        root = Path(spec.bucket).expanduser().resolve()
        allowed = _allowed_roots()
        if allowed and not any(root == base or _is_within(root, base) for base in allowed):
            raise ConnectorError(
                f"Storage folder {root} is outside the allowed roots "
                f"({', '.join(str(b) for b in allowed)}). "
                "Adjust CIAREN_STORAGE_ALLOWED_ROOTS or the connection folder."
            )
        return root

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

    def write_file(self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str) -> None:
        full = self._safe_path(spec, path)
        full.parent.mkdir(parents=True, exist_ok=True)
        if full.exists() and if_exists == "error":
            raise ConnectorError(f"File already exists: {full}. Set 'if_exists' to 'overwrite' to replace it.")
        try:
            if fmt == "csv":
                df.to_csv(full, index=False)
            elif fmt == "tsv":
                df.to_csv(full, index=False, sep="\t")
            elif fmt == "excel":
                df.to_excel(full, index=False)
            elif fmt == "parquet":
                df.to_parquet(full, index=False)
            elif fmt == "json":
                df.to_json(full, orient="records", indent=2)
            elif fmt == "jsonl":
                df.to_json(full, orient="records", lines=True)
            elif fmt == "text":
                df.to_csv(full, index=False, header=False, sep="\t")
            else:
                raise ConnectorError(f"Unsupported format {fmt!r}. Supported: {', '.join(FILE_FORMATS)}.")
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to write {full}: {exc}") from None
