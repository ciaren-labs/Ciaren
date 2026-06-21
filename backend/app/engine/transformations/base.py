from abc import ABC, abstractmethod

import pandas as pd


class BaseTransformation(ABC):
    type: str

    @abstractmethod
    def validate_config(self, config: dict) -> None: ...

    @abstractmethod
    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict,
    ) -> dict[str, pd.DataFrame]: ...

    @abstractmethod
    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict,
    ) -> str: ...
