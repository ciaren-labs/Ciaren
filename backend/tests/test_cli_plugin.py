"""CLI tests for `flowframe plugin` — pack/sign/verify/install/uninstall/keygen/search."""

from __future__ import annotations

import json

import pytest

from app.cli import main
from app.plugin_api import signing

_HAS_CRYPTO = signing.signing_available()

_MANIFEST = {
    "id": "community.cli",
    "name": "CLI Plugin",
    "version": "1.0.0",
    "entrypoint": "cli_plugin:CliPlugin",
    "permissions": [],
}


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "flowframe-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (d / "cli_plugin.py").write_text("CliPlugin = object\n", encoding="utf-8")
    return d


def test_pack_and_verify_unsigned(src, tmp_path, capsys):
    out = tmp_path / "p.ffplugin"
    main(["plugin", "pack", str(src), str(out)])
    assert out.is_file()
    capsys.readouterr()

    main(["plugin", "verify", str(out)])
    text = capsys.readouterr().out
    assert "community.cli" in text
    assert "unsigned" in text


def test_verify_json_output(src, tmp_path, capsys):
    out = tmp_path / "p.ffplugin"
    main(["plugin", "pack", str(src), str(out)])
    capsys.readouterr()
    main(["plugin", "verify", str(out), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "community.cli"
    assert payload["outcome"] == "unsigned"


def test_install_and_uninstall_dir(src, tmp_path, monkeypatch, capsys):
    install_dir = tmp_path / "installed"
    monkeypatch.setenv("FLOWFRAME_PLUGIN_INSTALL_DIR", str(install_dir))
    main(["plugin", "install", str(src), "--dir"])
    out = capsys.readouterr().out
    assert "Installed community.cli" in out
    assert (install_dir / "community.cli" / "cli_plugin.py").is_file()

    main(["plugin", "uninstall", "community.cli"])
    assert "Uninstalled community.cli" in capsys.readouterr().out
    assert not (install_dir / "community.cli").exists()


def test_search_local_index(tmp_path, capsys):
    index = {"plugins": [{"id": "acme.x", "name": "Acme X", "description": "does x"}]}
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    main(["plugin", "search", "acme", "--index", str(path)])
    assert "acme.x" in capsys.readouterr().out


def test_index_add_then_search(src, tmp_path, capsys):
    pkg = tmp_path / "p.ffplugin"
    main(["plugin", "pack", str(src), str(pkg)])
    capsys.readouterr()

    index = tmp_path / "index.json"
    main(["plugin", "index", "add", str(pkg), "--index", str(index)])
    out = capsys.readouterr().out
    assert "Added community.cli" in out
    assert index.is_file()

    # The package digest is recorded and the artifact is referenced relative to the
    # index file, so the entry is found by a subsequent search.
    payload = json.loads(index.read_text(encoding="utf-8"))
    entry = payload["plugins"][0]
    assert entry["id"] == "community.cli"
    assert entry["downloadUrl"] == "p.ffplugin"
    assert entry["digest"]

    main(["plugin", "search", "community", "--index", str(index)])
    assert "community.cli" in capsys.readouterr().out


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_keygen_pack_sign_verify_trusted(src, tmp_path, monkeypatch, capsys):
    # keygen
    main(["plugin", "keygen"])
    keygen_out = capsys.readouterr().out
    private_hex = next(line.split(":", 1)[1].strip() for line in keygen_out.splitlines() if "private_key" in line)
    public_hex = next(line.split(":", 1)[1].strip() for line in keygen_out.splitlines() if "public_key" in line)

    # pack + sign
    pkg = tmp_path / "p.ffplugin"
    main(["plugin", "pack", str(src), str(pkg)])
    capsys.readouterr()
    main(["plugin", "sign", str(pkg), "--key", private_hex, "--key-id", "kid-1", "--publisher", "acme"])
    assert "Signed" in capsys.readouterr().out

    # verify trusts the key via env
    monkeypatch.setenv("FLOWFRAME_TRUSTED_PLUGIN_KEYS", json.dumps({"kid-1": public_hex}))
    main(["plugin", "verify", str(pkg)])
    assert "trusted" in capsys.readouterr().out


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_install_trusted_only_rejects_unsigned(src, tmp_path, monkeypatch):
    pkg = tmp_path / "p.ffplugin"
    main(["plugin", "pack", str(src), str(pkg)])
    monkeypatch.setenv("FLOWFRAME_PLUGIN_INSTALL_DIR", str(tmp_path / "i"))
    with pytest.raises(SystemExit):
        main(["plugin", "install", str(pkg), "--trusted"])
