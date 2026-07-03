"""CLI tests for `ciaren-plugin` — pack/sign/verify/install/uninstall/keygen/search."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli_plugin import main
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
    (d / "ciaren-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (d / "cli_plugin.py").write_text("CliPlugin = object\n", encoding="utf-8")
    return d


def test_pack_and_verify_unsigned(src, tmp_path, capsys):
    out = tmp_path / "p.ciarenplugin"
    main(["pack", str(src), str(out)])
    assert out.is_file()
    capsys.readouterr()

    main(["verify", str(out)])
    text = capsys.readouterr().out
    assert "community.cli" in text
    assert "unsigned" in text


def test_verify_json_output(src, tmp_path, capsys):
    out = tmp_path / "p.ciarenplugin"
    main(["pack", str(src), str(out)])
    capsys.readouterr()
    main(["verify", str(out), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "community.cli"
    assert payload["outcome"] == "unsigned"


def test_install_and_uninstall_dir(src, tmp_path, monkeypatch, capsys):
    install_dir = tmp_path / "installed"
    monkeypatch.setenv("CIAREN_PLUGIN_INSTALL_DIR", str(install_dir))
    main(["install", str(src), "--dir"])
    out = capsys.readouterr().out
    assert "Installed community.cli" in out
    assert (install_dir / "community.cli" / "cli_plugin.py").is_file()

    main(["uninstall", "community.cli"])
    assert "Uninstalled community.cli" in capsys.readouterr().out
    assert not (install_dir / "community.cli").exists()


def test_search_local_index(tmp_path, capsys):
    index = {"plugins": [{"id": "acme.x", "name": "Acme X", "description": "does x"}]}
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    main(["search", "acme", "--index", str(path)])
    assert "acme.x" in capsys.readouterr().out


def test_index_add_then_search(src, tmp_path, capsys):
    pkg = tmp_path / "p.ciarenplugin"
    main(["pack", str(src), str(pkg)])
    capsys.readouterr()

    index = tmp_path / "index.json"
    main(["index", "add", str(pkg), "--index", str(index)])
    out = capsys.readouterr().out
    assert "Added community.cli" in out
    assert index.is_file()

    # The package digest is recorded and the artifact is referenced relative to the
    # index file, so the entry is found by a subsequent search.
    payload = json.loads(index.read_text(encoding="utf-8"))
    entry = payload["plugins"][0]
    assert entry["id"] == "community.cli"
    assert entry["downloadUrl"] == "p.ciarenplugin"
    assert entry["digest"]

    main(["search", "community", "--index", str(index)])
    assert "community.cli" in capsys.readouterr().out


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_keygen_pack_sign_verify_trusted(src, tmp_path, monkeypatch, capsys):
    # keygen
    main(["keygen"])
    keygen_out = capsys.readouterr().out
    private_hex = next(line.split(":", 1)[1].strip() for line in keygen_out.splitlines() if "private_key" in line)
    public_hex = next(line.split(":", 1)[1].strip() for line in keygen_out.splitlines() if "public_key" in line)

    # pack + sign
    pkg = tmp_path / "p.ciarenplugin"
    main(["pack", str(src), str(pkg)])
    capsys.readouterr()
    main(["sign", str(pkg), "--key", private_hex, "--key-id", "kid-1", "--publisher", "acme"])
    assert "Signed" in capsys.readouterr().out

    # verify trusts the key via env
    monkeypatch.setenv("CIAREN_TRUSTED_PLUGIN_KEYS", json.dumps({"kid-1": public_hex}))
    main(["verify", str(pkg)])
    assert "trusted" in capsys.readouterr().out


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_install_trusted_only_rejects_unsigned(src, tmp_path, monkeypatch):
    pkg = tmp_path / "p.ciarenplugin"
    main(["pack", str(src), str(pkg)])
    monkeypatch.setenv("CIAREN_PLUGIN_INSTALL_DIR", str(tmp_path / "i"))
    with pytest.raises(SystemExit):
        main(["install", str(pkg), "--trusted"])


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_license_issue_import_status_roundtrip(tmp_path, monkeypatch, capsys):
    # Isolate the license cache (LicenseCache defaults to ~/.ciaren/licenses).
    monkeypatch.setenv("HOME", str(tmp_path))
    main(["keygen"])
    keygen_out = capsys.readouterr().out
    priv = next(line.split(":", 1)[1].strip() for line in keygen_out.splitlines() if "private_key" in line)
    pub = next(line.split(":", 1)[1].strip() for line in keygen_out.splitlines() if "public_key" in line)

    token_path = tmp_path / "token.json"
    main(
        [
            "license",
            "issue",
            "--key",
            priv,
            "--user",
            "u-1",
            "--plugin",
            "acme.db",
            "--expires",
            "2099-01-01T00:00:00Z",
            "--grace",
            "2099-02-01T00:00:00Z",
            "--out",
            str(token_path),
        ]
    )
    assert token_path.is_file()
    capsys.readouterr()

    main(["license", "import", str(token_path)])
    assert "Imported license for acme.db" in capsys.readouterr().out

    main(["license", "status", "acme.db", "--key", pub])
    out = capsys.readouterr().out
    assert "valid — licensed" in out

    # A different key fails verification.
    main(["keygen"])
    other_lines = capsys.readouterr().out.splitlines()
    other_pub = next(line.split(":", 1)[1].strip() for line in other_lines if "public_key" in line)
    main(["license", "status", "acme.db", "--key", other_pub])
    assert "invalid" in capsys.readouterr().out


def test_license_status_without_cache(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    main(["license", "status", "nope.x"])
    assert "No cached license" in capsys.readouterr().out


# -- plugin manifest ----------------------------------------------------


def _hello_plugin_dir() -> Path:
    # examples/plugins lives at the repo root, two levels above backend/.
    return Path(__file__).resolve().parents[2] / "examples" / "plugins" / "hello-node-plugin"


def test_plugin_manifest_generates_from_code(capsys: pytest.CaptureFixture[str]) -> None:
    main(["manifest", str(_hello_plugin_dir()), "--out", "-"])
    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "community.hello"
    assert data["entrypoint"] == "ciaren_hello.plugin:HelloPlugin"
    assert data["ui"]["nodeCategories"] == {"hello.greeting": "columns"}


def test_plugin_manifest_writes_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    out = tmp_path / "generated.json"
    main(
        [
            "manifest",
            str(_hello_plugin_dir()),
            "--entrypoint",
            "ciaren_hello.plugin:HelloPlugin",
            "--out",
            str(out),
        ]
    )
    assert json.loads(out.read_text(encoding="utf-8"))["id"] == "community.hello"
    assert "Wrote" in capsys.readouterr().out
