# SPDX-License-Identifier: AGPL-3.0-only
"""Which provider, model and credential the assistant uses.

The active key saved on the Connections page wins: its secret lives in the OS
keychain under an installation-scoped service. Without one, an operator can
configure the provider in the environment and supply the key from an
environment variable or a mounted file.
"""

import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pydantic import SecretStr

from app.core.assistant_profiles import Provider
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.secrets import KEYRING_INSTALL_HINT, MAX_KEYRING_SECRET_BYTES


@dataclass(frozen=True)
class Selection:
    provider: Provider
    model: str
    effort: str
    # "local" for a key saved on the Connections page, else the operator source.
    source: str
    key_id: str | None = None
    name: str | None = None


# The active saved key, mirrored from the database at startup and on every change.
_local: Selection | None = None


def use_local(selection: Selection | None) -> None:
    global _local
    _local = selection


def source(provider: Provider) -> str:
    return str(getattr(get_settings(), f"ASSISTANT_{provider.upper()}_KEY_SOURCE"))


def selection() -> Selection | None:
    """The assistant's provider and model, or None when it is off."""
    cfg = get_settings()
    if not cfg.ASSISTANT_ENABLED:
        return None
    if _local is not None:
        return _local
    provider = cfg.ASSISTANT_PROVIDER
    if provider == "off":
        return None
    effort = getattr(cfg, f"ASSISTANT_{provider.upper()}_EFFORT", "default")
    return Selection(provider, getattr(cfg, f"ASSISTANT_{provider.upper()}_MODEL"), effort, source(provider))


def _service() -> str:
    root = str(Path(get_settings().DATA_DIR).resolve()).encode()
    return "ciaren-assistant-" + sha256(root).hexdigest()


def _backend() -> Any:
    import keyring

    backend = keyring.get_keyring()
    if type(backend).__module__ not in {
        "keyring.backends.SecretService",
        "keyring.backends.macOS",
        "keyring.backends.Windows",
    }:
        raise ValueError("Unsupported keychain")
    return backend


def keychain_status() -> str | None:
    """None when keys can be saved, else what the user must do first."""
    try:
        _backend()
    except ImportError:
        return KEYRING_INSTALL_HINT
    except Exception:
        return (
            "No supported OS keychain on this computer: Windows Credential Manager, macOS Keychain or Secret Service."
        )
    return None


def _account(key_id: str) -> str:
    return "key:" + key_id


def load_key(key_id: str) -> SecretStr | None:
    """The keychain secret of a saved key."""
    try:
        value = _backend().get_password(_service(), _account(key_id))
    except Exception:
        raise ValidationError("The OS keychain is unavailable. Unlock it and try again.") from None
    return SecretStr(value) if value else None


def credential(chosen: Selection) -> SecretStr | None:
    return load_key(chosen.key_id) if chosen.key_id is not None else read_key(chosen.provider)


def read_key(provider: Provider) -> SecretStr | None:
    """The operator-managed key of ``provider`` from its environment or file source."""
    settings = get_settings()
    try:
        match source(provider):
            case "env":
                return cast(SecretStr | None, getattr(settings, f"ASSISTANT_{provider.upper()}_API_KEY"))
            case "file":
                path = Path(settings.ASSISTANT_SECRET_DIR).resolve() / provider
                if path.is_symlink():
                    raise ValueError("Invalid mount")
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                with os.fdopen(os.open(path, flags), "rb") as file:
                    if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                        raise ValueError("Invalid secret file")
                    raw = file.read(MAX_KEYRING_SECRET_BYTES + 1)
                if len(raw) > MAX_KEYRING_SECRET_BYTES:
                    raise ValueError("Invalid mount")
                value = raw.decode().strip()
            case _:
                raise ValueError("Unsupported source")
        return SecretStr(value) if value else None
    except Exception:
        raise ValidationError("Assistant credential source unavailable. Check the server configuration.") from None


def store_key(key_id: str, key: SecretStr | None) -> None:
    """Save or, with None, delete the keychain secret of a saved key."""
    try:
        backend = _backend()
        if key is None:
            if backend.get_password(_service(), _account(key_id)) is not None:
                backend.delete_password(_service(), _account(key_id))
            return
        value = key.get_secret_value()
        if not value.strip() or len(value.encode()) > MAX_KEYRING_SECRET_BYTES:
            raise ValueError("Invalid credential")
        backend.set_password(_service(), _account(key_id), value)
    except Exception:
        raise ValidationError(
            "Could not save to the OS keychain. Unlock it, or install ciaren[keyring] on a supported system."
        ) from None
