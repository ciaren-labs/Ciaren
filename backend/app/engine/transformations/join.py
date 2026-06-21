import pandas as pd

from app.engine.transformations.base import BaseTransformation

_VALID_HOW = {"inner", "left", "right", "outer"}


class JoinTransformation(BaseTransformation):
    type = "join"

    def validate_config(self, config: dict) -> None:
        if not config.get("on"):
            raise ValueError("join requires 'on' key(s)")
        how = config.get("how", "inner")
        if how not in _VALID_HOW:
            raise ValueError(f"join 'how' must be one of {_VALID_HOW}")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        left = inputs["left"]
        right = inputs["right"]
        how = config.get("how", "inner")
        return {"default": pd.merge(left, right, on=config["on"], how=how)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        left, right = input_vars["left"], input_vars["right"]
        dst = output_vars["default"]
        how = config.get("how", "inner")
        return f'{dst} = pd.merge({left}, {right}, on={config["on"]!r}, how={how!r})'
