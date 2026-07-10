"""OpenAPI contract guardrail — catches backend↔frontend schema drift.

``test_route_snapshot.py`` pins the set of ``METHOD /path`` pairs. This goes a
layer deeper and pins the *shapes*: every request/response DTO's fields and
types, plus which schema each operation accepts and returns. So a silently
renamed response field (the ``column_schema`` / ``data_sample`` alias class of
bug), a field flipping required↔optional, a changed type, or an endpoint quietly
switching its response model all fail CI as a reviewable diff of
``tests/openapi_snapshot.json`` — instead of surfacing as a runtime bug in the UI.

Descriptions, titles, examples and defaults are intentionally excluded: they are
documentation, not contract, and snapshotting them would bury real drift in noise.

To update after an intentional API change, regenerate the snapshot:

    CIAREN_UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/test_openapi_snapshot.py

and review the diff.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.main import app

_SNAPSHOT = Path(__file__).resolve().parent / "openapi_snapshot.json"


def _ref_name(ref: str) -> str:
    """``#/components/schemas/FlowRead`` -> ``#FlowRead``."""
    return "#" + ref.rsplit("/", 1)[-1]


def _type_sig(schema: dict[str, Any] | None) -> str:
    """A compact, deterministic signature of a JSON-schema fragment — enough to
    catch a type/ref/enum/shape change, without the documentation noise."""
    if not schema:
        return "any"
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    for combinator in ("anyOf", "oneOf", "allOf"):
        if combinator in schema:
            parts = sorted(_type_sig(s) for s in schema[combinator])
            return f"{combinator}(" + "|".join(parts) + ")"
    if "enum" in schema and schema.get("type") is None:
        # A typeless enum is still a real contract (its allowed values).
        values = ",".join(sorted(str(v) for v in schema["enum"]))
        return f"enum{{{values}}}"
    schema_type = schema.get("type")
    if schema_type == "array":
        return f"array<{_type_sig(schema.get('items'))}>"
    if schema_type == "object" or "additionalProperties" in schema:
        ap = schema.get("additionalProperties")
        if isinstance(ap, dict):
            return f"object<{_type_sig(ap)}>"
        if ap is False:
            return "object(closed)"  # extra="forbid" is part of the contract
        return "object"
    if schema_type is None:
        return "any"
    if "enum" in schema:
        values = ",".join(sorted(str(v) for v in schema["enum"]))
        return f"{schema_type}{{{values}}}"
    # ``format`` matters to a client (date-time vs plain string, uuid, binary).
    fmt = schema.get("format")
    return f"{schema_type}({fmt})" if fmt else str(schema_type)


