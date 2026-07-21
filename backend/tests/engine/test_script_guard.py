"""Opt-in strict static checks for the pythonTransform node (defense in depth).

Off by default (existing scripts keep working); when PYTHON_TRANSFORM_STRICT is on,
dangerous imports/builtins/dunders are refused and the script runs with a restricted
set of builtins.
"""

import builtins

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


@pytest.mark.parametrize(
    "script",
    [
        # The classic str.format escape: dunder traversal hidden in the format
        # string, invisible to the ast.Attribute scan.
        "'{0.__class__.__init__.__globals__}'.format(df)\nreturn df",
        "'{x.__class__}'.format_map({'x': df})\nreturn df",
        "s = '{0.__class__}'\ns.format(df)\nreturn df",
        # Reaching str.format via the type also lands on the blocked attr name.
        "str.format('{0.__class__}', df)\nreturn df",
    ],
)
def test_blocked_format_string_traversal(script):
    with pytest.raises(ScriptSecurityError, match="not allowed"):
        check_script(script)


@pytest.mark.parametrize(
    "script",
    [
        # A live frame is reachable without any classic dunder, e.g. a
        # generator's gi_frame; its f_globals/f_builtins expose real builtins.
        "g = (0 for _ in range(1))\nfr = g.gi_frame\nreturn df",
        "fr = something.f_back\nreturn df",
        "x = obj.f_globals\nreturn df",
        "x = obj.f_builtins\nreturn df",
        "try:\n    1 / 0\nexcept Exception as e:\n    tb = e.__traceback__\nreturn df",
        "x = tb.tb_frame\nreturn df",
        "x = coro.cr_frame\nreturn df",
    ],
)
def test_blocked_frame_traversal_attributes(script):
    with pytest.raises(ScriptSecurityError, match="attribute"):
        check_script(script)


# A few representatives of the capability-granting stdlib modules added to the
# blocklist (io.open == builtin open; tempfile writes files; socket is network;
# pickle executes on deserialization). Each must fail BOTH the static scan and
# the runtime guarded __import__ — they share one _BLOCKED_IMPORTS set.
_CAPABILITY_MODULES = ["io", "tempfile", "socket", "pickle"]

# Pure data/compute modules that grant no host capability stay importable.
_PURE_COMPUTE_MODULES = ["math", "json", "datetime"]


@pytest.mark.parametrize("module", _CAPABILITY_MODULES)
def test_capability_stdlib_import_rejected_statically(module):
    with pytest.raises(ScriptSecurityError, match="import"):
        check_script(f"import {module}\nreturn df")


@pytest.mark.parametrize("module", _CAPABILITY_MODULES)
def test_capability_stdlib_import_rejected_at_runtime(module):
    guarded = safe_builtins()["__import__"]
    with pytest.raises(ImportError, match="blocked by the Ciaren script guard"):
        guarded(module)


@pytest.mark.parametrize("module", _PURE_COMPUTE_MODULES)
def test_pure_compute_import_still_allowed_statically(module):
    check_script(f"import {module}\nreturn df")


@pytest.mark.parametrize("module", _PURE_COMPUTE_MODULES)
def test_pure_compute_import_still_allowed_at_runtime(module):
    guarded = safe_builtins()["__import__"]
    assert guarded(module) is builtins.__import__(module)


def test_benign_attribute_access_still_allowed():
    check_script("x = df.shape\nreturn df.head(2)")
    check_script("cols = df.columns\nreturn df[cols]")


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
    for name in ("open", "eval", "exec", "getattr", "compile", "globals", "input"):
        assert name not in b


def test_safe_builtins_import_is_guarded_not_raw():
    # __import__ IS present (import statements need it) but is the curated
    # wrapper, never the real builtins.__import__.
    b = safe_builtins()
    assert "__import__" in b
    assert b["__import__"] is not builtins.__import__


def test_guarded_import_allows_non_blocked_module():
    import math

    assert safe_builtins()["__import__"]("math") is math


def test_guarded_import_blocks_with_clear_error():
    guarded = safe_builtins()["__import__"]
    with pytest.raises(ImportError, match="blocked by the Ciaren script guard"):
        guarded("os")
    with pytest.raises(ImportError, match="blocked by the Ciaren script guard"):
        guarded("os.path")  # root module is what's checked


def test_exec_with_safe_builtins_import_runtime_behavior():
    # Static-scan-free exec: verifies the runtime namespace alone enforces the
    # same policy — allowed imports work, blocked ones raise the clear guard
    # error instead of the opaque "__import__ not found".
    ns: dict[str, object] = {"__builtins__": safe_builtins()}
    exec("import math\nresult = math.sqrt(16)", ns)  # noqa: S102
    assert ns["result"] == 4.0

    ns2: dict[str, object] = {"__builtins__": safe_builtins()}
    with pytest.raises(ImportError, match="blocked by the Ciaren script guard"):
        exec("import os", ns2)  # noqa: S102


# -- integration through the node (strict on/off) ----------------------------


def _set_strict(monkeypatch, enabled: bool) -> None:
    monkeypatch.setenv("CIAREN_PYTHON_TRANSFORM_STRICT", "true" if enabled else "false")
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


def test_execute_allows_non_blocked_import_under_strict(strict):
    # Regression: a non-blocked import used to pass check_script but then die at
    # runtime with "ImportError: __import__ not found" because safe_builtins()
    # omitted __import__. It must now validate AND run.
    t = get_transformation("pythonTransform")
    engine = get_engine("pandas")
    config = {"script": "import math\ndf['b'] = [math.sqrt(x) for x in df['a']]\nreturn df"}
    t.validate_config(config)
    out = t.execute(engine, {"in": pd.DataFrame({"a": [4, 9]})}, config)
    assert list(engine.to_pandas(out["out"])["b"]) == [2.0, 3.0]


def test_execute_blocked_import_error_is_clear_not_opaque(strict):
    # Even if a blocked import ever slipped past the static scan, the runtime
    # error must be the guard-branded one, never "__import__ not found". Here the
    # static scan fires first, but the message assertion pins clarity either way.
    t = get_transformation("pythonTransform")
    engine = get_engine("pandas")
    with pytest.raises(ValueError) as excinfo:
        t.execute(engine, {"in": pd.DataFrame({"a": [1]})}, {"script": "import os\nreturn df"})
    assert "__import__ not found" not in str(excinfo.value)
    assert "not allowed" in str(excinfo.value)
