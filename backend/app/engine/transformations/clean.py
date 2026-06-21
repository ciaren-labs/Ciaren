import pandas as pd

from app.engine.transformations.base import BaseTransformation


class DropNullsTransformation(BaseTransformation):
    type = "dropNulls"

    def validate_config(self, config: dict) -> None:
        pass  # subset is optional

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        subset = config.get("subset") or None
        return {"default": df.dropna(subset=subset)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src = input_vars["default"]
        dst = output_vars["default"]
        subset = config.get("subset")
        if subset:
            return f'{dst} = {src}.dropna(subset={subset!r})'
        return f"{dst} = {src}.dropna()"


class FillNullsTransformation(BaseTransformation):
    type = "fillNulls"

    def validate_config(self, config: dict) -> None:
        if "value" not in config:
            raise ValueError("fillNulls requires a 'value' config key")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        return {"default": df.fillna(config["value"])}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        return f'{dst} = {src}.fillna({config["value"]!r})'


class DropColumnsTransformation(BaseTransformation):
    type = "dropColumns"

    def validate_config(self, config: dict) -> None:
        if not config.get("columns"):
            raise ValueError("dropColumns requires a non-empty 'columns' list")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        return {"default": df.drop(columns=config["columns"])}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        return f'{dst} = {src}.drop(columns={config["columns"]!r})'


class RenameColumnsTransformation(BaseTransformation):
    type = "renameColumns"

    def validate_config(self, config: dict) -> None:
        if not config.get("mapping") or not isinstance(config["mapping"], dict):
            raise ValueError("renameColumns requires a non-empty 'mapping' dict")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        return {"default": df.rename(columns=config["mapping"])}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        return f'{dst} = {src}.rename(columns={config["mapping"]!r})'


class SelectColumnsTransformation(BaseTransformation):
    type = "selectColumns"

    def validate_config(self, config: dict) -> None:
        if not config.get("columns"):
            raise ValueError("selectColumns requires a non-empty 'columns' list")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        return {"default": df[config["columns"]]}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        return f'{dst} = {src}[{config["columns"]!r}]'


class RemoveDuplicatesTransformation(BaseTransformation):
    type = "removeDuplicates"

    def validate_config(self, config: dict) -> None:
        pass

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        subset = config.get("subset") or None
        keep = config.get("keep", "first")
        return {"default": df.drop_duplicates(subset=subset, keep=keep)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        subset = config.get("subset")
        keep = config.get("keep", "first")
        args = f"keep={keep!r}"
        if subset:
            args = f"subset={subset!r}, {args}"
        return f"{dst} = {src}.drop_duplicates({args})"


class FilterRowsTransformation(BaseTransformation):
    type = "filterRows"

    def validate_config(self, config: dict) -> None:
        required = {"column", "operator", "value"}
        if not required.issubset(config):
            raise ValueError(f"filterRows requires keys: {required}")

    _OPS = {"==", "!=", ">", ">=", "<", "<="}

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        col, op, val = config["column"], config["operator"], config["value"]
        if op not in self._OPS:
            raise ValueError(f"Unsupported operator: {op}")
        return {"default": df.query(f"`{col}` {op} @val", local_dict={"val": val})}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        col, op, val = config["column"], config["operator"], config["value"]
        return f'{dst} = {src}[{src}[{col!r}] {op} {val!r}]'


class SortRowsTransformation(BaseTransformation):
    type = "sortRows"

    def validate_config(self, config: dict) -> None:
        if not config.get("columns"):
            raise ValueError("sortRows requires a non-empty 'columns' list")

    def execute(
        self, inputs: dict[str, pd.DataFrame], config: dict
    ) -> dict[str, pd.DataFrame]:
        df = inputs["default"]
        ascending = config.get("ascending", True)
        return {"default": df.sort_values(by=config["columns"], ascending=ascending)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict
    ) -> str:
        src, dst = input_vars["default"], output_vars["default"]
        ascending = config.get("ascending", True)
        return f'{dst} = {src}.sort_values(by={config["columns"]!r}, ascending={ascending!r})'
