import pytest

from app.flow_schema import (
    CURRENT_SCHEMA_VERSION,
    MigrationError,
    clear_migrations,
    migrate,
    register_migration,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_migrations()
    yield
    clear_migrations()


def test_noop_when_already_at_target():
    data = {"schemaVersion": CURRENT_SCHEMA_VERSION, "project": {"name": "x"}}
    out = migrate(data, target=CURRENT_SCHEMA_VERSION)
    assert out["schemaVersion"] == CURRENT_SCHEMA_VERSION


def test_single_migration_applied():
    def to_1_1(data):
        data["added"] = True
        return data

    register_migration("1.0.0", "1.1.0", to_1_1)
    out = migrate({"schemaVersion": "1.0.0"}, target="1.1.0")
    assert out["schemaVersion"] == "1.1.0"
    assert out["added"] is True


def test_migration_chain():
    register_migration("1.0.0", "1.1.0", lambda d: {**d, "a": 1})
    register_migration("1.1.0", "2.0.0", lambda d: {**d, "b": 2})
    out = migrate({"schemaVersion": "1.0.0"}, target="2.0.0")
    assert out["schemaVersion"] == "2.0.0"
    assert out["a"] == 1
    assert out["b"] == 2


def test_stops_at_intermediate_target():
    register_migration("1.0.0", "1.1.0", lambda d: {**d, "a": 1})
    register_migration("1.1.0", "2.0.0", lambda d: {**d, "b": 2})
    out = migrate({"schemaVersion": "1.0.0"}, target="1.1.0")
    assert out["schemaVersion"] == "1.1.0"
    assert "b" not in out


def test_error_when_no_path():
    with pytest.raises(MigrationError, match="no migration registered"):
        migrate({"schemaVersion": "1.0.0"}, target="9.9.9")


def test_error_when_document_newer_than_target():
    with pytest.raises(MigrationError, match="newer than target"):
        migrate({"schemaVersion": "2.0.0"}, target="1.0.0")


def test_duplicate_migration_registration_rejected():
    register_migration("1.0.0", "1.1.0", lambda d: d)
    with pytest.raises(ValueError, match="already registered"):
        register_migration("1.0.0", "1.2.0", lambda d: d)


def test_invalid_version_rejected():
    with pytest.raises(MigrationError, match="invalid schema version"):
        migrate({"schemaVersion": "not-a-version"}, target="1.0.0")
