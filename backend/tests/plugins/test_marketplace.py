"""The marketplace index data contract: parse, find, search."""

from __future__ import annotations

import json

from app.plugins.marketplace import load_index, parse_index

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
            "downloadUrl": "https://example/acme-databricks-1.2.0.ffplugin",
            "keyId": "acme-key",
            "licenseRequired": True,
        },
        {
            "id": "community.hello",
            "name": "Hello Plugin",
            "version": "0.1.0",
            "description": "A friendly greeting node.",
            "capabilities": ["node.hello"],
        },
    ],
}


def test_parse_index_aliases():
    index = parse_index(_INDEX)
    entry = index.find("acme.databricks")
    assert entry is not None
    assert entry.download_url.endswith(".ffplugin")
    assert entry.key_id == "acme-key"
    assert entry.license_required is True
    assert entry.permissions == ["network", "credentials"]


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
