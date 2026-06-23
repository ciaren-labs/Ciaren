"""Single source of truth for input/output node types and their file formats.

Input and output node types used to be duplicated as literal sets/dicts across
the executor, code generator, graph validation, and dataset resolver. Keeping
them here keeps those four in sync and gives a new I/O node type (e.g. a SQL
source/sink) exactly one place to register.
"""

# Input node type -> source_type understood by ``EngineBackend.read``.
INPUT_SOURCE_TYPES: dict[str, str] = {
    "csvInput": "csv",
    "excelInput": "excel",
    "parquetInput": "parquet",
}

# Output node type -> source_type understood by ``EngineBackend.write``.
# ``sqlOutput`` is materialized as a parquet by the executor; the execution
# service then pushes that parquet to the database via a connector.
OUTPUT_SOURCE_TYPES: dict[str, str] = {
    "csvOutput": "csv",
    "excelOutput": "excel",
    "parquetOutput": "parquet",
    "sqlOutput": "parquet",
}

# File extension written for each output source_type.
OUTPUT_SUFFIX: dict[str, str] = {
    "csv": ".csv",
    "excel": ".xlsx",
    "parquet": ".parquet",
}

# Database-backed I/O nodes (resolved via app/connectors, not the file engine).
SQL_INPUT_TYPE = "sqlInput"
SQL_OUTPUT_TYPE = "sqlOutput"

#: Membership sets — use these for ``in`` checks. ``sqlInput`` is not a file
#: source_type (it is materialized to parquet in the resolution layer), so it is
#: added to the input set explicitly; ``sqlOutput`` already lives in the output map.
INPUT_TYPES: frozenset[str] = frozenset(INPUT_SOURCE_TYPES) | {SQL_INPUT_TYPE}
OUTPUT_TYPES: frozenset[str] = frozenset(OUTPUT_SOURCE_TYPES)
