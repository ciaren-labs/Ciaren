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
        "capitalize": ("capitalize", "to_titlecase()"),
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
        if op in self._SIMPLE_OPS:
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
