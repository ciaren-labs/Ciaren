"""Opt-in static checks for user-supplied ``pythonTransform`` code.

``pythonTransform`` runs arbitrary Python and is **not** sandboxed (see
the public security policy. When ``PYTHON_TRANSFORM_STRICT`` is enabled, this module
adds two defense-in-depth layers applied *before/around* execution:

1. :func:`check_script` — an AST scan that refuses obviously dangerous constructs
   (dangerous imports, code-exec builtins, and the dunder-traversal attribute
   names used to break out of a restricted namespace).
2. :func:`safe_builtins` — a restricted ``__builtins__`` mapping to run the script
   with, so the usual ``open``/``__import__``/``eval`` are simply absent.

These raise the bar and catch accidental or casual misuse; they are **not** a
sandbox. A determined attacker can still find a bypass, so the real controls remain
network auth (#1) and running FlowFrame as an unprivileged user. The guard is off by
default so existing scripts (e.g. ``import numpy``) keep working; turn it on for
shared/untrusted deployments.
"""

from __future__ import annotations

import ast
import builtins

#: Top-level modules a strict script may not import. Anything granting filesystem,
#: process, network, or interpreter access — and the codegen/serialization escape
#: hatches.
_BLOCKED_IMPORTS = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "shutil",
        "pathlib",
        "ctypes",
        "importlib",
        "imp",
        "runpy",
        "pickle",
        "marshal",
        "shelve",
        "code",
        "pty",
        "multiprocessing",
        "threading",
        "asyncio",
        "requests",
        "urllib",
        "urllib2",
        "http",
        "httpx",
        "ftplib",
        "smtplib",
        "telnetlib",
        "webbrowser",
        "builtins",
        "__builtin__",
        "gc",
        "inspect",
        "platform",
        "resource",
        "signal",
        "fcntl",
    }
)

#: Builtin names that execute code, import, or reach the global/file environment.
_BLOCKED_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "input",
        "breakpoint",
        "memoryview",
        "exit",
        "quit",
    }
)

#: Dunder attribute names used to climb from a harmless object to ``type``,
#: ``__builtins__``, or arbitrary code (the classic restricted-exec escapes).
_BLOCKED_ATTRS = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__subclasses__",
        "__bases__",
        "__base__",
        "__mro__",
        "__class__",
        "__code__",
        "__closure__",
        "__dict__",
        "__getattribute__",
        "__getattr__",
        "__import__",
        "__loader__",
        "__module__",
        "__func__",
        "__self__",
    }
)

#: Builtins a strict script *is* allowed to use — everything else is withheld.
_ALLOWED_BUILTINS = frozenset(
    {
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytearray",
        "bytes",
        "chr",
        "complex",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "hash",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "oct",
        "ord",
        "pow",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "True",
        "False",
        "None",
    }
)


class ScriptSecurityError(ValueError):
    """Raised when strict-mode static analysis rejects a pythonTransform script."""


def is_strict_enabled() -> bool:
    from app.core.config import get_settings

    return get_settings().PYTHON_TRANSFORM_STRICT


def check_script(script: str) -> None:
    """Raise :class:`ScriptSecurityError` if ``script`` uses a denied import,
    builtin, or dunder attribute. Syntax errors are reported as-is. Wraps the body
    in a function so a bare ``return`` parses, mirroring how it is executed."""
    from app.engine.transformations.script import _indent

    fn_code = f"def _transform(df):\n{_indent(script)}"
    try:
        tree = ast.parse(fn_code)
    except SyntaxError as exc:  # surfaced the same way as validate_config
        raise ScriptSecurityError(f"pythonTransform: syntax error — {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_IMPORTS:
                    raise ScriptSecurityError(f"pythonTransform (strict): importing {root!r} is not allowed.")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _BLOCKED_IMPORTS:
                raise ScriptSecurityError(f"pythonTransform (strict): importing from {root!r} is not allowed.")
        elif isinstance(node, ast.Name):
            if node.id in _BLOCKED_NAMES:
                raise ScriptSecurityError(f"pythonTransform (strict): use of {node.id!r} is not allowed.")
        elif isinstance(node, ast.Attribute):
            if node.attr in _BLOCKED_ATTRS:
                raise ScriptSecurityError(
                    f"pythonTransform (strict): access to attribute {node.attr!r} is not allowed."
                )


def safe_builtins() -> dict[str, object]:
    """A restricted ``__builtins__`` mapping for executing a strict script: only the
    names in :data:`_ALLOWED_BUILTINS`, so ``open``/``__import__``/``eval`` etc. are
    simply absent from the user's namespace."""
    available = vars(builtins)
    return {name: available[name] for name in _ALLOWED_BUILTINS if name in available}
