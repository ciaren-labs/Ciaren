import json

import pytest

from app.cli import main

VALID = {
    "schemaVersion": "1.0.0",
    "project": {"name": "My Flow"},
    "graph": {
        "nodes": [{"id": "a", "type": "csvInput"}],
        "edges": [],
    },
}


def _write(tmp_path, data, name="flow.flow"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_flow_validate_ok(tmp_path, capsys):
    path = _write(tmp_path, VALID)
    main(["flow", "validate", str(path)])
    out = capsys.readouterr().out
    assert "OK" in out
    assert "1.0.0" in out


def test_flow_validate_json_output(tmp_path, capsys):
    path = _write(tmp_path, VALID)
    main(["flow", "validate", str(path), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"valid": True, "schemaVersion": "1.0.0"}


def test_flow_validate_invalid_exits_nonzero(tmp_path, capsys):
    bad = {
        "project": {"name": "x"},
        "graph": {"nodes": [{"id": "a", "type": "t"}], "edges": [{"id": "e", "source": "a", "target": "missing"}]},
    }
    path = _write(tmp_path, bad)
    with pytest.raises(SystemExit) as exc:
        main(["flow", "validate", str(path)])
    assert exc.value.code == 1
    assert "INVALID" in capsys.readouterr().out


def test_flow_validate_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        main(["flow", "validate", str(tmp_path / "nope.flow")])


def test_flow_validate_accepts_legacy_document(tmp_path, capsys):
    # Shape actually emitted today by POST /api/flows/{flow_id}/export/python
    # and accepted by POST /api/flows/import (see app/flow_schema/document.py's
    # module docstring on the legacy <-> versioned round trip).
    legacy = {
        "format": "ciaren.flow/v1",
        "name": "My Flow",
        "graph_json": {
            "nodes": [{"id": "a", "type": "csvInput"}],
            "edges": [],
        },
    }
    path = _write(tmp_path, legacy)
    main(["flow", "validate", str(path)])
    out = capsys.readouterr().out
    assert "OK" in out


def test_flow_validate_accepts_legacy_document_json_output(tmp_path, capsys):
    legacy = {
        "format": "ciaren.flow/v1",
        "name": "My Flow",
        "graph_json": {"nodes": [], "edges": []},
    }
    path = _write(tmp_path, legacy)
    main(["flow", "validate", str(path), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True


def test_flow_migrate_noop_prints_document(tmp_path, capsys):
    path = _write(tmp_path, VALID)
    main(["flow", "migrate", str(path)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "1.0.0"


def test_flow_migrate_write_keeps_backup(tmp_path, capsys):
    path = _write(tmp_path, VALID)
    main(["flow", "migrate", str(path), "--write"])
    backup = path.with_suffix(path.suffix + ".bak")
    assert backup.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == "1.0.0"
    assert "backup" in capsys.readouterr().out
