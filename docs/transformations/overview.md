---
title: Transformations Reference
description: Reference of the available transformation nodes
search: transformations nodes all reference
---

# Transformations Reference

FlowFrame ships with input/output nodes plus 16 transformation nodes for
cleaning, reshaping, and combining data. Each node maps to a clear pandas
operation and contributes to the exported Python code.

## Quick Overview

| Category | Nodes | Purpose |
|----------|-------|---------|
| **Input** | CSV, Excel, Parquet | Load data from files |
| **Cleaning** | 12 nodes | Columns, nulls, types, rows |
| **Transform** | 4 nodes | Calculate, aggregate, join, union |
| **Output** | CSV, Excel, Parquet | Save results to files |

## Input Nodes

Load data from files.

- **CSV Input** — Read CSV files with custom delimiters
- **Excel Input** — Read Excel sheets
- **Parquet Input** — Read Parquet files

## Cleaning Nodes

Clean and prepare data.

### Column Operations

- **Drop Columns** — Remove unwanted columns
- **Rename Columns** — Rename columns
- **Select Columns** — Keep only specific columns

### Null Handling

- **Drop Nulls** — Remove rows with missing values
- **Fill Nulls** — Replace nulls with values

### Value & Row Operations

- **Remove Duplicates** — Drop duplicate rows
- **Change Data Types** — Convert column types
- **Filter Rows** — Keep rows matching conditions
- **Replace Values** — Substitute values in a column
- **String Transform** — Apply string operations (trim, case, etc.)
- **Sort** — Sort by one or more columns
- **Limit Rows** — Keep the first N rows

## Transform Nodes

Reshape and combine data.

- **Calculated Column** — Create a new computed column
- **Group by & Aggregate** — Group rows and compute statistics
- **Join** — Combine two datasets on a key
- **Union / Concat** — Stack datasets row-wise

## Output Nodes

Save results.

- **CSV Output** — Save as CSV
- **Excel Output** — Save as Excel
- **Parquet Output** — Save as Parquet

## Finding the Right Transformation

| I want to... | Use |
|--------------|-----|
| Remove columns | Drop Columns |
| Fix column names | Rename Columns |
| Remove missing values | Drop Nulls |
| Fill missing values | Fill Nulls |
| Remove duplicates | Remove Duplicates |
| Keep only matching rows | Filter Rows |
| Change column types | Change Data Types |
| Create a new column | Calculated Column |
| Sum, count, or average | Group by & Aggregate |
| Combine two datasets | Join |
| Stack two datasets | Union / Concat |

## Node Configuration

Every node has a title, a configuration panel with settings specific to that
node, and input/output handles to connect to other nodes. Common settings
include column selection, comparison operators, target data types, and
aggregation functions.

## Generated Python Code

Every flow generates clean Python code you can run outside FlowFrame:

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

## Current Limitations

| Limitation | Workaround |
|-----------|-----------|
| No window functions | Use group by + join |
| No regex in filter | Edit the exported Python and add regex |
| Union takes two inputs at a time | Chain multiple union nodes |
| No if/else branching | Use multiple filter paths |

## Custom Transformations

Need a transformation that isn't built in?
[Open an issue](https://github.com/rodrigo-arenas/FlowFrame/issues) or
[contribute one](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md).

## Next Steps

- [Examples](/examples/sales-analysis) — sample workflows
- [pandas documentation](https://pandas.pydata.org/docs/) — the library underneath
