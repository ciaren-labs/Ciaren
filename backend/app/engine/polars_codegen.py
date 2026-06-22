"""Generate readable **polars** code for a flow graph.

Mirrors :class:`app.engine.codegen.CodeGenerator` (pandas) but emits polars.
Kept as a standalone generator — rather than a method on every transformation —
so the polars mapping lives in one reviewable place.
"""

from typing import Any

from app.engine.graph import topological_sort, validate_graph

_INPUT_READ = {
    "csvInput": "pl.read_csv",
    "excelInput": "pl.read_excel",
    "parquetInput": "pl.read_parquet",
}
_OUTPUT_WRITE = {
    "csvOutput": "write_csv",
    "excelOutput": "write_excel",
    "parquetOutput": "write_parquet",
}

_SIMPLE_OPS = {"==", "!=", ">", ">=", "<", "<="}
# Fill-null strategy -> polars fill_null(strategy=...) name.
_FILL_STRATEGY = {
    "mean": "mean",
    "min": "min",
    "max": "max",
    "zero": "zero",
    "ffill": "forward",
    "bfill": "backward",
}
_CAST_DTYPE = {
    "integer": "pl.Int64",
    "float": "pl.Float64",
    "boolean": "pl.Boolean",
    "string": "pl.Utf8",
}
_STRING_OP = {
    "lower": "to_lowercase()",
    "upper": "to_uppercase()",
    "strip": "strip_chars()",
    "title": "to_titlecase()",
    "capitalize": "to_titlecase()",
}
_AGG_FUNC = {
    "sum": "sum",
    "mean": "mean",
    "count": "count",
    "min": "min",
    "max": "max",
    "median": "median",
    "nunique": "n_unique",
}
# pandas drop_duplicates keep -> polars unique keep
_KEEP = {"first": "first", "last": "last", False: "none"}
# pandas merge how -> polars join how
_JOIN_HOW = {"inner": "inner", "left": "left", "right": "right", "outer": "full"}


class PolarsCodeGenerator:
    def generate(self, graph: dict[str, Any], dataset_paths: dict[str, str]) -> str:
        validate_graph(graph)
        order = topological_sort(graph)

        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in graph.get("edges", []):
            incoming[edge["target"]].append(edge)

        lines: list[str] = ["import polars as pl", ""]
        var_counter = 0
        node_var: dict[str, str] = {}

        def next_var() -> str:
            nonlocal var_counter
            var_counter += 1
            return f"df_{var_counter}"

        for node_id in order:
            node = nodes_by_id[node_id]
            node_type = node["type"]
            config: dict[str, Any] = node.get("data", {}).get("config", {})

            if node_type in _INPUT_READ:
                var = next_var()
                node_var[node_id] = var
                path = dataset_paths.get(config.get("dataset_id", ""), "input.csv")
                lines.append(f'{var} = {_INPUT_READ[node_type]}("{path}")')
            elif node_type in _OUTPUT_WRITE:
                src_var = node_var[incoming[node_id][0]["source"]]
                out_path = config.get("path", "output.csv")
                lines.append(f'{src_var}.{_OUTPUT_WRITE[node_type]}("{out_path}")')
            else:
                input_vars: dict[str, str] = {}
                for i, e in enumerate(incoming[node_id]):
                    handle = e.get("targetHandle") or "in"
                    if handle in input_vars:
                        handle = f"{handle}_{i}"
                    input_vars[handle] = node_var[e["source"]]
                out_var = next_var()
                node_var[node_id] = out_var
                lines.append(_node_code(node_type, config, input_vars, out_var))

        return "\n".join(lines) + "\n"


