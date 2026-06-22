---
title: Transformations Reference
description: Complete reference of all available transformation nodes
search: transformations nodes all reference
---

# Transformations Reference

FlowFrame includes 25+ transformation nodes for cleaning, reshaping, and transforming data.

## Quick Overview

| Category | Nodes | Purpose |
|----------|-------|---------|
| **Input** | CSV, Excel, Parquet | Load data from files |
| **Cleaning** | 8 nodes | Handle nulls, duplicates, types |
| **Transform** | 5 nodes | Filter, aggregate, join, reshape |
| **Output** | 3 nodes | Save results to files |

## Input Nodes

Load data from files.

- **[CSV Input](/transformations/io/csv-input)** — Read CSV files with custom delimiters
- **[Excel Input](/transformations/io/excel-input)** — Read Excel sheets
- **[Parquet Input](/transformations/io/parquet-input)** — Read Parquet files

## Cleaning Nodes

Clean and prepare data.

### Column Operations

- **[Drop Columns](/transformations/cleaning/drop-columns)** — Remove unwanted columns
- **[Rename Columns](/transformations/cleaning/rename-columns)** — Rename columns
- **[Select Columns](/transformations/transform/select-columns)** — Keep specific columns

### Null Handling

- **[Drop Nulls](/transformations/cleaning/drop-nulls)** — Remove rows with missing values
- **[Fill Nulls](/transformations/cleaning/fill-nulls)** — Replace nulls with values

### Value Operations

- **[Remove Duplicates](/transformations/cleaning/remove-duplicates)** — Drop duplicate rows
- **[Change Data Types](/transformations/cleaning/change-types)** — Convert column types
- **[Filter Rows](/transformations/cleaning/filter-rows)** — Keep rows matching conditions

### Sorting & Structure

- **[Sort](/transformations/cleaning/sort)** — Sort by one or more columns
- **[Calculated Column](/transformations/transform/calculated-column)** — Create new computed columns

## Transform Nodes

Transform data structure.

- **[Group by & Aggregate](/transformations/transform/group-aggregate)** — Group rows and compute statistics
- **[Join](/transformations/transform/join)** — Combine two datasets
- **[Union](/transformations/transform/union)** — Stack multiple datasets

## Output Nodes

Save results.

- **[CSV Output](/transformations/io/csv-output)** — Save as CSV
- **[Excel Output](/transformations/io/excel-output)** — Save as Excel
- **[Parquet Output](/transformations/io/parquet-output)** — Save as Parquet

## Finding the Right Transformation

### I want to...

- **Remove columns** → [Drop Columns](/transformations/cleaning/drop-columns)
- **Fix column names** → [Rename Columns](/transformations/cleaning/rename-columns)
- **Remove missing values** → [Drop Nulls](/transformations/cleaning/drop-nulls)
- **Fill missing values** → [Fill Nulls](/transformations/cleaning/fill-nulls)
- **Remove duplicates** → [Remove Duplicates](/transformations/cleaning/remove-duplicates)
- **Keep only rows where...** → [Filter Rows](/transformations/cleaning/filter-rows)
- **Change column types** → [Change Data Types](/transformations/cleaning/change-types)
- **Create a new column** → [Calculated Column](/transformations/transform/calculated-column)
- **Sum, count, or average** → [Group by & Aggregate](/transformations/transform/group-aggregate)
- **Combine two datasets** → [Join](/transformations/transform/join)
- **Stack two datasets** → [Union](/transformations/transform/union)

## Node Configuration Tips

Every node has:

1. **Title** — Label shown in the flow editor
2. **Configuration panel** — Settings specific to that node
3. **Handles** — Inputs/outputs to connect to other nodes

### Common Settings

- **Column selection** — Click to choose from your data
- **Operators** — =, !=, >, <, contains, etc.
- **Data types** — string, integer, float, date, boolean
- **Aggregations** — sum, mean, count, min, max, etc.

## Generated Python Code

Every flow generates clean Python code you can use outside FlowFrame:

```python
import pandas as pd

# Load
df = pd.read_csv('input.csv')

# Drop columns
df = df.drop(columns=['internal_id'])

# Filter rows
df = df[df['amount'] > 0]

# Group and aggregate
df = df.groupby('region').agg({'amount': 'sum'}).reset_index()

# Rename
df = df.rename(columns={'amount': 'total_sales'})

# Save
df.to_csv('output.csv', index=False)
```

## Limitations & Workarounds

| Limitation | Workaround |
|-----------|-----------|
| **No window functions** | Use group by + join |
| **No regex in filter** | Use Python export + regex |
| **No multi-table union** | Chain multiple union nodes |
| **No if/else logic** | Use multiple filter paths |

## Custom Transformations

Want a transformation that's not built-in? [Open an issue →](https://github.com/rodrigo-arenas/FlowFrame/issues) or [contribute one!](/CONTRIBUTING.md)

## Next Steps

- **[Transformation Examples](/examples/sales-analysis)** — Real workflows
- **[Python Reference](https://pandas.pydata.org/docs/)** — Pandas docs
- **[API Reference](/api/rest-api)** — FlowFrame API

---

Ready to transform some data? [Quick Start →](/guide/quick-start)
