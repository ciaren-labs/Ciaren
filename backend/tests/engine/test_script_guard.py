"""Opt-in strict static checks for the pythonTransform node (defense in depth).

Off by default (existing scripts keep working); when PYTHON_TRANSFORM_STRICT is on,
dangerous imports/builtins/dunders are refused and the script runs with a restricted
set of builtins.
"""

import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends import get_engine
from app.engine.registry import get_transformation
from app.engine.script_guard import (
    ScriptSecurityError,
    check_script,
    safe_builtins,
)

# -- check_script (unit) -----------------------------------------------------


def test_safe_script_passes():
    check_script("df['c'] = df['a'] + 1\nreturn df")
    check_script("return df.head(3)")
    check_script("rows = [i for i in range(len(df))]\nreturn df")


@pytest.mark.parametrize(
    "script",
    [
        "import os\nreturn df",
        "import sys, json\nreturn df",
        "from subprocess import run\nreturn df",
        "import os.path\nreturn df",
        "from os import system\nreturn df",
    ],
)
def test_blocked_imports(script):
    with pytest.raises(ScriptSecurityError, match="import"):
        check_script(script)


@pytest.mark.parametrize(
    "script",
    [
        "eval('1+1')\nreturn df",
        "exec('x=1')\nreturn df",
        "open('/etc/passwd')\nreturn df",
        "__import__('os')\nreturn df",
        "getattr(df, 'x')\nreturn df",
        "globals()\nreturn df",
    ],
)
def test_blocked_builtins(script):
    with pytest.raises(ScriptSecurityError, match="not allowed"):
        check_script(script)


@pytest.mark.parametrize(
    "script",
    [
        "().__class__.__bases__\nreturn df",
        "x = type(df).__subclasses__()\nreturn df",
        "df.__class__\nreturn df",
        "(1).__class__.__mro__\nreturn df",
        "f = lambda: None\nf.__globals__\nreturn df",
    ],
)
def test_blocked_dunder_attributes(script):
    with pytest.raises(ScriptSecurityError, match="attribute"):
        check_script(script)


def test_syntax_error_is_reported():
    with pytest.raises(ScriptSecurityError, match="syntax error"):
        check_script("return df[[")


# -- safe_builtins (unit) ----------------------------------------------------


def test_safe_builtins_allows_common_helpers():
    b = safe_builtins()
    for name in ("len", "range", "sum", "min", "max", "sorted", "enumerate", "print"):
        assert name in b


def test_safe_builtins_withholds_dangerous_ones():
    b = safe_builtins()
    for name in ("open", "eval", "exec", "__import__", "getattr", "compile", "globals", "input"):
        assert name not in b


# -- integration through the node (strict on/off) ----------------------------


def _set_strict(monkeypatch, enabled: bool) -> None:
    monkeypatch.setenv("FLOWFRAME_PYTHON_TRANSFORM_STRICT", "true" if enabled else "false")
    get_settings.cache_clear()


@pytest.fixture
def strict(monkeypatch):
    _set_strict(monkeypatch, True)
    yield
    get_settings.cache_clear()


def test_validate_allows_dangerous_when_strict_off(monkeypatch):
    _set_strict(monkeypatch, False)
    try:
        # Off by default: an import that strict mode would block is accepted.
        get_transformation("pythonTransform").validate_config({"script": "import os\nreturn df"})
    finally:
        get_settings.cache_clear()


def test_validate_rejects_dangerous_when_strict_on(strict):
    t = get_transformation("pythonTransform")
    with pytest.raises(ValueError, match="not allowed"):
        t.validate_config({"script": "import os\nreturn df"})


def test_execute_runs_safe_script_under_strict(strict):
    t = get_transformation("pythonTransform")
    engine = get_engine("pandas")
    config = {"script": "df['b'] = [x * 2 for x in df['a']]\nreturn df"}
    t.validate_config(config)
    out = t.execute(engine, {"in": pd.DataFrame({"a": [1, 2, 3]})}, config)
    assert list(engine.to_pandas(out["out"])["b"]) == [2, 4, 6]


def test_execute_blocks_dangerous_script_under_strict(strict):
    t = get_transformation("pythonTransform")
    engine = get_engine("pandas")
    config = {"script": "import os\nreturn df"}
    with pytest.raises(ValueError, match="not allowed"):
        t.execute(engine, {"in": pd.DataFrame({"a": [1]})}, config)
