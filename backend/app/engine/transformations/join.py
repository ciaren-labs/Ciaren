from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation

_VALID_HOW = {"inner", "left", "right", "outer"}


class JoinTransformation(BaseTransformation):
    type = "join"
    input_handles = ("left", "right")

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("on"):
            raise ValueError("join requires 'on' key(s)")
        how = config.get("how", "inner")
        if how not in _VALID_HOW:
            raise ValueError(f"join 'how' must be one of {_VALID_HOW}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        on = config["on"]
        on = [on] if isinstance(on, str) else on
        how = config.get("how", "inner")
        return {"out": engine.join(inputs["left"], inputs["right"], on, how)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        left, right = input_vars["left"], input_vars["right"]
        dst = output_vars["out"]
        how = config.get("how", "inner")
        return f"{dst} = pd.merge({left}, {right}, on={config['on']!r}, how={how!r})"
