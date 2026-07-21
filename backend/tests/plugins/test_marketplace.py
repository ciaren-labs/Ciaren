"""The marketplace index data contract: parse, find, search, schema gate, revocation."""

from __future__ import annotations

import json

import pytest

from app.plugins.marketplace import (
    MarketplaceEntry,
    MarketplaceIndexError,
    configured_index_is_trusted,
    load_index,
    parse_index,
    resolve_artifact_path,
)

_INDEX = {
    "schemaVersion": "1.0.0",
    "plugins": [
        {
            "id": "acme.databricks",
            "name": "Databricks Connector",
            "version": "1.2.0",
            "publisher": "acme",
            "description": "Read and write Delta tables.",
            "license": "commercial",
            "capabilities": ["connector.databricks"],
            "permissions": ["network", "credentials"],
            "downloadUrl": "https://example/acme-databricks-1.2.0.ciarenplugin",
            "keyId": "acme-key",
            "licenseRequired": True,
        },
        {
            "id": "community.hello",
            "name": "Hello Plugin",
            "version": "0.1.0",
            "description": "A friendly greeting node.",
            "capabilities": ["node.hello"],
            "nodes": ["hello.greeting"],
            "nodeCategories": {"hello.greeting": "columns"},
        },
    ],
}


def test_parse_index_aliases():
    index = parse_index(_INDEX)
    entry = index.find("acme.databricks")
    assert entry is not None
    assert entry.download_url.endswith(".ciarenplugin")
    assert entry.key_id == "acme-key"
    assert entry.license_required is True
    assert entry.permissions == ["network", "credentials"]
    hello = parse_index(_INDEX).find("community.hello")
    assert hello is not None
    assert hello.nodes == ["hello.greeting"]
    assert hello.node_categories == {"hello.greeting": "columns"}


def test_find_missing_returns_none():
    assert parse_index(_INDEX).find("nope") is None


def test_search_by_name_and_capability():
    index = parse_index(_INDEX)
    assert [e.id for e in index.search("databricks")] == ["acme.databricks"]
    assert [e.id for e in index.search("connector.databricks")] == ["acme.databricks"]
    assert {e.id for e in index.search("")} == {"acme.databricks", "community.hello"}


def test_search_is_case_insensitive():
    assert [e.id for e in parse_index(_INDEX).search("HELLO")] == ["community.hello"]


def test_load_index_from_file(tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps(_INDEX), encoding="utf-8")
    index = load_index(path)
    assert len(index.plugins) == 2
    assert index.schema_version == "1.0.0"


def test_minor_schema_bump_is_accepted():
    # Additive (minor) changes parse fine; unknown fields are ignored by pydantic.
    index = parse_index({**_INDEX, "schemaVersion": "1.7.0", "futureField": True})
    assert len(index.plugins) == 2


@pytest.mark.parametrize("version", ["2.0.0", "0.9.0", "banana"])
def test_incompatible_or_malformed_schema_is_refused(version):
    with pytest.raises(MarketplaceIndexError, match="schemaVersion"):
        parse_index({**_INDEX, "schemaVersion": version})


def test_revoked_ids_parse_and_answer():
    index = parse_index({**_INDEX, "revoked": ["acme.databricks", "gone.plugin"]})
    assert index.is_revoked("acme.databricks") is True
    # Revocation works even for an id no longer listed in plugins.
    assert index.is_revoked("gone.plugin") is True
    assert index.is_revoked("community.hello") is False


# -- resolve_artifact_path confinement ----------------------------------------


def _entry(download_url: str) -> MarketplaceEntry:
    return MarketplaceEntry(id="x.plugin", name="X", download_url=download_url)


