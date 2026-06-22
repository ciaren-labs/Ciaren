from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation

_VALID_HOW = {"inner", "left", "right", "outer"}


def _as_list(value: Any) -> list[str] | None:
    if not value:
        return None
    return [value] if isinstance(value, str) else list(value)


class JoinTransformation(BaseTransformation):
    type = "join"
    input_handles = ("left", "right")

    # pandas merge 'how' -> polars join 'how' (pandas 'outer' is polars 'full').
    _POLARS_HOW = {"inner": "inner", "left": "left", "right": "right", "outer": "full"}

    def validate_config(self, config: dict[str, Any]) -> None:
        has_on = bool(config.get("on"))
        has_split = bool(config.get("left_on")) and bool(config.get("right_on"))
        if not has_on and not has_split:
            raise ValueError("join requires either 'on', or both 'left_on' and 'right_on'")
        how = config.get("how", "inner")
        if how not in _VALID_HOW:
            raise ValueError(f"join 'how' must be one of {_VALID_HOW}")

    def _suffixes(self, config: dict[str, Any]) -> tuple[str, str]:
        suffixes = config.get("suffixes")
        if isinstance(suffixes, (list, tuple)) and len(suffixes) == 2:
            return (str(suffixes[0]), str(suffixes[1]))
        return ("_x", "_y")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        how = config.get("how", "inner")
        left_on = _as_list(config.get("left_on"))
        right_on = _as_list(config.get("right_on"))
        on = None if (left_on and right_on) else _as_list(config.get("on"))
        return {
            "out": engine.join(
                inputs["left"],
                inputs["right"],
                on,
                how,
                left_on,
                right_on,
                self._suffixes(config),
            )
        }

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        left, right = input_vars["left"], input_vars["right"]
        dst = output_vars["out"]
        how = config.get("how", "inner")
        suffixes = self._suffixes(config)
        left_on, right_on = _as_list(config.get("left_on")), _as_list(config.get("right_on"))
        if left_on and right_on:
            keys = f"left_on={left_on!r}, right_on={right_on!r}"
        else:
            keys = f"on={_as_list(config.get('on'))!r}"
        return (
            f"{dst} = pd.merge({left}, {right}, {keys}, how={how!r}, "
            f"suffixes={suffixes!r})"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        left, right = input_vars["left"], input_vars["right"]
        dst = output_vars["out"]
        how = self._POLARS_HOW.get(config.get("how", "inner"), "inner")
        suffix = self._suffixes(config)[1]
        left_on, right_on = _as_list(config.get("left_on")), _as_list(config.get("right_on"))
        if left_on and right_on:
            keys = f"left_on={left_on!r}, right_on={right_on!r}"
        else:
            keys = f"on={_as_list(config.get('on'))!r}"
        return f"{dst} = {left}.join({right}, {keys}, how={how!r}, suffix={suffix!r})"
