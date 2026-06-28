"""The unified File Output node writes every supported format on both engines."""

from __future__ import annotations

import pandas as pd
import pytest

from app.engine.codegen import CodeGenerator
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import validate_graph
from app.engine.node_kinds import OUTPUT_SUFFIX, output_source_type
from app.engine.polars_codegen import PolarsCodeGenerator


def _graph(fmt: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "out1", "type": "fileOutput", "data": {"config": {"format": fmt, "dataset_name": "result"}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }


def test_output_source_type_resolves_format():
    assert output_source_type("fileOutput", {"format": "json"}) == "json"
    assert output_source_type("fileOutput", {}) == "csv"  # default
    assert output_source_type("csvOutput", {}) == "csv"  # legacy still works


def test_output_source_type_rejects_unknown_format():
    with pytest.raises(ValueError, match="unknown format"):
        output_source_type("fileOutput", {"format": "yaml"})


def test_file_output_is_a_valid_terminal():
    validate_graph(_graph("csv"))  # must not raise (fileOutput is an output node)


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
@pytest.mark.parametrize("fmt", ["csv", "excel", "parquet", "json", "text"])
def test_file_output_writes_every_format(tmp_path, engine_name, fmt):
    in_csv = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).to_csv(in_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    outputs = FlowExecutor().execute(
        _graph(fmt),
        dataset_paths={dataset_ref_key("ds1", None): in_csv},
        output_dir=out_dir,
        engine_name=engine_name,
    )
    path = outputs["out1"]
    assert path.exists()
    assert path.suffix == OUTPUT_SUFFIX[fmt]
    assert path.stat().st_size > 0


@pytest.mark.parametrize("fmt,needle", [("csv", "to_csv"), ("json", "to_json"), ("parquet", "to_parquet")])
def test_pandas_codegen_uses_format(fmt, needle):
    code = CodeGenerator().generate(_graph(fmt), {"ds1": "in.csv"})
    assert needle in code
    assert "result" in code  # the chosen filename


@pytest.mark.parametrize("fmt,needle", [("csv", "write_csv"), ("json", "write_json"), ("parquet", "write_parquet")])
def test_polars_codegen_uses_format(fmt, needle):
    code = PolarsCodeGenerator().generate(_graph(fmt), {"ds1": "in.csv"})
    assert needle in code