def _schema_fingerprint(schema: dict[str, Any]) -> dict[str, Any]:
    """Field-level fingerprint of one component schema: required set + per-property
    type signature. Falls back to a whole-schema type sig for non-object schemas
    (e.g. a str enum defined at the top level)."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {"type": _type_sig(schema)}
    return {
        "required": sorted(schema.get("required", [])),
        "properties": {name: _type_sig(properties[name]) for name in sorted(properties)},
    }


def _deep_sig(schema: dict[str, Any] | None) -> Any:
    """Signature of a body schema: a ``$ref`` -> ``#Name``; an *inline* object with
    properties -> its field fingerprint (so multipart form fields are captured, not
    collapsed to a bare ``object``); anything else -> a scalar type sig."""
    if not schema:
        return "any"
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    if isinstance(schema.get("properties"), dict):
        return _schema_fingerprint(schema)
    return _type_sig(schema)


def _body(content: dict[str, Any] | None) -> dict[str, Any] | None:
    """Request/response body keyed by media type, so a ``multipart/form-data``
    upload's fields are guarded just like a JSON body's."""
    if not content:
        return None
    return {media_type: _deep_sig(content[media_type].get("schema")) for media_type in sorted(content)}


def _params(op: dict[str, Any]) -> list[dict[str, Any]]:
    """Query/path/header parameters — a renamed or newly-required query param is
    exactly the drift class this guard exists for, on the request side."""
    out = [
        {
            "name": p.get("name"),
            "in": p.get("in"),
            "required": bool(p.get("required", False)),
            "type": _type_sig(p.get("schema")),
        }
        for p in op.get("parameters", [])
        if isinstance(p, dict)
    ]
    return sorted(out, key=lambda d: (str(d["in"]), str(d["name"])))


def _contract(openapi: dict[str, Any]) -> dict[str, Any]:
    schemas = openapi.get("components", {}).get("schemas", {})
    schema_fps = {name: _schema_fingerprint(schemas[name]) for name in sorted(schemas)}

    operations: dict[str, Any] = {}
    for path in sorted(openapi.get("paths", {})):
        for method in sorted(openapi["paths"][path]):
            op = openapi["paths"][path][method]
            if not isinstance(op, dict):
                continue
            request = _body((op.get("requestBody") or {}).get("content"))
            responses = {
                code: _body((op["responses"][code] or {}).get("content")) for code in sorted(op.get("responses", {}))
            }
            operations[f"{method.upper()} {path}"] = {
                "parameters": _params(op),
                "request": request,
                "responses": responses,
            }

    return {"schemas": schema_fps, "operations": operations}


def _dump(contract: dict[str, Any]) -> str:
    return json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_openapi_contract_snapshot_matches() -> None:
    current = _contract(app.openapi())
    if os.getenv("CIAREN_UPDATE_OPENAPI_SNAPSHOT"):
        _SNAPSHOT.write_text(_dump(current), encoding="utf-8")
        return

    expected = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))

    added_schemas = sorted(set(current["schemas"]) - set(expected["schemas"]))
    removed_schemas = sorted(set(expected["schemas"]) - set(current["schemas"]))
    changed_schemas = sorted(
        name
        for name in set(current["schemas"]) & set(expected["schemas"])
        if current["schemas"][name] != expected["schemas"][name]
    )
    added_ops = sorted(set(current["operations"]) - set(expected["operations"]))
    removed_ops = sorted(set(expected["operations"]) - set(current["operations"]))
    changed_ops = sorted(
        op
        for op in set(current["operations"]) & set(expected["operations"])
        if current["operations"][op] != expected["operations"][op]
    )

    assert current == expected, (
        "OpenAPI contract changed.\n"
        f"  schemas   added:   {added_schemas}\n"
        f"  schemas   removed: {removed_schemas}\n"
        f"  schemas   changed: {changed_schemas}\n"
        f"  operations added:  {added_ops}\n"
        f"  operations removed:{removed_ops}\n"
        f"  operations changed:{changed_ops}\n"
        "If intentional, regenerate: CIAREN_UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/test_openapi_snapshot.py"
    )


# ---------------------------------------------------------------------------
# Fingerprint machinery — pure unit tests proving it has teeth
# ---------------------------------------------------------------------------


def test_type_sig_covers_the_shapes_that_matter() -> None:
    assert _type_sig(None) == "any"
    assert _type_sig({}) == "any"
    assert _type_sig({"type": "string"}) == "string"
    assert _type_sig({"$ref": "#/components/schemas/FlowRead"}) == "#FlowRead"
    assert _type_sig({"type": "array", "items": {"type": "string"}}) == "array<string>"
    assert _type_sig({"anyOf": [{"type": "string"}, {"type": "null"}]}) == "anyOf(null|string)"
    assert _type_sig({"type": "string", "enum": ["b", "a"]}) == "string{a,b}"  # sorted, order-stable
    assert _type_sig({"type": "object", "additionalProperties": {"type": "integer"}}) == "object<integer>"
    assert _type_sig({"type": "object"}) == "object"
    # format and closed-object are part of the contract, not noise.
    assert _type_sig({"type": "string", "format": "date-time"}) == "string(date-time)"
    assert _type_sig({"type": "object", "additionalProperties": False}) == "object(closed)"
    assert _type_sig({"enum": ["a", "b"]}) == "enum{a,b}"  # typeless enum still distinguished


def test_fingerprint_detects_field_rename() -> None:
    before = _schema_fingerprint({"properties": {"column_schema": {"type": "string"}}, "required": ["column_schema"]})
    after = _schema_fingerprint({"properties": {"schema": {"type": "string"}}, "required": ["schema"]})
    assert before != after  # the exact alias-drift bug class this guard exists for


def test_fingerprint_detects_type_and_required_changes() -> None:
    base = {"properties": {"n": {"type": "integer"}}, "required": ["n"]}
    type_changed = {"properties": {"n": {"type": "string"}}, "required": ["n"]}
    now_optional = {"properties": {"n": {"type": "integer"}}, "required": []}
    assert _schema_fingerprint(base) != _schema_fingerprint(type_changed)
    assert _schema_fingerprint(base) != _schema_fingerprint(now_optional)


def test_fingerprint_falls_back_for_non_object_schema() -> None:
    assert _schema_fingerprint({"type": "string", "enum": ["ok", "error"]}) == {"type": "string{error,ok}"}


def test_contract_detects_response_model_swap() -> None:
    def _api(ref: str) -> dict[str, Any]:
        return {
            "components": {"schemas": {}},
            "paths": {
                "/api/x": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": ref}}}}}}}
            },
        }

    before = _contract(_api("#/components/schemas/FlowRead"))
    after = _contract(_api("#/components/schemas/ProjectRead"))
    assert before["operations"]["GET /api/x"] != after["operations"]["GET /api/x"]


def test_contract_captures_query_parameters() -> None:
    def _api(required: bool) -> dict[str, Any]:
        return {
            "paths": {
                "/api/x": {
                    "get": {
                        "parameters": [
                            {"name": "category", "in": "query", "required": required, "schema": {"type": "string"}}
                        ],
                        "responses": {},
                    }
                }
            }
        }

    # A query param flipping optional->required is a breaking change and must show.
    assert _contract(_api(False))["operations"]["GET /api/x"] != _contract(_api(True))["operations"]["GET /api/x"]


def test_contract_captures_multipart_form_fields() -> None:
    def _api(field: str) -> dict[str, Any]:
        return {
            "paths": {
                "/api/x": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "schema": {"type": "object", "properties": {field: {"type": "string"}}}
                                }
                            }
                        },
                        "responses": {},
                    }
                }
            }
        }

    # Renaming a multipart form field (e.g. 'file') is the request-side alias drift.
    before = _contract(_api("file"))["operations"]["POST /api/x"]
    after = _contract(_api("upload"))["operations"]["POST /api/x"]
    assert before != after
    assert before["request"] == {"multipart/form-data": {"required": [], "properties": {"file": "string"}}}


def _collect_refs(obj: Any) -> set[str]:
    """Every ``#Schema`` reference anywhere in a contract fragment (strings, dicts, lists)."""
    if isinstance(obj, str):
        tokens = obj.replace("(", " ").replace(")", " ").replace("|", " ").replace("<", " ").replace(">", " ").split()
        return {tok[1:] for tok in tokens if tok.startswith("#")}
    if isinstance(obj, dict):
        return set().union(*(_collect_refs(v) for v in obj.values())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(_collect_refs(v) for v in obj)) if obj else set()
    return set()


def test_every_referenced_schema_exists() -> None:
    """A referenced request/response schema must resolve to a real component —
    a dangling ``$ref`` means the generated client would have a broken type."""
    openapi = app.openapi()
    defined = set(openapi.get("components", {}).get("schemas", {}))
    referenced = _collect_refs(_contract(openapi)["operations"])
    missing = sorted(referenced - defined)
    assert not missing, f"operations reference undefined schemas: {missing}"
