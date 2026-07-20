"""Notebook codegen: splitting a generated script into valid .ipynb cells.

Verifies that:
- ``script_to_notebook`` produces a valid nbformat v4 structure.
- Cells are split at blank-line boundaries (paragraph breaks).
- The notebook's combined cell source is equivalent to the original script.
- A round-trip through ``exec`` of all cells reproduces the same result as
  running the original ``.py`` script.
"""

import json
import tempfile
from pathlib import Path

from app.engine.codegen import CodeGenerator
from app.engine.notebook_codegen import (
    _split_into_cells,
    script_to_notebook,
    script_to_notebook_json,
)
from app.engine.polars_codegen import PolarsCodeGenerator

# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def _simple_graph() -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }


def test_notebook_structure_is_valid_nbformat_v4() -> None:
    code = CodeGenerator().generate(_simple_graph(), {"d": "sales.csv"})
    nb = script_to_notebook(code)
    assert nb["nbformat"] == 4
    assert isinstance(nb["nbformat_minor"], int)
    assert isinstance(nb["cells"], list)
    assert len(nb["cells"]) >= 1
    meta = nb["metadata"]
    assert meta["kernelspec"]["language"] == "python"
    assert meta["language_info"]["name"] == "python"


def test_notebook_cells_are_all_code() -> None:
    code = CodeGenerator().generate(_simple_graph(), {"d": "sales.csv"})
    nb = script_to_notebook(code)
    for cell in nb["cells"]:
        assert cell["cell_type"] == "code"
        assert isinstance(cell["source"], list)
        assert cell["execution_count"] is None
        assert cell["outputs"] == []


def test_notebook_flow_name_adds_markdown_title() -> None:
    code = CodeGenerator().generate(_simple_graph(), {"d": "sales.csv"})
    nb = script_to_notebook(code, flow_name="My Pipeline")
    assert nb["cells"][0]["cell_type"] == "markdown"
    assert nb["cells"][0]["source"] == ["# My Pipeline"]
    for cell in nb["cells"][1:]:
        assert cell["cell_type"] == "code"


def test_notebook_json_is_valid_json() -> None:
    code = CodeGenerator().generate(_simple_graph(), {"d": "sales.csv"})
    raw = script_to_notebook_json(code, flow_name="Test")
    parsed = json.loads(raw)
    assert parsed["nbformat"] == 4


def test_empty_script_produces_single_empty_cell() -> None:
    nb = script_to_notebook("")
    assert len(nb["cells"]) == 1
    assert nb["cells"][0]["source"] == []


# ---------------------------------------------------------------------------
# Cell splitting
# ---------------------------------------------------------------------------


def test_split_into_cells_by_blank_lines() -> None:
    code = "import pandas as pd\n\ndf = pd.read_csv('x.csv')\n\ndf.head()\n"
    cells = _split_into_cells(code)
    assert cells == ["import pandas as pd", "df = pd.read_csv('x.csv')", "df.head()"]


def test_split_preserves_multiline_blocks() -> None:
    code = (
        "import pandas as pd\n"
        "\n"
        "df = pd.read_csv('x.csv')\n"
        "df = df.dropna()\n"
        "df = df.head(5)\n"
        "\n"
        "df.to_csv('out.csv')\n"
    )
    cells = _split_into_cells(code)
    assert len(cells) == 3
    assert "import pandas as pd" in cells[0]
    assert "df.dropna()" in cells[1]
    assert "to_csv" in cells[2]


# ---------------------------------------------------------------------------
# Equivalence: notebook cells produce the same output as the .py script
# ---------------------------------------------------------------------------


def _write_sample_csv(path: Path) -> None:
    path.write_text("a,b\n1,2\n3,4\n5,6\n")


def _all_code_cells_source(nb: dict) -> str:
    """Concatenate all code cell sources, separated by newlines."""
    parts: list[str] = []
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        if src.strip():
            parts.append(src)
    return "\n\n".join(parts) + "\n"


