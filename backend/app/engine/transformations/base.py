from abc import ABC, abstractmethod
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend


class BaseTransformation(ABC):
    """A single visual node's data operation.

    Transformations are engine-agnostic: ``execute`` receives an
    :class:`~app.engine.backends.base.EngineBackend` and delegates the actual
    DataFrame work to it, so the same node runs on pandas or polars unchanged.

    Handle conventions:
    - Single-input nodes read ``inputs["in"]`` and write ``{"out": ...}``.
    - Join reads ``inputs["left"]`` / ``inputs["right"]``.
    - Concat reads every value in ``inputs`` (variadic).
    """

    type: str

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None: ...

    @abstractmethod
    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]: ...

    @abstractmethod
    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str: ...
