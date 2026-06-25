"""Live round-trip tests for the MongoDB connector.

These exercise the real pymongo code path (``app/connectors/mongo.py``) against a
running MongoDB — the official ``mongo`` service container in CI (see
``.github/workflows/connectors-integration.yml``), or a local instance.

The whole module self-skips unless ``FLOWFRAME_TEST_MONGO_HOST`` is set, so the
default infra-free suite is unaffected. To run locally::

    FLOWFRAME_TEST_MONGO_HOST=127.0.0.1 \\
        pytest tests/integration/test_mongo_connector.py -m connectors
"""

from __future__ import annotations

import os
import uuid

import pandas as pd
import pytest

from app.connectors.base import ConnectionSpec, ConnectorError

pytestmark = pytest.mark.connectors

_HOST = os.environ.get("FLOWFRAME_TEST_MONGO_HOST")
_PORT = int(os.environ.get("FLOWFRAME_TEST_MONGO_PORT", "27017"))
_USER = os.environ.get("FLOWFRAME_TEST_MONGO_USER") or None
_PASSWORD = os.environ.get("FLOWFRAME_TEST_MONGO_PASSWORD") or None

if not _HOST:
    pytest.skip(
        "FLOWFRAME_TEST_MONGO_HOST not set; skipping live MongoDB connector tests.",
        allow_module_level=True,
    )

pymongo = pytest.importorskip("pymongo", reason="pymongo not installed (pip install flowframe[mongo])")


def _spec(database: str) -> ConnectionSpec:
    return ConnectionSpec(
        provider="mongodb",
        host=_HOST,
        port=_PORT,
        database=database,
        username=_USER,
        password=_PASSWORD,
    )


@pytest.fixture
def database():
    """A unique database name, dropped after the test so runs don't collide."""
    name = f"flowframe_test_{uuid.uuid4().hex[:12]}"
    client = pymongo.MongoClient(
        host=_HOST,
        port=_PORT,
        username=_USER,
        password=_PASSWORD,
        authSource="admin" if _USER else name,
        serverSelectionTimeoutMS=5000,
    )
    try:
        yield name
    finally:
        try:
            client.drop_database(name)
        finally:
            client.close()


@pytest.fixture
def connector():
    from app.connectors.mongo import MongoConnector

    return MongoConnector()


def test_test_connection_succeeds(connector, database):
    # Should not raise against a reachable server.
    connector.test_connection(_spec(database))


def test_test_connection_fails_on_unreachable_server(connector):
    spec = _spec("anything")
    spec.port = 1  # nothing listens here; pymongo times out and we wrap the error
    with pytest.raises(ConnectorError):
        connector.test_connection(spec)


def test_write_then_read_round_trip(connector, database):
    spec = _spec(database)
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})

    connector.write_table(spec, df, "people", None, "replace")
    out = connector.read_table(spec, "people", None, None)

    # Mongo assigns an ObjectId; read_table stringifies it into an `_id` column.
    assert "_id" in out.columns
    assert out["_id"].map(type).eq(str).all()
    data = out.drop(columns="_id").sort_values("a").reset_index(drop=True)
    assert data["a"].tolist() == [1, 2, 3]
    assert data["b"].tolist() == ["x", "y", "z"]


def test_list_tables_returns_written_collection(connector, database):
    spec = _spec(database)
    connector.write_table(spec, pd.DataFrame({"a": [1]}), "orders", None, "replace")

    names = [t.name for t in connector.list_tables(spec)]
    assert "orders" in names


def test_read_table_honors_limit(connector, database):
    spec = _spec(database)
    connector.write_table(spec, pd.DataFrame({"a": list(range(10))}), "nums", None, "replace")

    assert len(connector.read_table(spec, "nums", None, 4)) == 4


def test_write_fail_mode_rejects_non_empty_collection(connector, database):
    spec = _spec(database)
    df = pd.DataFrame({"a": [1]})
    connector.write_table(spec, df, "guarded", None, "replace")

    with pytest.raises(ConnectorError, match="already has documents"):
        connector.write_table(spec, df, "guarded", None, "fail")


def test_replace_mode_overwrites_existing(connector, database):
    spec = _spec(database)
    connector.write_table(spec, pd.DataFrame({"a": [1]}), "c", None, "replace")
    connector.write_table(spec, pd.DataFrame({"a": [1, 2, 3]}), "c", None, "replace")

    assert len(connector.read_table(spec, "c", None, None)) == 3


def test_append_mode_adds_documents(connector, database):
    spec = _spec(database)
    df = pd.DataFrame({"a": [1, 2]})
    connector.write_table(spec, df, "c", None, "replace")
    connector.write_table(spec, df, "c", None, "append")

    assert len(connector.read_table(spec, "c", None, None)) == 4


def test_read_table_rejects_bad_identifier(connector, database):
    with pytest.raises(ConnectorError):
        connector.read_table(_spec(database), "bad; drop", None, None)
