"""Installing/uninstalling .ffplugin packages, with verification + zip-slip guard."""

from __future__ import annotations

import json
import zipfile

import pytest

from app.plugin_api import signing
from app.plugins import package
from app.plugins.install import (
    InstallError,
    install_directory,
    install_ffplugin,
    uninstall_plugin,
)

_HAS_CRYPTO = signing.signing_available()

_MANIFEST = {
    "id": "community.inst",
    "name": "Inst Plugin",
    "version": "1.0.0",
    "entrypoint": "inst_plugin:InstPlugin",
    "permissions": [],
}


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "flowframe-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (d / "inst_plugin.py").write_text("InstPlugin = object\n", encoding="utf-8")
    return d


def test_install_unsigned_then_uninstall(src, tmp_path):
    pkg = package.pack_directory(src, tmp_path / "p.ffplugin")
    install_dir = tmp_path / "installed"
    res = install_ffplugin(pkg, install_dir=install_dir)
    assert res.plugin_id == "community.inst"
    assert (res.location / "flowframe-plugin.json").is_file()
    assert (res.location / "inst_plugin.py").is_file()

    assert uninstall_plugin("community.inst", install_dir=install_dir) is True
    assert not res.location.exists()
    # Idempotent: uninstalling again reports nothing removed.
    assert uninstall_plugin("community.inst", install_dir=install_dir) is False


def test_install_refuses_existing_without_force(src, tmp_path):
    pkg = package.pack_directory(src, tmp_path / "p.ffplugin")
    install_dir = tmp_path / "installed"
    install_ffplugin(pkg, install_dir=install_dir)
    with pytest.raises(InstallError):
        install_ffplugin(pkg, install_dir=install_dir)
    # force overwrites.
    install_ffplugin(pkg, install_dir=install_dir, force=True)


def test_install_from_directory(src, tmp_path):
    install_dir = tmp_path / "installed"
    res = install_directory(src, install_dir=install_dir)
    assert (res.location / "inst_plugin.py").is_file()


def test_require_trusted_refuses_unsigned(src, tmp_path):
    pkg = package.pack_directory(src, tmp_path / "p.ffplugin")
    with pytest.raises(InstallError, match="trusted"):
        install_ffplugin(pkg, install_dir=tmp_path / "i", require_trusted=True)


def test_install_rejects_zip_slip(tmp_path):
    # Craft a malicious package with a path-traversal entry.
    pkg = tmp_path / "evil.ffplugin"
    with zipfile.ZipFile(pkg, "w") as zf:
        zf.writestr("flowframe-plugin.json", json.dumps(_MANIFEST))
        zf.writestr("../escape.py", "pwned = True\n")
    with pytest.raises(InstallError, match="unsafe path"):
        install_ffplugin(pkg, install_dir=tmp_path / "i")


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_install_trusted_signed_package(src, tmp_path):
    pkg = package.pack_directory(src, tmp_path / "p.ffplugin")
    priv, pub = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="kid-1", publisher="acme")
    res = install_ffplugin(
        pkg,
        install_dir=tmp_path / "i",
        require_trusted=True,
        trusted_keys={"kid-1": pub},
    )
    assert res.verification.outcome == "trusted"


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_install_refuses_tampered_package(src, tmp_path):
    pkg = package.pack_directory(src, tmp_path / "p.ffplugin")
    priv, _ = signing.generate_keypair()
    package.sign_package(pkg, priv, key_id="kid-1")
    with zipfile.ZipFile(pkg) as zf:
        entries = {n: zf.read(n) for n in zf.namelist()}
    entries["inst_plugin.py"] = b"# tampered\n"
    with zipfile.ZipFile(pkg, "w") as zf:
        for n, d in entries.items():
            zf.writestr(n, d)
    with pytest.raises(InstallError):
        install_ffplugin(pkg, install_dir=tmp_path / "i")
