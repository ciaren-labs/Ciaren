"""The Validator example plugin: config validation, runtime, and codegen.

Loads the committed example plugin from its directory (the same path the loader
uses) and exercises ``validate_config``, both validation rules at runtime, and
Python-code export — including that the exported ``allowed_set`` code produces
the same result as runtime execution for non-string columns.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "examples" / "plugins" / "validator-plugin"


@pytest.fixture(scope="module")
def runtime():
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.append(str(PLUGIN_DIR))
    from ciaren_validator.plugin import _CheckColumnRuntime

    return _CheckColumnRuntime()


def _df() -> pd.DataFrame:
    return pd.DataFrame({"sku": ["A-001", "B-002", "A-003", "x"], "qty": [1, 2, 3, 4]})


@pytest.mark.parametrize(
    "config",
    [
        {},  # missing column
        {"column": "sku"},  # missing rule
        {"column": "sku", "rule": "bogus"},  # unsupported rule
        {"column": "sku", "rule": "regex"},  # regex rule without a pattern
        {"column": "sku", "rule": "regex", "pattern": "[unclosed"},  # invalid regex
        {"column": "sku", "rule": "allowed_set"},  # allowed_set without values
        {"column": "sku", "rule": "allowed_set", "allowed_values": []},  # empty list
        {"column": "sku", "rule": "allowed_set", "allowed_values": "A-001"},  # not a list
    ],
)
def test_validate_config_rejects_bad_config(runtime, config):
    with pytest.raises(ValueError):
        runtime.validate_config(config)


@pytest.mark.parametrize(
    "config",
    [
        {"column": "sku", "rule": "regex", "pattern": "^[A-Z]-\\d{3}$"},
        {"column": "sku", "rule": "allowed_set", "allowed_values": ["A-001", "B-002"]},
    ],
)
def test_validate_config_accepts_valid_config(runtime, config):
    runtime.validate_config(config)


def test_execute_rejects_missing_column(runtime):
    with pytest.raises(ValueError, match="not found"):
        runtime.execute({"in": _df()}, {"column": "nope", "rule": "regex", "pattern": "x"})


def test_execute_regex_rule(runtime):
    out = runtime.execute({"in": _df()}, {"column": "sku", "rule": "regex", "pattern": "^[A-Z]-\\d{3}$"})
    assert list(out["out"]["passed"]) == [True, True, True, False]


def test_execute_allowed_set_coerces_column_to_str(runtime):
    # "qty" is integer-typed; runtime str-coerces before the membership check.
    out = runtime.execute(
        {"in": _df()}, {"column": "qty", "rule": "allowed_set", "allowed_values": ["1", "3"]}
    )
    assert list(out["out"]["passed"]) == [True, False, True, False]


def test_execute_uses_custom_output_column(runtime):
    out = runtime.execute(
        {"in": _df()},
        {"column": "qty", "rule": "allowed_set", "allowed_values": ["1"], "output_column": "ok"},
    )
    assert list(out["out"]["ok"]) == [True, False, False, False]
    assert "passed" not in out["out"].columns


def test_to_python_code_regex_is_valid_python(runtime):
    code = runtime.to_python_code(
        {"in": "df_1"}, {"out": "df_2"}, {"column": "sku", "rule": "regex", "pattern": "^[A-Z]-\\d{3}$"}
    )
    assert ".astype(str).str.match(" in code
    compile(code, "<generated>", "exec")


def test_to_python_code_allowed_set_matches_runtime(runtime):
    """Exported code must reproduce runtime output, incl. str coercion for
    non-string columns (regression for the allowed_set codegen mismatch)."""
    config = {"column": "qty", "rule": "allowed_set", "allowed_values": ["1", "3"]}
    code = runtime.to_python_code({"in": "df_1"}, {"out": "df_2"}, config)
    assert ".astype(str).isin(" in code
    compile(code, "<generated>", "exec")

    ns: dict[str, Any] = {"df_1": _df()}
    exec(code, ns)
    exported = ns["df_2"]

    runtime_out = runtime.execute({"in": _df()}, config)["out"]
    assert list(exported["passed"]) == list(runtime_out["passed"])
    assert list(exported["passed"]) == [True, False, True, False]
