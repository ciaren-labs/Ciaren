---
title: Transformations Reference
description: Every transformation node, its config, and the code it generates
search: transformations nodes all reference config pandas polars
---

# Transformations Reference

FlowFrame ships with file input/output nodes plus **28 transformation nodes** for
cleaning, reshaping, and combining data. Each node maps to one clear dataframe
operation and contributes to the exported Python — both the **pandas** and the
**polars** version.

This page is the map. **Each node also has its own reference page** with use
cases, full configuration, generated code, and tips — follow the links below or
use the sidebar.

::: info Source of truth
The authoritative list lives in
[`backend/app/engine/registry.py`](https://github.com/rodrigo-arenas/FlowFrame/blob/main/backend/app/engine/registry.py).
Each node's `type` (shown on its page) is the value stored in the flow graph at
`node.type`; its settings live at `node.data.config`.
:::

## Node categories

The node palette (left panel in the editor) groups all nodes into color-coded categories. Click a category to expand it, then drag a node onto the canvas or click to place it.

![Flow editor showing the node palette with Inputs, Cleaning, Columns, Reshape, Analytics, Machine Learning, and Outputs categories](/screenshots/editor-full.png)

<NodeCategoryGrid />

## How nodes connect

A flow is a graph of `nodes` and `edges` (React Flow-compatible). Most nodes have
a single input handle (`in`) and output handle (`out`). Two are special:

- **[Join](./join.md)** has two inputs: `left` and `right`.
- **[Union / Concat](./union-concat.md)** accepts any number of inputs.

A minimal complete pipeline always starts with at least one **Input** node and
ends with at least one **Output** node. Everything in between is optional cleaning
and transformation.

<FlowPipeline :nodes='[
  {"type":"input","label":"Input node","detail":"CSV · Excel · Parquet · SQL · Storage"},
  {"type":"clean","label":"Clean nodes","detail":"columns · nulls · rows · text · numeric"},
  {"type":"transform","label":"Transform nodes","detail":"reshape · combine · analytics"},
  {"type":"output","label":"Output node","detail":"CSV · Excel · Parquet · SQL · Storage"}
]' />

## Choosing the right node

| I want to... | Use |
| -------------- | ----- |
| Remove columns | [Drop columns](./drop-columns.md) |
| Fix column names | [Rename columns](./rename-columns.md) |
| Keep only some columns | [Select columns](./select-columns.md) |
| Change a column's type | [Cast types](./cast-types.md) |
| Remove rows with missing values | [Drop nulls](./drop-nulls.md) |
| Fill missing values | [Fill nulls](./fill-nulls.md) |
| Remove duplicate rows | [Remove duplicates](./remove-duplicates.md) |
| Keep rows matching a condition | [Filter rows](./filter-rows.md) |
| Create a new computed column | [Calculated column](./calculated-column.md) |
| Sum / count / average by group | [Group by + aggregate](./group-by-aggregate.md) |
| Read from S3 / GCS / Azure Blob | [Storage input](./storage-input.md) |
| Write to S3 / GCS / Azure Blob | [Storage output](./storage-output.md) |
| Read from a database | [SQL input](./sql-input.md) |
| Combine two datasets on a key | [Join](./join.md) |
| Stack datasets row-wise | [Union / Concat](./union-concat.md) |
| Reshape long ↔ wide | [Pivot](./pivot.md) / [Unpivot](./unpivot.md) |
| Bucket a number into bands | [Bin column](./bin-column.md) |
| Split a date into year/month/… | [Extract date parts](./extract-date-parts.md) |
| Turn date text into real dates | [Parse dates](./parse-dates.md) |
| Split one column into several | [Split column](./split-column.md) |
| Recode values (A→Pass, B→Pass…) | [Map values](./map-values.md) |
| Rank, running total, lag/lead | [Window function](./window-function.md) |
| Bucket with custom if/else logic | [Conditional column](./conditional-column.md) |

## Generated code: pandas and polars

Every node implements both `to_python_code` (pandas) and `to_polars_code`
(polars), so [exporting a flow](/guide/engines#code-export) gives you a runnable
script in either dialect. The per-node pages show the **pandas** export; the
polars export is equivalent and produced from the same config. The two engines
are kept at parity by a test suite that runs each node on both.

## Current limitations

| Limitation | Workaround |
| ----------- | ----------- |
| Join takes two inputs at a time | Chain multiple join nodes |
| `rank`/`dense_rank` rank by a single order column | Pre-sort, or use a calculated key |
| `calculatedColumn` evaluates arithmetic expressions | For complex logic, use [Conditional column](./conditional-column.md), or export and edit the Python |

## Custom transformations

Need a node that isn't built in?
[Open an issue](https://github.com/rodrigo-arenas/FlowFrame/issues) or
[contribute one](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md).
Each transformation implements `validate_config`, `execute`, `to_python_code`,
and `to_polars_code`, and is registered in `app/engine/registry.py` with tests.

## Next steps

- [Examples](/examples/sales-analysis) — sample workflows end to end
- [Engines](/guide/engines) — polars vs. pandas and code export
- [REST API](/api/rest-api) — driving flows programmatically