def test_pandas_notebook_exec_matches_script() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "data.csv"
        out_py = Path(tmpdir) / "out_py.csv"
        _write_sample_csv(csv_path)

        graph = {
            "nodes": [
                {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
                {"id": "h", "type": "limitRows", "data": {"config": {"n": 2}}},
                {"id": "out", "type": "csvOutput", "data": {"config": {"path": str(out_py)}}},
            ],
            "edges": [
                {"id": "e1", "source": "in", "target": "h"},
                {"id": "e2", "source": "h", "target": "out"},
            ],
        }
        code = CodeGenerator().generate(graph, {"d": str(csv_path)})
        nb = script_to_notebook(code)
        # Run .py script (writes to out_py).
        exec(compile(code, "<pandas.py>", "exec"), {})  # noqa: S102
        py_content = out_py.read_text()
        # Run notebook cells (writes to out_nb).
        nb_code = _all_code_cells_source(nb)
        exec(compile(nb_code, "<notebook>", "exec"), {})  # noqa: S102
        nb_content = out_py.read_text()
        assert py_content == nb_content


def test_polars_notebook_exec_matches_script() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "data.csv"
        out_path = Path(tmpdir) / "out.csv"
        _write_sample_csv(csv_path)

        graph = {
            "nodes": [
                {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
                {"id": "h", "type": "limitRows", "data": {"config": {"n": 2}}},
                {"id": "out", "type": "csvOutput", "data": {"config": {"path": str(out_path)}}},
            ],
            "edges": [
                {"id": "e1", "source": "in", "target": "h"},
                {"id": "e2", "source": "h", "target": "out"},
            ],
        }
        code = PolarsCodeGenerator().generate(graph, {"d": str(csv_path)})
        nb = script_to_notebook(code)
        # Run .py script.
        exec(compile(code, "<polars.py>", "exec"), {})  # noqa: S102
        py_content = out_path.read_text()
        # Run notebook cells.
        nb_code = _all_code_cells_source(nb)
        exec(compile(nb_code, "<notebook>", "exec"), {})  # noqa: S102
        nb_content = out_path.read_text()
        assert py_content == nb_content


def test_polars_lazy_notebook_exec_matches_script() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "data.csv"
        out_path = Path(tmpdir) / "out.csv"
        _write_sample_csv(csv_path)

        graph = {
            "nodes": [
                {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
                {"id": "h", "type": "limitRows", "data": {"config": {"n": 2}}},
                {"id": "out", "type": "csvOutput", "data": {"config": {"path": str(out_path)}}},
            ],
            "edges": [
                {"id": "e1", "source": "in", "target": "h"},
                {"id": "e2", "source": "h", "target": "out"},
            ],
        }
        code = PolarsCodeGenerator().generate(graph, {"d": str(csv_path)}, lazy=True)
        nb = script_to_notebook(code)
        # Run .py script.
        exec(compile(code, "<polars-lazy.py>", "exec"), {})  # noqa: S102
        py_content = out_path.read_text()
        # Run notebook cells.
        nb_code = _all_code_cells_source(nb)
        exec(compile(nb_code, "<notebook>", "exec"), {})  # noqa: S102
        nb_content = out_path.read_text()
        assert py_content == nb_content


# ---------------------------------------------------------------------------
# Edge case: multi-step pipeline with multiple nodes
# ---------------------------------------------------------------------------


def test_multi_step_pipeline_notebook_structure() -> None:
    """A pipeline with input -> head -> output produces multiple cells."""
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "h", "type": "limitRows", "data": {"config": {"n": 5}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "h"},
            {"id": "e2", "source": "h", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, {"d": "data.csv"})
    nb = script_to_notebook(code)
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) >= 2
    first_src = "".join(code_cells[0]["source"])
    assert "import pandas as pd" in first_src


def test_notebook_cells_combined_equals_script() -> None:
    """Concatenating all code cells reproduces the original script's non-blank lines."""
    code = CodeGenerator().generate(_simple_graph(), {"d": "sales.csv"})
    nb = script_to_notebook(code)
    cell_sources = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    combined = "\n\n".join(cell_sources) + "\n"
    original_lines = [ln for ln in code.split("\n") if ln.strip()]
    combined_lines = [ln for ln in combined.split("\n") if ln.strip()]
    assert original_lines == combined_lines
