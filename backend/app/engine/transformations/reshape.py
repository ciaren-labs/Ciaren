import pandas as pd

from app.engine.transformations.base import BaseTransformation


class GroupByAggregateTransformation(BaseTransformation):
    type = "groupByAggregate"

    def validate_config(self, config: dict) -> None:
        if not config.get("group_by"):
            raise ValueError("groupByAggregate requires 'group_by' list")
        if not config.get("aggregations"):
            raise ValueError("groupByAggregate requires 'aggregations' dict {col: func}")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        result = df.groupby(config["group_by"]).agg(config["aggregations"]).reset_index()
        return {"default": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        return (
            f"{dst} = {src}.groupby({config['group_by']!r})"
            f".agg({config['aggregations']!r}).reset_index()"
        )


class ConcatRowsTransformation(BaseTransformation):
    type = "concatRows"

    def validate_config(self, config: dict) -> None:
        pass

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        frames = list(inputs.values())
        return {"default": pd.concat(frames, ignore_index=True)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        dst = output_vars["default"]
        src_list = list(input_vars.values())
        return f"{dst} = pd.concat([{', '.join(src_list)}], ignore_index=True)"


class CreateCalculatedColumnTransformation(BaseTransformation):
    type = "calculatedColumn"

    _ALLOWED_FUNCS = {"str", "int", "float", "len", "abs", "round"}

    def validate_config(self, config: dict) -> None:
        if not config.get("column_name"):
            raise ValueError("calculatedColumn requires 'column_name'")
        if not config.get("expression"):
            raise ValueError("calculatedColumn requires 'expression'")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"].copy()
        df[config["column_name"]] = df.eval(config["expression"])
        return {"default": df}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        col = config["column_name"]
        expr = config["expression"]
        return (
            f"{dst} = {src}.copy()\n"
            f'{dst}[{col!r}] = {dst}.eval({expr!r})'
        )