def _node_code(
    node_type: str, config: dict[str, Any], inputs: dict[str, str], dst: str
) -> str:
    src = inputs.get("in", next(iter(inputs.values()), "df"))

    if node_type == "dropNulls":
        subset = config.get("subset")
        if subset:
            return f"{dst} = {src}.drop_nulls(subset={subset!r})"
        return f"{dst} = {src}.drop_nulls()"

    if node_type == "fillNulls":
        columns = config.get("columns")
        strategy = config.get("strategy", "constant")
        cols_iter = f"{columns!r}" if columns else f"{src}.columns"
        if strategy == "constant":
            value = config.get("value")
            if columns:
                return (
                    f"{dst} = {src}.with_columns("
                    f"[pl.col(c).fill_null({value!r}) for c in {columns!r}])"
                )
            return f"{dst} = {src}.fill_null({value!r})"
        if strategy in _FILL_STRATEGY:
            strat = _FILL_STRATEGY[strategy]
            return (
                f"{dst} = {src}.with_columns("
                f"[pl.col(c).fill_null(strategy={strat!r}) for c in {cols_iter}])"
            )
        # median / mode: compute the value per column, then fill.
        agg = "median" if strategy == "median" else "mode().first"
        return (
            f"{dst} = {src}.with_columns("
            f"[pl.col(c).fill_null({src}[c].{agg}()) for c in {cols_iter}])"
        )

    if node_type == "dropColumns":
        return f"{dst} = {src}.drop({config['columns']!r})"

    if node_type == "renameColumns":
        return f"{dst} = {src}.rename({config['mapping']!r})"

    if node_type == "selectColumns":
        return f"{dst} = {src}.select({config['columns']!r})"

    if node_type == "removeDuplicates":
        keep = _KEEP.get(config.get("keep", "first"), "first")
        subset = config.get("subset")
        args = f"keep={keep!r}, maintain_order=True"
        if subset:
            args = f"subset={subset!r}, {args}"
        return f"{dst} = {src}.unique({args})"

    if node_type == "filterRows":
        col, op = config["column"], config["operator"]
        val = config.get("value")
        if op in _SIMPLE_OPS:
            return f"{dst} = {src}.filter(pl.col({col!r}) {op} {val!r})"
        if op == "isnull":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_null())"
        if op == "notnull":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_not_null())"
        if op == "between":
            return (
                f"{dst} = {src}.filter(pl.col({col!r})"
                f".is_between({val!r}, {config.get('value2')!r}))"
            )
        if op == "in":
            items = (
                val
                if isinstance(val, list)
                else [v.strip() for v in str(val).split(",") if v.strip()]
            )
            return f"{dst} = {src}.filter(pl.col({col!r}).is_in({items!r}))"
        if op in {"contains", "startswith", "endswith"}:
            method = {
                "contains": "contains",
                "startswith": "starts_with",
                "endswith": "ends_with",
            }[op]
            return f"{dst} = {src}.filter(pl.col({col!r}).cast(pl.Utf8).str.{method}({val!r}))"
        raise ValueError(f"Unknown filter operator: {op!r}")

    if node_type == "castDtypes":
        lines = [f"{dst} = {src}"]
        for column, dtype in config["casts"].items():
            if dtype == "datetime":
                lines.append(f"{dst} = {dst}.with_columns(pl.col({column!r}).str.to_datetime())")
            else:
                lines.append(
                    f"{dst} = {dst}.with_columns(pl.col({column!r}).cast({_CAST_DTYPE[dtype]}))"
                )
        return "\n".join(lines)

    if node_type == "sortRows":
        columns = config["columns"]
        ascending = config.get("ascending", True)
        descending = (
            [not a for a in ascending]
            if isinstance(ascending, list)
            else not ascending
        )
        return f"{dst} = {src}.sort({columns!r}, descending={descending!r})"

    if node_type == "limitRows":
        return f"{dst} = {src}.head({config['n']!r})"

    if node_type == "replaceValues":
        col = config["column"]
        return (
            f"{dst} = {src}.with_columns("
            f"pl.col({col!r}).replace({config['to_replace']!r}, {config['value']!r}))"
        )

    if node_type == "stringTransform":
        col = config["column"]
        method = _STRING_OP[config["operation"]]
        return f"{dst} = {src}.with_columns(pl.col({col!r}).str.{method})"

    if node_type == "calculatedColumn":
        col, expr = config["column_name"], config["expression"]
        # pl.sql_expr handles arithmetic expressions like "price * quantity".
        return f"{dst} = {src}.with_columns(pl.sql_expr({expr!r}).alias({col!r}))"

    if node_type == "groupByAggregate":
        by = config["group_by"]
        aggs = ", ".join(
            f"pl.col({col!r}).{_AGG_FUNC.get(func, func)}().alias({col!r})"
            for col, func in config["aggregations"].items()
        )
        return f"{dst} = {src}.group_by({by!r}).agg([{aggs}])"

    if node_type == "join":
        left, right = inputs["left"], inputs["right"]
        how = _JOIN_HOW.get(config.get("how", "inner"), "inner")
        on = config["on"]
        return f"{dst} = {left}.join({right}, on={on!r}, how={how!r})"

    if node_type == "concatRows":
        srcs = ", ".join(inputs.values())
        return f"{dst} = pl.concat([{srcs}])"

    raise ValueError(f"Unknown node type: {node_type!r}")
