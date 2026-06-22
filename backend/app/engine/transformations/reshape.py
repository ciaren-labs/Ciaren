from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


class GroupByAggregateTransformation(BaseTransformation):
    type = "groupByAggregate"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("group_by"):
            raise ValueError("groupByAggregate requires 'group_by' list")
        if not config.get("aggregations"):
            raise ValueError("groupByAggregate requires 'aggregations' dict {col: func}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.groupby_agg(
            inputs["in"], config["group_by"], config["aggregations"]
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return (
            f"{dst} = {src}.groupby({config['group_by']!r})"
            f".agg({config['aggregations']!r}).reset_index()"
        )


class ConcatRowsTransformation(BaseTransformation):
    type = "concatRows"
    multi_input = True

    def validate_config(self, config: dict[str, Any]) -> None:
        pass

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frames = list(inputs.values())
        return {"out": engine.concat(frames)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        dst = output_vars["out"]
        src_list = list(input_vars.values())
        return f"{dst} = pd.concat([{', '.join(src_list)}], ignore_index=True)"


class CreateCalculatedColumnTransformation(BaseTransformation):
    type = "calculatedColumn"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column_name"):
            raise ValueError("calculatedColumn requires 'column_name'")
        if not config.get("expression"):
            raise ValueError("calculatedColumn requires 'expression'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.add_column(
            inputs["in"], config["column_name"], config["expression"]
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column_name"]
        expr = config["expression"]
        return f"{dst} = {src}.assign(**{{{col!r}: {src}.eval({expr!r})}})"