def test_resolve_artifact_path_untrusted_rejects_file_urls_absolute_and_traversal(tmp_path):
    """A malicious hosted index must not be able to point a "package" at local
    files: file: URLs, absolute paths, and any .. component all resolve to None."""
    index_path = tmp_path / "market" / "index.json"
    outside = tmp_path / "outside.ciarenplugin"  # absolute, exists outside the index dir
    outside.write_bytes(b"victim")
    for url in (
        "file:///etc/passwd",
        "file://C:/Windows/win.ini",
        "FILE:///etc/passwd",
        str(outside),
        "/etc/passwd",
        "../outside.ciarenplugin",
        "../../secrets/id_rsa",
        "pkgs/../../outside.ciarenplugin",
        "..",
    ):
        assert resolve_artifact_path(_entry(url), index_path, trusted=False) is None, url


def test_resolve_artifact_path_untrusted_allows_confined_relative(tmp_path):
    """A legitimate relative artifact under the index directory still resolves
    for an untrusted source (no false rejection, including nested dirs)."""
    market = tmp_path / "market"
    (market / "pkgs").mkdir(parents=True)
    artifact = market / "pkgs" / "x.plugin-1.0.0.ciarenplugin"
    artifact.write_bytes(b"pkg")
    resolved = resolve_artifact_path(_entry("pkgs/x.plugin-1.0.0.ciarenplugin"), market / "index.json", trusted=False)
    assert resolved is not None
    assert resolved == artifact.resolve()
    assert resolved.is_file()


def test_resolve_artifact_path_trusted_keeps_local_index_contract(tmp_path):
    """A trusted local index (operator/bundle-controlled) keeps the authoring
    contract: absolute paths, file:// URLs, and index-relative paths resolve."""
    index_path = tmp_path / "index.json"
    absolute = tmp_path / "elsewhere" / "x.ciarenplugin"
    assert resolve_artifact_path(_entry(str(absolute)), index_path, trusted=True) == absolute
    relative = resolve_artifact_path(_entry("rel/x.ciarenplugin"), index_path, trusted=True)
    assert relative == tmp_path / "rel" / "x.ciarenplugin"
    via_file_url = resolve_artifact_path(_entry(f"file://{absolute.as_posix()}"), index_path, trusted=True)
    assert via_file_url is not None and via_file_url.name == "x.ciarenplugin"


@pytest.mark.parametrize("trusted", [True, False])
@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://example.com/x.ciarenplugin",
        "https://example.com/x.ciarenplugin",
        "HTTP://example.com/x.ciarenplugin",  # scheme match is case-insensitive
        "HTTPS://example.com/x.ciarenplugin",
    ],
)
def test_resolve_artifact_path_remote_or_empty_is_none(tmp_path, trusted, url):
    assert resolve_artifact_path(_entry(url), tmp_path / "index.json", trusted=trusted) is None


# -- configured_index_is_trusted -----------------------------------------------


@pytest.mark.parametrize(
    ("configured", "trusted"),
    [
        ("http://host/i.json", False),
        ("https://host/i.json", False),
        ("HTTPS://host/i.json", False),  # scheme check is case-insensitive
        ("file:///opt/ciaren/index.json", False),
        ("ftp://host/i.json", False),  # any future scheme:// stays untrusted
        ("/opt/ciaren/index.json", True),
        ("C:\\ciaren\\index.json", True),  # Windows drive path is not a URL
        ("", True),  # empty -> bundled local fallback stays trusted
        (None, True),  # env var absent entirely -> bundled fallback
    ],
)
def test_configured_index_is_trusted_only_for_local_non_url_sources(monkeypatch, configured, trusted):
    """Trust is by inclusion: any ``scheme://`` form (http, https, file, ftp,
    any case) is untrusted; only a bare local path or the unset/empty default
    (the bundled local index) is trusted."""
    from app.core.config import get_settings

    if configured is None:
        monkeypatch.delenv("CIAREN_MARKETPLACE_INDEX", raising=False)
    else:
        monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", configured)
    get_settings.cache_clear()
    try:
        assert configured_index_is_trusted() is trusted
    finally:
        get_settings.cache_clear()
