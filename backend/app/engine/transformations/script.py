# SPDX-License-Identifier: AGPL-3.0-only
"""Custom Python transform node.

The user writes the body of ``def transform(df): …``. Ciaren wraps it,
injects the engine-appropriate namespace (``pd`` / ``pl``), and calls it.

No sandboxing: Ciaren is local-first. Document that scripts run with full
user permissions.
"""

from __future__ import annotations

from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


def _indent(script: str) -> str:
    """Indent every non-empty line by 4 spaces for function body embedding."""
    lines = script.splitlines()
    indented = "\n".join(("    " + line) if line.strip() else "" for line in lines)
    return indented or "    return df"


class PythonTransformTransformation(BaseTransformation):
    """Run arbitrary user-supplied Python code on the input DataFrame.

    Config keys:
    - ``script`` (str, required): the body of ``def transform(df): …``
      The script must ``return`` a DataFrame; anything else raises at runtime.
    """

    type = "pythonTransform"
    polars_lazy_safe = False

    def validate_config(self, config: dict[str, Any]) -> None:
        script = config.get("script", "")
        if not isinstance(script, str) or not script.strip():
            raise ValueError("pythonTransform requires a non-empty 'script'")
        # Validate syntax by wrapping in a function (mirrors what execute does).
        fn_code = f"def _transform(df):\n{_indent(script)}"
        try:
            compile(fn_code, "<pythonTransform>", "exec")
        except SyntaxError as exc:
            raise ValueError(f"pythonTransform: syntax error — {exc}") from exc
        # Opt-in defense-in-depth: reject dangerous constructs before the script can
        # ever be saved/run. No-op unless PYTHON_TRANSFORM_STRICT is enabled.
        from app.engine.script_guard import check_script, is_strict_enabled

        if is_strict_enabled():
            check_script(script)

    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]:
        df = inputs["in"]
        script = config["script"]

        # Build namespace with the engine-appropriate imports so the user's
        # script can reference pd.DataFrame / pl.col(...) without explicit imports.
        ns: dict[str, Any]
        if engine.name == "polars":
            import polars as pl

            ns = {"pl": pl, "polars": pl}
        else:
            import pandas as pd

            ns = {"pd": pd, "pandas": pd}

        # Opt-in hardening: re-check statically (the config may not have gone through
        # validate_config) and run with a restricted set of builtins so open/eval/
        # __import__ are absent. No-op unless PYTHON_TRANSFORM_STRICT is enabled.
        from app.engine.script_guard import check_script, is_strict_enabled, safe_builtins

        if is_strict_enabled():
            check_script(script)
            ns["__builtins__"] = safe_builtins()

        fn_code = f"def _transform(df):\n{_indent(script)}"
        exec(fn_code, ns)  # noqa: S102
        result = ns["_transform"](df)

        if result is None:
            raise ValueError("pythonTransform: script returned None — add a 'return' statement.")
        return {"out": result}

    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        script = config.get("script", "return df")
        return f"def _ff_transform(df):\n{_indent(script)}\n\n{dst} = _ff_transform({src})"

    def imports(self, config: dict[str, Any]) -> list[str]:
        return ["import pandas as pd"]

    def to_polars_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        script = config.get("script", "return df")
        return f"def _ff_transform(df):\n{_indent(script)}\n\n{dst} = _ff_transform({src})"
