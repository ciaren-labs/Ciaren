# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in static checks for user-supplied ``pythonTransform`` code.

``pythonTransform`` runs arbitrary Python and is **not** sandboxed (see
the public security policy. When ``PYTHON_TRANSFORM_STRICT`` is enabled, this module
adds two defense-in-depth layers applied *before/around* execution:

1. :func:`check_script` — an AST scan that refuses obviously dangerous constructs
   (dangerous imports, code-exec builtins, the dunder-traversal attribute names
   used to break out of a restricted namespace, and the ``str.format`` family
   whose format-string mini-language can reach those same dunders as a runtime
   string the attribute scan can't see).
2. :func:`safe_builtins` — a restricted ``__builtins__`` mapping to run the script
   with, so the usual ``open``/``eval`` are simply absent and ``__import__`` is a
   curated wrapper enforcing the same import policy as the static scan (imports
   that pass :func:`check_script`, e.g. ``import numpy``, keep working at runtime;
   blocked ones fail with a clear guard error).

These raise the bar and catch accidental or casual misuse; they are **not** a
sandbox. A determined attacker can still find a bypass, so the real controls remain
network auth (#1) and running Ciaren as an unprivileged user. The guard is off by
default so existing scripts (e.g. ``import numpy``) keep working; turn it on for
shared/untrusted deployments.
"""

from __future__ import annotations

import ast
import builtins

#: Top-level modules a strict script may not import: anything granting the host
#: capabilities the guard withholds — filesystem access (``io.open`` is builtin
#: ``open``; ``tempfile``/``shutil``/``pathlib``/``glob``/``fileinput``/``mmap``/
#: ``dbm``/``shelve`` all reach files), process/OS control, network I/O, native
#: code (``ctypes``), code execution/deserialization (``pickle``/``marshal``/
#: ``code``/``codeop``), and interpreter introspection. Pure data/compute modules
#: (``math``, ``json``, ``datetime``, ``re``, ``numpy``, ``pandas``, …) stay
#: allowed. Both :func:`check_script` (static) and :func:`_guarded_import`
#: (runtime) read this single set — keep it that way.
_BLOCKED_IMPORTS = frozenset(
    {
        "__builtin__",
        "asyncio",
        "builtins",
        "code",
        "codeop",
        "ctypes",
        "dbm",
        "fcntl",
        "fileinput",
        "ftplib",
        "gc",
        "glob",
        "http",
        "httpx",
        "imp",
        "importlib",
        "inspect",
        "io",
        "marshal",
        "mmap",
        "msvcrt",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "pty",
        "requests",
        "resource",
        "runpy",
        "shelve",
        "shutil",
        "signal",
        "smtplib",
        "socket",
        "ssl",
        "subprocess",
        "sys",
        "telnetlib",
        "tempfile",
        "threading",
        "urllib",
        "urllib2",
        "webbrowser",
        "winreg",
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

#: Method names whose *format string* is a mini-language that can traverse
#: attributes at runtime (``"{0.__class__.__init__.__globals__}".format(obj)``),
#: reaching dunders that never appear as an ``ast.Attribute`` for the scan below
#: to catch — the classic ``str.format`` restricted-exec escape. Covers the ``str``
#: methods and ``string.Formatter``. F-strings need no entry: their ``{obj.__x__}``
#: interpolations parse *as* ``ast.Attribute`` and are caught by ``_BLOCKED_ATTRS``.
_BLOCKED_METHODS = frozenset(
    {
        "format",
        "format_map",
        "vformat",
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
        # Frame/traceback traversal: a live frame's f_globals/f_builtins expose the
        # *real* module builtins (open/eval/__import__), bypassing safe_builtins().
        # Frames are reachable without any blocked dunder, e.g. via a generator's
        # gi_frame or an exception's __traceback__.
        "__traceback__",
        "f_back",
        "f_globals",
        "f_locals",
        "f_builtins",
        "gi_frame",
        "cr_frame",
        "ag_frame",
        "tb_frame",
        "tb_next",
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
            if node.attr in _BLOCKED_METHODS:
                raise ScriptSecurityError(
                    f"pythonTransform (strict): {node.attr!r} is not allowed — its format string can "
                    "traverse attributes to escape the restricted namespace. Use an f-string or "
                    "concatenation instead."
                )


def _guarded_import(
    name: str,
    globals: object | None = None,
    locals: object | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> object:
    """``__import__`` replacement enforcing the *same* policy as :func:`check_script`:
    imports whose root module is in :data:`_BLOCKED_IMPORTS` raise a clear,
    guard-branded :class:`ImportError`; everything else (``math``, ``numpy``,
    ``pandas``, …) imports normally. Sharing :data:`_BLOCKED_IMPORTS` keeps the
    static scan and the runtime namespace from drifting apart."""
    root = name.split(".")[0]
    if root in _BLOCKED_IMPORTS:
        raise ImportError(
            f"import of module {root!r} is blocked by the Ciaren script guard (PYTHON_TRANSFORM_STRICT is enabled)."
        )
    return builtins.__import__(name, globals, locals, fromlist, level)  # type: ignore[arg-type]


def safe_builtins() -> dict[str, object]:
    """A restricted ``__builtins__`` mapping for executing a strict script: only the
    names in :data:`_ALLOWED_BUILTINS`, so ``open``/``eval`` etc. are simply absent
    from the user's namespace, plus a curated ``__import__``
    (:func:`_guarded_import`) so that ``import`` statements the static scan accepts
    (e.g. ``import numpy``) also work at runtime instead of failing with an opaque
    ``__import__ not found``."""
    available = vars(builtins)
    restricted: dict[str, object] = {name: available[name] for name in _ALLOWED_BUILTINS if name in available}
    # The import statement's bytecode looks up ``__import__`` in ``__builtins__``.
    # Direct calls to ``__import__`` in user code remain rejected statically via
    # _BLOCKED_NAMES; this entry only serves ``import x`` / ``from x import y``.
    restricted["__import__"] = _guarded_import
    return restricted
