""".ciarenplugin packaging, digest determinism, and signature verification."""

from __future__ import annotations

import json
import zipfile

import pytest

from app.plugin_api import signing
from app.plugins import package

_HAS_CRYPTO = signing.signing_available()

_MANIFEST = {
    "id": "community.pkg",
    "name": "Pkg Plugin",
    "version": "1.0.0",
    "entrypoint": "pkg_plugin:PkgPlugin",
    "permissions": [],
}


@pytest.fixture
def plugin_src(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "ciaren-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (src / "pkg_plugin.py").write_text("# plugin module\nPkgPlugin = object\n", encoding="utf-8")
    return src


def test_pack_directory_creates_readable_package(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    assert pkg.is_file()
    manifest = package.read_manifest(pkg)
    assert manifest.id == "community.pkg"
    assert package.read_signature(pkg) is None  # unsigned


def test_pack_refuses_dir_without_manifest(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(package.PackageError):
        package.pack_directory(tmp_path / "empty", tmp_path / "out.ciarenplugin")


def test_digest_is_deterministic(plugin_src, tmp_path):
    a = package.pack_directory(plugin_src, tmp_path / "a.ciarenplugin")
    b = package.pack_directory(plugin_src, tmp_path / "b.ciarenplugin")
    assert package.compute_package_digest(a) == package.compute_package_digest(b)


def test_verify_unsigned_package(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    result = package.verify_package(pkg, trusted_keys={})
    assert result.outcome == "unsigned"
    assert result.ok is True  # unsigned is acceptable (installer may still require trusted)


def _add_entry(pkg, name, data):
    """Append a raw entry to an existing .ciarenplugin (repacking the zip)."""
    with zipfile.ZipFile(pkg) as zf:
        entries = [(n, zf.read(n)) for n in zf.namelist() if n != name]
    with zipfile.ZipFile(pkg, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, d in entries:
            zf.writestr(n, d)
        zf.writestr(name, data)


def test_malformed_signature_is_rejected_as_package_error(plugin_src, tmp_path):
    """A signature file that is not valid JSON (or not a valid signature schema)
    must surface as a clean PackageError, not an uncaught 500 from json/pydantic."""
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    _add_entry(pkg, package.SIGNATURE_FILENAME, "{not valid json")
    with pytest.raises(package.PackageError):
        package.read_signature(pkg)
    with pytest.raises(package.PackageError):
        package.verify_package(pkg, trusted_keys={})

    # Valid JSON but missing required fields is also a malformed signature.
    _add_entry(pkg, package.SIGNATURE_FILENAME, json.dumps({"algorithm": "ed25519"}))
    with pytest.raises(package.PackageError):
        package.verify_package(pkg, trusted_keys={})


def test_read_manifest_rejects_non_zip(tmp_path):
    bogus = tmp_path / "bad.ciarenplugin"
    bogus.write_text("not a zip", encoding="utf-8")
    with pytest.raises(package.PackageError):
        package.read_manifest(bogus)


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_sign_then_verify_trusted(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    priv, pub = signing.generate_keypair()
    sig = package.sign_package(pkg, priv, key_id="kid-1", publisher="acme")

    # Untrusted: signed but the key isn't in trusted set.
    untrusted = package.verify_package(pkg, trusted_keys={})
    assert untrusted.outcome == "untrusted"
    assert untrusted.ok is True

    # Trusted: key registered under its key_id.
    trusted = package.verify_package(pkg, trusted_keys={"kid-1": pub})
    assert trusted.outcome == "trusted"
    assert trusted.publisher == "acme"
    assert sig.digest == trusted.digest


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_tampered_package_is_invalid(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    priv, pub = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="kid-1")

    # Tamper: rewrite the archive with a modified file but keep the old signature.
    with zipfile.ZipFile(pkg) as zf:
        entries = {n: zf.read(n) for n in zf.namelist()}
    entries["pkg_plugin.py"] = b"# TAMPERED\n"
    with zipfile.ZipFile(pkg, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)

    result = package.verify_package(pkg, trusted_keys={"kid-1": pub})
    assert result.outcome == "invalid"
    assert result.ok is False


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_wrong_key_signature_is_invalid(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    priv, _ = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="kid-1")
    # Trust kid-1 but map it to a DIFFERENT public key → signature won't verify.
    _, other_pub = signing.generate_keypair()
    result = package.verify_package(pkg, trusted_keys={"kid-1": other_pub})
    assert result.outcome == "invalid"


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_publisher_is_not_a_trust_fallback(plugin_src, tmp_path):
    # Trust is keyed strictly by key_id; the attacker-controlled publisher name
    # must NOT select a trusted key (the removed fallback).
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    priv, pub = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="kid-1", publisher="acme")
    # The pub key is trusted only under the publisher name, never under key_id.
    result = package.verify_package(pkg, trusted_keys={"acme": pub})
    assert result.outcome == "untrusted"


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_relabelling_signer_metadata_breaks_signature(plugin_src, tmp_path):
    # The signature binds key_id/publisher, so taking a validly-signed package and
    # relabelling who signed it (to impersonate a trusted key) is rejected.
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ciarenplugin")
    priv, pub = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="real-kid", publisher="real")

    sig = package.read_signature(pkg)
    assert sig is not None
    forged = sig.model_copy(update={"key_id": "trusted-kid", "publisher": "official"})
    with zipfile.ZipFile(pkg) as zf:
        entries = {n: zf.read(n) for n in zf.namelist() if n != package.SIGNATURE_FILENAME}
    with zipfile.ZipFile(pkg, "w") as zf:
        for n, d in entries.items():
            zf.writestr(n, d)
        zf.writestr(package.SIGNATURE_FILENAME, forged.model_dump_json())

    # Even though the digest still matches, the signature no longer covers the
    # relabelled metadata, so verifying against the impersonated key fails.
    result = package.verify_package(pkg, trusted_keys={"trusted-kid": pub})
    assert result.outcome == "invalid"


def test_pack_compiled_ships_bytecode_not_source(tmp_path):
    src = tmp_path / "src"
    pkg_dir = src / "compiled_plugin"
    pkg_dir.mkdir(parents=True)
    (src / "ciaren-plugin.json").write_text(
        json.dumps({**_MANIFEST, "entrypoint": "compiled_plugin:CompiledPlugin"}), encoding="utf-8"
    )
    (pkg_dir / "__init__.py").write_text("from .impl import CompiledPlugin\n", encoding="utf-8")
    (pkg_dir / "impl.py").write_text("CompiledPlugin = object\n", encoding="utf-8")

    pkg = package.pack_directory(src, tmp_path / "out.ciarenplugin", compile_python=True)
    with zipfile.ZipFile(pkg) as zf:
        names = set(zf.namelist())
    # No .py source ships; the compiled .pyc takes its place at the import path.
    assert not any(n.endswith(".py") for n in names)
    assert "compiled_plugin/__init__.pyc" in names
    assert "compiled_plugin/impl.pyc" in names
    assert "ciaren-plugin.json" in names  # non-Python assets untouched


def test_pack_compiled_pyc_is_importable(tmp_path):
    # Install the compiled package and confirm Python imports the bare .pyc with no
    # source present — i.e. the loader's importlib path still works.
    import importlib
    import sys

    src = tmp_path / "src"
    pkg_dir = src / "byc_plugin"
    pkg_dir.mkdir(parents=True)
    (src / "ciaren-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (pkg_dir / "__init__.py").write_text("VALUE = 41\n", encoding="utf-8")
    (pkg_dir / "thing.py").write_text("def answer():\n    return 42\n", encoding="utf-8")

    pkg = package.pack_directory(src, tmp_path / "out.ciarenplugin", compile_python=True)
    install_root = tmp_path / "installed"
    install_root.mkdir()
    with zipfile.ZipFile(pkg) as zf:
        zf.extractall(install_root)

    sys.path.insert(0, str(install_root))
    try:
        mod = importlib.import_module("byc_plugin.thing")
        assert mod.answer() == 42
        assert importlib.import_module("byc_plugin").VALUE == 41
    finally:
        sys.path.remove(str(install_root))
        for name in [n for n in sys.modules if n.startswith("byc_plugin")]:
            del sys.modules[name]


def test_official_pinned_keys_cannot_be_overridden(monkeypatch, tmp_path):
    """A pinned official key is always present, and user config (env/file) can add
    keys but never replace an official key id — that's what a key-substitution
    attack would look like."""
    monkeypatch.setattr(package, "OFFICIAL_PUBLISHER_KEYS", {"ciaren-official": "aa" * 32})
    monkeypatch.setenv(
        package.TRUSTED_KEYS_ENV,
        json.dumps({"ciaren-official": "bb" * 32, "community-key": "cc" * 32}),
    )
    keys = package.load_trusted_keys()
    assert keys["ciaren-official"] == "aa" * 32  # pinned value wins
    assert keys["community-key"] == "cc" * 32  # additions still work
