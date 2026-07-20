# SPDX-License-Identifier: AGPL-3.0-only
"""Wrap a generated Python script as a Jupyter notebook (``.ipynb``).

The existing pandas / polars code generators produce a complete, runnable script.
This module splits it into logical cells — one per paragraph (blank-line-separated
block) — and wraps the result in a valid nbformat v4 JSON structure **without**
requiring the ``nbformat`` package: the .ipynb schema is simple enough to build
by hand.

Cells are split at blank lines, which the codegen pipeline already inserts as
paragraph breaks around fused method chains (see
:func:`app.engine.codegen_common.insert_paragraph_breaks`).  The first cell
always contains the imports so the notebook can be run top-to-bottom; a
parameters prelude (when present) becomes its own cell for easy tuning.
"""

from __future__ import annotations

import json
from typing import Any

# Notebook format version (nbformat 4, nbformat_minor 5 — widely supported).
_NBFORMAT = 4
_NBFORMAT_MINOR = 5


def _code_cell(source: str, *, execution_count: int | None = None) -> dict[str, Any]:
    """Build a single code cell dict."""
    cell: dict[str, Any] = {
        "cell_type": "code",
        "execution_count": execution_count,
        "metadata": {},
        "source": source.splitlines(keepends=True),
        "outputs": [],
    }
    return cell


def _md_cell(source: str) -> dict[str, Any]:
    """Build a single markdown cell dict."""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def _split_into_cells(code: str) -> list[str]:
    """Split a generated script into cell-sized chunks at blank-line boundaries.

    Consecutive non-empty lines stay in the same cell; a blank line starts a new
    one.  Trailing blank lines are ignored so the last cell is never empty.
    """
    cells: list[str] = []
    current: list[str] = []
    for line in code.split("\n"):
        if line == "":
            if current:
                cells.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        cells.append("\n".join(current))
    return cells


def script_to_notebook(
    code: str,
    *,
    kernel_name: str = "python3",
    flow_name: str | None = None,
) -> dict[str, Any]:
    """Convert a complete Python script into a Jupyter notebook dict.

    ``code`` is the full output of a ``CodeGenerator`` or
    ``PolarsCodeGenerator`` — imports, parameters, and body all in one string.
    The result is a JSON-serialisable dict that, when written to an ``.ipynb``
    file, is openable by JupyterLab, classic Notebook, VS Code, and nbconvert.

    ``kernel_name`` is stored in the notebook metadata so front-ends select the
    right kernel.  ``flow_name`` is optional; when given, a markdown title cell
    is prepended.
    """
    cells: list[dict[str, Any]] = []

    if flow_name:
        cells.append(_md_cell(f"# {flow_name}"))

    for cell_source in _split_into_cells(code):
        cells.append(_code_cell(cell_source))

    if not cells:
        cells.append(_code_cell(""))

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": kernel_name,
                "language": "python",
                "name": kernel_name,
            },
            "language_info": {
                "name": "python",
                "version": "3.12.0",
            },
        },
        "nbformat": _NBFORMAT,
        "nbformat_minor": _NBFORMAT_MINOR,
    }


def script_to_notebook_json(
    code: str,
    *,
    kernel_name: str = "python3",
    flow_name: str | None = None,
) -> str:
    """Like :func:`script_to_notebook` but returns a JSON string."""
    return json.dumps(
        script_to_notebook(code, kernel_name=kernel_name, flow_name=flow_name),
        indent=1,
    )
