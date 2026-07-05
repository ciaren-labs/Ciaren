"""An in-memory fake of the `keyring` package for tests, so the suite never
touches the real OS keychain. Install it with :func:`install_fake_keyring`."""

from __future__ import annotations

import sys
import types
from typing import Any


class PasswordDeleteError(Exception):
    pass


class _FakeBackend:
    """Stands in for a real, usable keyring backend."""


class _FailBackend:
    """Mirror of keyring.backends.fail.Keyring — a host with no usable keychain."""


def install_fake_keyring(monkeypatch, store: dict[str, str] | None = None, *, available: bool = True) -> dict[str, str]:
    """Inject a fake `keyring` (and its `errors` / `backends.fail` submodules)
    into sys.modules. Returns the backing store so a test can assert on it."""
    data = {} if store is None else store

    keyring = types.ModuleType("keyring")
    errors = types.ModuleType("keyring.errors")
    backends = types.ModuleType("keyring.backends")
    fail = types.ModuleType("keyring.backends.fail")

    errors.PasswordDeleteError = PasswordDeleteError  # type: ignore[attr-defined]
    fail.Keyring = _FailBackend  # type: ignore[attr-defined]

    def get_password(service: str, name: str) -> str | None:
        return data.get(f"{service}\x00{name}")

    def set_password(service: str, name: str, value: str) -> None:
        data[f"{service}\x00{name}"] = value

    def delete_password(service: str, name: str) -> None:
        key = f"{service}\x00{name}"
        if key not in data:
            raise PasswordDeleteError(name)
        del data[key]

    def get_keyring() -> Any:
        return (_FakeBackend if available else _FailBackend)()

    keyring.get_password = get_password  # type: ignore[attr-defined]
    keyring.set_password = set_password  # type: ignore[attr-defined]
    keyring.delete_password = delete_password  # type: ignore[attr-defined]
    keyring.get_keyring = get_keyring  # type: ignore[attr-defined]
    keyring.errors = errors  # type: ignore[attr-defined]
    keyring.backends = backends  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "keyring", keyring)
    monkeypatch.setitem(sys.modules, "keyring.errors", errors)
    monkeypatch.setitem(sys.modules, "keyring.backends", backends)
    monkeypatch.setitem(sys.modules, "keyring.backends.fail", fail)
    return data
