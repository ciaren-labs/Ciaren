from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


class ReplaceValuesTransformation(BaseTransformation):
    type = "replaceValues"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("replaceValues requires a 'column'")
        if "to_replace" not in config or "value" not in config:
            raise ValueError("replaceValues requires 'to_replace' and 'value'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.replace_values(
            inputs["in"],
            config["column"],
            config["to_replace"],
            config["value"],
            bool(config.get("regex", False)),
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        extra = ", regex=True" if config.get("regex") else ""
        return (
            f"{dst} = {src}.assign(**{{{col!r}: {src}[{col!r}]"
            f".replace({config['to_replace']!r}, {config['value']!r}{extra})}})"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        if config.get("regex"):
            return (
                f"{dst} = {src}.with_columns(pl.col({col!r}).cast(pl.Utf8)"
                f".str.replace_all({config['to_replace']!r}, {config['value']!r}))"
            )
        return (
            f"{dst} = {src}.with_columns("
            f"pl.col({col!r}).replace({config['to_replace']!r}, {config['value']!r}))"
        )


class StringTransformTransformation(BaseTransformation):
    type = "stringTransform"

    # Argument-free operations: name -> (pandas str method, polars str expr).
    _SIMPLE_OPS = {
        "lower": ("lower", "to_lowercase()"),
        "upper": ("upper", "to_uppercase()"),
        "strip": ("strip", "strip_chars()"),
        "title": ("title", "to_titlecase()"),
        # capitalize is special-cased in to_polars_code (no direct polars method).
        "capitalize": ("capitalize", None),
        "len": ("len", "len_chars()"),
    }
    _VALID_OPS = set(_SIMPLE_OPS) | {"replace", "pad"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("stringTransform requires a 'column'")
        op = config.get("operation")
        if op not in self._VALID_OPS:
            raise ValueError(
                f"stringTransform 'operation' must be one of {sorted(self._VALID_OPS)}"
            )
        if op == "replace" and "find" not in config:
            raise ValueError("stringTransform 'replace' requires a 'find' value")
        if op == "pad" and not isinstance(config.get("width"), int):
            raise ValueError("stringTransform 'pad' requires an integer 'width'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.string_transform(
            inputs["in"],
            config["column"],
            config["operation"],
            find=config.get("find"),
            replace_with=config.get("replace_with", ""),
            width=config.get("width"),
            fill_char=config.get("fill_char", " "),
            side=config.get("side", "left"),
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        op = config["operation"]
        accessor = f"{src}[{col!r}].astype('string').str"
        if op in self._SIMPLE_OPS:
            method = self._SIMPLE_OPS[op][0]
            call = f"{accessor}.{method}()"
        elif op == "replace":
            call = f"{accessor}.replace({config['find']!r}, {config.get('replace_with', '')!r})"
        else:  # pad
            side = config.get("side", "left")
            return (
                f"{dst} = {src}.assign(**{{{col!r}: {accessor}"
                f".pad({config['width']!r}, side={side!r}, "
                f"fillchar={config.get('fill_char', ' ')!r})}})"
            )
        return f"{dst} = {src}.assign(**{{{col!r}: {call}}})"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        op = config["operation"]
        base = f"pl.col({col!r}).cast(pl.Utf8).str"
        if op == "capitalize":
            # pandas capitalize: first char upper, the rest lower (whole string).
            expr = f"({base}.slice(0, 1).str.to_uppercase() + {base}.slice(1).str.to_lowercase())"
        elif op in self._SIMPLE_OPS:
            expr = f"{base}.{self._SIMPLE_OPS[op][1]}"
        elif op == "replace":
            expr = (
                f"{base}.replace_all({config['find']!r}, "
                f"{config.get('replace_with', '')!r}, literal=True)"
            )
        else:  # pad
            method = "pad_end" if config.get("side") == "right" else "pad_start"
            expr = f"{base}.{method}({config['width']!r}, {config.get('fill_char', ' ')!r})"
        return f"{dst} = {src}.with_columns({expr}.alias({col!r}))"


class SplitColumnTransformation(BaseTransformation):
    """Split a text column into several columns by a delimiter or regex groups."""

    type = "splitColumn"

    _MODES = {"delimiter", "regex"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("splitColumn requires a 'column'")
        into = config.get("into")
        if not isinstance(into, list) or not into:
            raise ValueError("splitColumn requires a non-empty 'into' list")
        mode = config.get("mode", "delimiter")
        if mode not in self._MODES:
            raise ValueError(f"splitColumn 'mode' must be one of {sorted(self._MODES)}")
        if mode == "delimiter" and not config.get("delimiter"):
            raise ValueError("splitColumn delimiter mode requires a 'delimiter'")
        if mode == "regex" and not config.get("pattern"):
            raise ValueError("splitColumn regex mode requires a 'pattern'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.split_column(
                inputs["in"],
                config["column"],
                config["into"],
                config.get("mode", "delimiter"),
                config.get("delimiter", ""),
                config.get("pattern", ""),
                bool(config.get("keep_original", True)),
            )
        }

    def _parts_expr(self, src: str, col: str, config: dict[str, Any]) -> str:
        accessor = f"{src}[{col!r}].astype('string').str"
        if config.get("mode", "delimiter") == "regex":
            return f"{accessor}.extract({config['pattern']!r})"
        return f"{accessor}.split({config['delimiter']!r}, expand=True, regex=False)"

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, into = config["column"], config["into"]
        assigns = ", ".join(f"{name!r}: _parts[{i}]" for i, name in enumerate(into))
        lines = [
            f"_parts = {self._parts_expr(src, col, config)}",
            f"{dst} = {src}.assign(**{{{assigns}}})",
        ]
        if not config.get("keep_original", True) and col not in into:
            lines.append(f"{dst} = {dst}.drop(columns=[{col!r}])")
        return "\n".join(lines)

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, into = config["column"], config["into"]
        base = f"pl.col({col!r}).cast(pl.Utf8).str"
        if config.get("mode", "delimiter") == "regex":
            exprs = ", ".join(
                f"{base}.extract({config['pattern']!r}, {i + 1}).alias({name!r})"
                for i, name in enumerate(into)
            )
        else:
            exprs = ", ".join(
                f"{base}.split({config['delimiter']!r}).list.get({i}, null_on_oob=True)"
                f".alias({name!r})"
                for i, name in enumerate(into)
            )
        code = f"{dst} = {src}.with_columns([{exprs}])"
        if not config.get("keep_original", True) and col not in into:
            code += f"\n{dst} = {dst}.drop({col!r})"
        return code


class MapValuesTransformation(BaseTransformation):
    """Map column values via a lookup dict (CASE-WHEN-lite), with optional default."""

    type = "mapValues"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("mapValues requires a 'column'")
        mapping = config.get("mapping")
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("mapValues requires a non-empty 'mapping' object")

    def _use_default(self, config: dict[str, Any]) -> bool:
        return bool(config.get("use_default", "default" in config))

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.map_values(
                inputs["in"],
                config["column"],
                config.get("new_column") or None,
                config["mapping"],
                config.get("default"),
                bool(self._use_default(config)),
            )
        }

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        target = config.get("new_column") or col
        mapping = config["mapping"]
        if self._use_default(config):
            mapped = (
                f"{src}[{col!r}].map({mapping!r})"
                f".where({src}[{col!r}].isin({list(mapping)!r}), {config.get('default')!r})"
            )
        else:
            mapped = f"{src}[{col!r}].replace({mapping!r})"
        return f"{dst} = {src}.assign(**{{{target!r}: {mapped}}})"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        target = config.get("new_column") or col
        mapping = config["mapping"]
        if self._use_default(config):
            expr = f"pl.col({col!r}).replace_strict({mapping!r}, default={config.get('default')!r})"
        else:
            expr = f"pl.col({col!r}).replace({mapping!r})"
        return f"{dst} = {src}.with_columns({expr}.alias({target!r}))"
