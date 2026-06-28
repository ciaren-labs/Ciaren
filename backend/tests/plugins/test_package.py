""".ffplugin packaging, digest determinism, and signature verification."""

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
    (src / "flowframe-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (src / "pkg_plugin.py").write_text("# plugin module\nPkgPlugin = object\n", encoding="utf-8")
    return src


def test_pack_directory_creates_readable_package(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ffplugin")
    assert pkg.is_file()
    manifest = package.read_manifest(pkg)
    assert manifest.id == "community.pkg"
    assert package.read_signature(pkg) is None  # unsigned


def test_pack_refuses_dir_without_manifest(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(package.PackageError):
        package.pack_directory(tmp_path / "empty", tmp_path / "out.ffplugin")


def test_digest_is_deterministic(plugin_src, tmp_path):
    a = package.pack_directory(plugin_src, tmp_path / "a.ffplugin")
    b = package.pack_directory(plugin_src, tmp_path / "b.ffplugin")
    assert package.compute_package_digest(a) == package.compute_package_digest(b)


def test_verify_unsigned_package(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ffplugin")
    result = package.verify_package(pkg, trusted_keys={})
    assert result.outcome == "unsigned"
    assert result.ok is True  # unsigned is acceptable (installer may still require trusted)


def test_read_manifest_rejects_non_zip(tmp_path):
    bogus = tmp_path / "bad.ffplugin"
    bogus.write_text("not a zip", encoding="utf-8")
    with pytest.raises(package.PackageError):
        package.read_manifest(bogus)


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_sign_then_verify_trusted(plugin_src, tmp_path):
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ffplugin")
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
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ffplugin")
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
    pkg = package.pack_directory(plugin_src, tmp_path / "out.ffplugin")
    priv, _ = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="kid-1")
    # Trust kid-1 but map it to a DIFFERENT public key → signature won't verify.
    _, other_pub = signing.generate_keypair()
    result = package.verify_package(pkg, trusted_keys={"kid-1": other_pub})
    assert result.outcome == "invalid"
