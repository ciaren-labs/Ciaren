# SPDX-License-Identifier: AGPL-3.0-only
"""trainTestSplit — split a dataframe into train and test outputs.

A two-output node: ``{"train": ..., "test": ...}``. The seed is **required** (no
default) so a run is reproducible; allowing a silent random split would quietly
break the reproducibility contract every ML run depends on.
"""

from __future__ import annotations

import logging
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.ml.base import MLSchema, MLTransformation

logger = logging.getLogger(__name__)

# Guardrails — keep these in one place so node + tests agree.
MIN_TRAIN_ROWS = 10


class TrainTestSplitTransformation(MLTransformation):
    type = "trainTestSplit"
    input_handles = ("in",)

    def validate_config(self, config: dict[str, Any]) -> None:
        seed = config.get("seed")
        # bool is an int subclass — reject True/False masquerading as a seed.
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError(
                "trainTestSplit requires an integer 'seed' for reproducibility."
            )
        test_size = config.get("test_size", 0.2)
        if not isinstance(test_size, (int, float)) or isinstance(test_size, bool) or not (0.0 < test_size < 1.0):
            raise ValueError("trainTestSplit 'test_size' must be a number strictly between 0 and 1.")
        stratify = config.get("stratify_column")
        if stratify is not None and not isinstance(stratify, str):
            raise ValueError("trainTestSplit 'stratify_column' must be a column name or null.")

    def validate_with_schema(self, config: dict[str, Any], schema: MLSchema) -> None:
        stratify = config.get("stratify_column")
        if stratify is not None and stratify not in schema.columns:
            raise ValueError(
                f"trainTestSplit: stratify column {stratify!r} is not in the input columns {schema.columns}."
            )
        # Reject obviously-too-small inputs before any compute.
        test_size = config.get("test_size", 0.2)
        if schema.row_count is not None:
            approx_train = int(schema.row_count * (1.0 - test_size))
            if approx_train < MIN_TRAIN_ROWS:
                raise ValueError(
                    f"trainTestSplit: the training set would have ~{approx_train} rows; "
                    f"at least {MIN_TRAIN_ROWS} are required. Reduce test_size or add data."
                )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        from sklearn.model_selection import train_test_split

        pdf = engine.to_pandas(inputs["in"])
        test_size = config.get("test_size", 0.2)
        seed = config["seed"]
        stratify_col = config.get("stratify_column")

        stratify = None
        if stratify_col:
            if stratify_col not in pdf.columns:
                raise ValueError(
                    f"trainTestSplit: stratify column {stratify_col!r} is not in the input columns {list(pdf.columns)}."
                )
            stratify = pdf[stratify_col]
            self._check_stratifiable(stratify, stratify_col)

        train_df, test_df = train_test_split(pdf, test_size=test_size, random_state=seed, stratify=stratify)

        if len(train_df) < MIN_TRAIN_ROWS:
            raise ValueError(
                f"trainTestSplit: the training set has only {len(train_df)} rows; "
                f"at least {MIN_TRAIN_ROWS} are required. Reduce test_size or add data."
            )

        train_df = train_df.reset_index(drop=True)
        test_df = test_df.reset_index(drop=True)
        return {
            "train": engine.from_pandas(train_df),
            "test": engine.from_pandas(test_df),
        }

    def _check_stratifiable(self, stratify: Any, column: str) -> None:
        """Guard the two stratification footguns: a continuous (regression) target,
        and a class with too few samples to appear in both splits."""
        import pandas as pd

        if pd.api.types.is_float_dtype(stratify):
            logger.warning(
                "trainTestSplit: stratifying on float column %r looks like a "
                "regression target; stratification expects discrete classes.",
                column,
            )
        counts = stratify.value_counts(dropna=False)
        if len(counts) and int(counts.min()) < 2:
            smallest = counts.idxmin()
            raise ValueError(
                f"trainTestSplit: class {smallest!r} in {column!r} has only "
                f"{int(counts.min())} sample(s) — cannot stratify. Reduce test_size, "
                f"merge rare classes, or remove the stratify column."
            )

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src = input_vars["in"]
        train, test = output_vars["train"], output_vars["test"]
        test_size = config.get("test_size", 0.2)
        seed = config["seed"]
        stratify_col = config.get("stratify_column")
        stratify = f", stratify={src}[{stratify_col!r}]" if stratify_col else ""
        # reset_index mirrors execute(): the two splits get a fresh 0..n index so
        # downstream index-based ops (concat, .loc) behave the same as in the run.
        return (
            f"{train}, {test} = train_test_split("
            f"{src}, test_size={test_size!r}, random_state={seed!r}{stratify})\n"
            f"{train} = {train}.reset_index(drop=True)\n"
            f"{test} = {test}.reset_index(drop=True)"
        )

    def imports(self, config: dict[str, Any]) -> list[str]:
        return ["from sklearn.model_selection import train_test_split"]
