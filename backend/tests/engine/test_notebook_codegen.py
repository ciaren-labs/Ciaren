"""Notebook codegen: splitting a generated script into valid .ipynb cells.

Verifies that:
- ``script_to_notebook`` produces a valid nbformat v4 structure.
- Cells split only at blank lines between top-level statements, never inside one.
- Every code cell parses on its own, and running the cells one at a time in a
  shared namespace (as Jupyter does) gives the same result as the ``.py`` script.
"""

import ast
import json
import platform
import re
from pathlib import Path

import pytest

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
    nb = script_to_notebook(code, flow_name="Sales")
    assert (nb["nbformat"], nb["nbformat_minor"]) == (4, 5)
    assert len(nb["cells"]) >= 2
    # nbformat 4.5 requires every cell to carry a unique id of this shape.
    ids = [cell["id"] for cell in nb["cells"]]
    assert all(re.fullmatch(r"[a-zA-Z0-9-_]{1,64}", cell_id) for cell_id in ids)
    assert len(set(ids)) == len(ids)
    meta = nb["metadata"]
    assert meta["kernelspec"]["language"] == "python"
    assert meta["language_info"] == {"name": "python", "version": platform.python_version()}


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


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            "import pandas as pd\n\ndef f(df):\n    a = 1\n\n    return df\n\nf(1)\n",
            ["import pandas as pd", "def f(df):\n    a = 1\n\n    return df", "f(1)"],
            id="blank-line-in-function-body",
        ),
        pytest.param(
            'x = 1\n\nq = """first\n\nthird"""\n\nprint(q)\n',
            ["x = 1", 'q = """first\n\nthird"""', "print(q)"],
            id="blank-line-in-multiline-string",
        ),
        pytest.param(
            "import functools\n\n@functools.cache\n\ndef f():\n    return 1\n",
            ["import functools", "@functools.cache\n\ndef f():\n    return 1"],
            id="blank-line-after-decorator",
        ),
        pytest.param(
            "total = sum(\n    [1,\n\n     2]\n)\n",
            ["total = sum(\n    [1,\n\n     2]\n)"],
            id="blank-line-in-brackets",
        ),
        pytest.param(
            "a = 1\n\n# explain b\nb = 2\n# trailing note\n",
            ["a = 1", "# explain b\nb = 2\n# trailing note"],
            id="comments-stay-with-their-statements",
        ),
        pytest.param(
            'a = """\r\r\r"""\n\ndef f():\n    x = 1\n\n    return x\n',
            ['a = """\n\n\n"""', "def f():\n    x = 1\n\n    return x"],
            id="lone-carriage-returns-count-as-line-breaks",
        ),
        pytest.param(
            "def broken(:\n    pass\n\nx = 1\n",
            ["def broken(:\n    pass\n\nx = 1"],
            id="syntax-error-is-one-cell",
        ),
    ],
)
def test_split_never_breaks_a_statement(code: str, expected: list[str]) -> None:
    assert _split_into_cells(code) == expected


# ---------------------------------------------------------------------------
# Generated notebooks run cell by cell like the .py script
# ---------------------------------------------------------------------------

# A pythonTransform script with blank lines in its body and inside a string
# literal: the generator emits it as a function, which must stay in one cell.
_TRANSFORM_SCRIPT = 'total = df["a"].sum()\n\nlabel = """first\n\nthird"""\nreturn df.head(2)'

_VARIANTS = pytest.mark.parametrize("variant", ["pandas", "polars", "polars_lazy"])


def _transform_flow_script(variant: str, tmp_path: Path) -> tuple[str, Path]:
    """Script for csv -> pythonTransform -> csv, plus the path it writes to."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n5,6\n")
    out_path = tmp_path / "out.csv"
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "t", "type": "pythonTransform", "data": {"config": {"script": _TRANSFORM_SCRIPT}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": str(out_path)}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "t"},
            {"id": "e2", "source": "t", "target": "out"},
        ],
    }
    datasets = {"d": str(csv_path)}
    if variant == "pandas":
        return CodeGenerator().generate(graph, datasets), out_path
    return PolarsCodeGenerator().generate(graph, datasets, lazy=variant == "polars_lazy"), out_path


def _code_cells(nb: dict) -> list[str]:
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


@_VARIANTS
def test_every_code_cell_parses_on_its_own(variant: str, tmp_path: Path) -> None:
    code, _ = _transform_flow_script(variant, tmp_path)
    for cell in _code_cells(script_to_notebook(code, flow_name="Flow")):
        ast.parse(cell)


@_VARIANTS
def test_cells_run_one_by_one_match_script(variant: str, tmp_path: Path) -> None:
    code, out_path = _transform_flow_script(variant, tmp_path)
    exec(compile(code, "<script>", "exec"), {})  # noqa: S102
    expected = out_path.read_text()
    out_path.unlink()

    # One cell at a time into a shared namespace, the way Jupyter runs them.
    namespace: dict = {}
    for i, cell in enumerate(_code_cells(script_to_notebook(code))):
        exec(compile(cell, f"<cell {i}>", "exec"), namespace)  # noqa: S102
    assert out_path.read_text() == expected


@_VARIANTS
def test_notebook_cells_keep_every_script_line(variant: str, tmp_path: Path) -> None:
    """No source line (comments included) is lost; only separating blank lines go."""
    code, _ = _transform_flow_script(variant, tmp_path)
    combined = "\n".join(_code_cells(script_to_notebook(code)))
    assert [ln for ln in combined.split("\n") if ln.strip()] == [ln for ln in code.split("\n") if ln.strip()]


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
    code_cells = _code_cells(script_to_notebook(CodeGenerator().generate(graph, {"d": "data.csv"})))
    assert len(code_cells) >= 2
    assert "import pandas as pd" in code_cells[0]
