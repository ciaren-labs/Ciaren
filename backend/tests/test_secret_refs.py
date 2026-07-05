"""Secret references (app/core/secrets.py): env / keyring / file schemes.

The keyring tests stub ``sys.modules["keyring"]`` so they run without the
optional package or a real OS keychain.
"""

import sys
import types

import pytest

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.secrets import (
    KEYRING_SERVICE,
    ensure_permitted_secret_ref,
    parse_secret_ref,
    resolve_secret,
)

# -- parsing ------------------------------------------------------------------


def test_bare_name_parses_as_env():
    assert parse_secret_ref("PG_PASSWORD") == ("env", "PG_PASSWORD")


def test_scheme_refs_parse():
    assert parse_secret_ref("env:PG_PASSWORD") == ("env", "PG_PASSWORD")
    assert parse_secret_ref("keyring:pg-main") == ("keyring", "pg-main")
    assert parse_secret_ref("file:/run/secrets/pg") == ("file", "/run/secrets/pg")
    # Windows drive letters survive the scheme split.
    assert parse_secret_ref("file:C:/secrets/pg") == ("file", "C:/secrets/pg")


def test_invalid_refs_rejected():
    for bad in ["has-dash", "has space", "1DIGIT", "vault:pg", "env:9X", "keyring:bad name", "file:", "keyring:"]:
        with pytest.raises(ValidationError):
            parse_secret_ref(bad)


# -- env scheme ---------------------------------------------------------------


def test_resolve_env(monkeypatch):
    monkeypatch.setenv("MY_TEST_SECRET", "s3cret")
    assert resolve_secret("MY_TEST_SECRET") == "s3cret"
    assert resolve_secret("env:MY_TEST_SECRET") == "s3cret"


def test_resolve_env_unset_is_clear_error(monkeypatch):
    monkeypatch.delenv("MY_UNSET_SECRET", raising=False)
    with pytest.raises(ValidationError, match="MY_UNSET_SECRET"):
        resolve_secret("MY_UNSET_SECRET")


def test_app_config_vars_refused_in_both_forms(monkeypatch):
    monkeypatch.setenv("CIAREN_API_TOKEN", "token")
    for ref in ["CIAREN_API_TOKEN", "env:CIAREN_API_TOKEN", "env:ciaren_api_token"]:
        with pytest.raises(ValidationError, match="own configuration"):
            resolve_secret(ref)


def test_env_allowlist_applies_to_env_scheme_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "SECRET_ENV_ALLOWLIST", ["PG_*"])
    with pytest.raises(ValidationError, match="allowlist"):
        ensure_permitted_secret_ref("env:OTHER_SECRET")
    ensure_permitted_secret_ref("env:PG_PASSWORD")  # allowed
    ensure_permitted_secret_ref("keyring:other-secret")  # keyring is not env-gated


# -- file scheme --------------------------------------------------------------


def test_file_ref_reads_within_allowed_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(tmp_path)])
    secret = tmp_path / "pg_password"
    secret.write_text("hunter2\n", encoding="utf-8")
    assert resolve_secret(f"file:{secret}") == "hunter2"  # trailing newline stripped


def test_file_ref_outside_allowed_dirs_refused(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(allowed)])
    with pytest.raises(ValidationError, match="allowed secrets folders"):
        resolve_secret(f"file:{outside}")


def test_file_ref_confined_even_without_config(monkeypatch, tmp_path):
    """No SECRET_FILE_DIRS still confines to the defaults — there is no
    unrestricted mode for file references."""
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [])
    outside = tmp_path / "anywhere.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(ValidationError, match="allowed secrets folders"):
        resolve_secret(f"file:{outside}")


def test_file_ref_missing_file_is_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(tmp_path)])
    with pytest.raises(ValidationError, match="does not exist"):
        resolve_secret(f"file:{tmp_path / 'absent'}")


def test_file_ref_dotdot_traversal_refused(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (tmp_path / "outside.txt").write_text("nope", encoding="utf-8")
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(allowed)])
    with pytest.raises(ValidationError, match="allowed secrets folders"):
        resolve_secret(f"file:{allowed / '..' / 'outside.txt'}")


def test_file_ref_to_the_directory_itself_is_read_error_not_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(tmp_path)])
    with pytest.raises(ValidationError, match="could not be read|does not exist"):
        resolve_secret(f"file:{tmp_path}")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privilege on Windows")
def test_file_ref_symlink_escape_refused(monkeypatch, tmp_path):
    """A symlink inside the secrets dir pointing outside resolves to its real
    target, which fails confinement."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("nope", encoding="utf-8")
    (allowed / "link").symlink_to(target)
    monkeypatch.setattr(get_settings(), "SECRET_FILE_DIRS", [str(allowed)])
    with pytest.raises(ValidationError, match="allowed secrets folders"):
        resolve_secret(f"file:{allowed / 'link'}")


# -- keyring scheme -----------------------------------------------------------


def _stub_keyring(monkeypatch, store: dict[str, str]):
    stub = types.ModuleType("keyring")
    stub.get_password = lambda service, name: store.get(name) if service == KEYRING_SERVICE else None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", stub)


def test_keyring_ref_resolves(monkeypatch):
    _stub_keyring(monkeypatch, {"pg-main": "hunter2"})
    assert resolve_secret("keyring:pg-main") == "hunter2"


def test_keyring_missing_entry_is_clear_error(monkeypatch):
    _stub_keyring(monkeypatch, {})
    with pytest.raises(ValidationError, match="ciaren secret set absent"):
        resolve_secret("keyring:absent")


def test_keyring_package_missing_gives_install_hint(monkeypatch):
    """keyring is a core dependency, but a broken install must still fail with a
    clear message, not an ImportError traceback."""
    monkeypatch.setitem(sys.modules, "keyring", None)  # import keyring -> ImportError
    with pytest.raises(ValidationError, match="keyring.*missing"):
        resolve_secret("keyring:pg-main")
