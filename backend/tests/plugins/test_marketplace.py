"""The marketplace index data contract: parse, find, search, schema gate, revocation."""

from __future__ import annotations

import json

import pytest

from app.plugins.marketplace import MarketplaceIndexError, load_index, parse_index

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
