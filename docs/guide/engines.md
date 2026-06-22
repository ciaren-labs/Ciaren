---
title: Engines (polars / pandas)
description: How FlowFrame runs flows on polars or pandas, and how it exports code
search: engines polars pandas default execution mode export code timeout
---

# Engines: polars & pandas

FlowFrame executes flows through a small **engine abstraction**, so the same
visual flow runs on either **polars** or **pandas**. Every transformation node is
engine-agnostic — it knows how to run on both and how to generate code for both.

## The default is polars

The default dataframe engine is **polars** (`settings.DEFAULT_ENGINE = "polars"`).
polars is fast and memory-light on small-to-medium data, which suits FlowFrame's
target use cases. pandas is fully supported and remains a first-class choice.

You can change the server-wide default:

```bash
# backend/.env
FLOWFRAME_DEFAULT_ENGINE=pandas
```

```bash
# or per process
flowframe serve --engine pandas
```

## Choosing an engine per run

A single run can override the default. In the UI, pick the engine when you run a
flow; over the API, pass it in the run body:

```bash
curl -X POST http://localhost:8000/api/flows/{flow_id}/runs \
  -H "Content-Type: application/json" -d '{"engine": "pandas"}'
```

The chosen engine is **recorded on the run**, so the run is reproducible and you
can see which engine produced a given output.

## Code export is dual

`POST /api/flows/{flow_id}/export/python` returns **both** versions of the flow's
code — the pandas script and the polars script — generated from the same graph.
Use whichever library your downstream code prefers; both are standalone and
readable.

```python
# pandas
import pandas as pd
df_1 = pd.read_csv("sales.csv")
df_2 = df_1.dropna(subset=['amount'])
df_3 = df_2.groupby(['region']).agg({'amount': 'sum'}).reset_index()
df_3.to_csv("summary.csv", index=False)
```

```python
# polars
import polars as pl
df_1 = pl.read_csv("sales.csv")
df_2 = df_1.drop_nulls(subset=['amount'])
df_3 = df_2.group_by(['region']).agg([pl.col('amount').sum().alias('amount')])
df_3.write_csv("summary.csv")
```

## Execution mode: thread vs. process

Flow compute is synchronous (pandas/polars), so FlowFrame runs it **off the event
loop** to avoid blocking the API. `EXECUTION_MODE` selects how:

- **`thread`** (default) — a worker thread. Simple; shares the GIL.
- **`process`** — a `ProcessPoolExecutor`, for true multi-core parallelism. Only
  picklable arguments cross the process boundary, so the database session always
  stays in the parent process.

```bash
flowframe serve --execution-mode process
```

## Run timeouts

`RUN_TIMEOUT_SECONDS` (default `0` = no limit) abandons a run that overruns:

- in **`process`** mode, the worker process is recycled to reclaim the CPU;
- in **`thread`** mode, the run is abandoned (the thread itself finishes).

```bash
# backend/.env
FLOWFRAME_RUN_TIMEOUT_SECONDS=300
```

Each node also records a `duration_ms` in the run, so you can spot the slow step.

## Notes & gotchas

- The two engines aim for equivalent results, but edge cases (null handling,
  dtype inference, ordering) can differ. The exported code mirrors exactly what
  each engine does.
- `calculatedColumn` uses pandas `df.eval` and polars `pl.sql_expr` under the
  hood — keep expressions to arithmetic over columns (e.g. `price * quantity`).

## See also

- [Transformations Reference](/transformations/overview) — per-node generated code
- [CLI Reference](/guide/cli) — `--engine`, `--execution-mode`, and env vars
- [Projects & Runs](/guide/projects-and-runs) — inspecting run results
