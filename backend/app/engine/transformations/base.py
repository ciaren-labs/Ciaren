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

    #: Named input handles this node reads from. Single-input nodes use the
    #: default ``("in",)``; join overrides it with ``("left", "right")``.
    input_handles: tuple[str, ...] = ("in",)

    #: When true the node accepts an arbitrary number of incoming edges on its
    #: ``"in"`` handle (concat). ``input_handles`` is then advisory.
    multi_input: bool = False

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
    ) -> str:
        """Readable **pandas** code for this node (``df`` variables)."""
        ...

    @abstractmethod
    def to_polars_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        """Readable **polars** code for this node, co-located with ``execute`` and
        ``to_python_code`` so a node's whole definition lives in one place."""
        ...
