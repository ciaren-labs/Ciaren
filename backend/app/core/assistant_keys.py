# SPDX-License-Identifier: AGPL-3.0-only
"""Installation-scoped OS keychain or one explicit operator-managed source."""

import os
import stat
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pydantic import SecretStr

from app.core.assistant_profiles import Provider
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.secrets import MAX_KEYRING_SECRET_BYTES


def source(provider: Provider) -> str:
    return str(getattr(get_settings(), f"ASSISTANT_{provider.upper()}_KEY_SOURCE"))


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


def read_key(provider: Provider) -> SecretStr | None:
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
            case "keyring":
                value = _backend().get_password(_service(), provider)
            case _:
                raise ValueError("Unsupported source")
        return SecretStr(value) if value else None
    except Exception:
        raise ValidationError("Assistant credential source unavailable. Check the server configuration.") from None


def write_key(provider: Provider, key: SecretStr | None) -> None:
    if source(provider) != "keyring":
        raise ValidationError("Rotate this credential at its configured server source.")
    try:
        backend = _backend()
        if key is None:
            if backend.get_password(_service(), provider) is not None:
                backend.delete_password(_service(), provider)
        else:
            value = key.get_secret_value()
            if (
                not value.strip()
                or len(value.encode()) > MAX_KEYRING_SECRET_BYTES
                or not value.isascii()
                or not value.isprintable()
            ):
                raise ValueError("Invalid credential")
            backend.set_password(_service(), provider, value)
    except Exception:
        raise ValidationError("Credential update failed. Check the API key and secure OS keychain.") from None
