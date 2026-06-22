---
title: Transformations Reference
description: Every transformation node, its config, and the code it generates
search: transformations nodes all reference config pandas polars
---

# Transformations Reference

FlowFrame ships with file input/output nodes plus **23 transformation nodes** for
cleaning, reshaping, and combining data. Each node maps to one clear dataframe
operation and contributes to the exported Python — both the **pandas** and the
**polars** version.

::: info Source of truth
The authoritative list lives in
[`backend/app/engine/registry.py`](https://github.com/rodrigo-arenas/FlowFrame/blob/main/backend/app/engine/registry.py).
Each node's `type` (shown below) is the value stored in the flow graph at
`node.type`; its settings live at `node.data.config`.
:::

## How nodes connect

A flow is a graph of `nodes` and `edges` (React Flow-compatible). Most nodes have
a single input handle (`in`) and output handle (`out`). Two are special:

- **Join** has two inputs: `left` and `right`.
- **Union / Concat** accepts any number of inputs.

## Quick overview

| Category | Nodes |
|----------|-------|
| **Input** | CSV, Excel, Parquet |
| **Columns** | Drop, Rename, Select, Cast types |
| **Nulls** | Drop nulls, Fill nulls |
| **Rows** | Filter, Sort, Limit, Sample, Remove duplicates |
| **Text** | Replace values, String transform |
| **Numeric** | Round, Remove outliers, Bin column |
| **Reshape & combine** | Calculated column, Group by + aggregate, Join, Union/Concat, Pivot, Unpivot, Extract date parts |
| **Output** | CSV, Excel, Parquet |

---

## Input nodes

Load data from a dataset you've uploaded. `type`: `csvInput`, `excelInput`,
`parquetInput`.

| Config key | Type | Required | Description |
|---|---|---|---|
| `dataset_id` | string | Yes | The dataset to read |
| `dataset_version` | int | No | Pin a specific version (defaults to latest) |

```python
df_1 = pd.read_csv("sales.csv")
```

Pinning `dataset_version` makes runs reproducible even after the file is
re-uploaded. See [Projects & Runs](/guide/projects-and-runs#dataset-versioning).

## Output nodes

Write the upstream frame to a file. `type`: `csvOutput`, `excelOutput`,
`parquetOutput`.

| Config key | Type | Required | Description |
|---|---|---|---|
| `path` | string | No | Output filename (defaults to `output.<ext>`) |

```python
df_5.to_csv("output.csv", index=False)
```

---

## Column nodes

### Drop columns — `dropColumns`

Remove one or more columns.

| Config key | Type | Required | Description |
|---|---|---|---|
| `columns` | string[] | Yes | Columns to remove |

```python
df_2 = df_1.drop(columns=['internal_id', 'temp_notes'])
```

### Rename columns — `renameColumns`

Rename columns via an old → new mapping.

| Config key | Type | Required | Description |
|---|---|---|---|
| `mapping` | object | Yes | `{ "old_name": "new_name" }` |

```python
df_2 = df_1.rename(columns={'amt': 'amount'})
```

### Select columns — `selectColumns`

Keep only the listed columns (and reorder them).

| Config key | Type | Required | Description |
|---|---|---|---|
| `columns` | string[] | Yes | Columns to keep, in order |

```python
df_2 = df_1[['region', 'amount']]
```

### Cast types — `castDtypes`

Convert column data types.

| Config key | Type | Required | Description |
|---|---|---|---|
| `casts` | object | Yes | `{ "col": "dtype" }` — dtype is `integer`, `float`, `boolean`, `string`, or `datetime` |
| `format` | string | No | datetime parse format (e.g. `%Y-%m-%d`) |
| `errors` | string | No | `raise` (default) or `coerce` (invalid → null) |

```python
df_2 = df_1.assign(**{'amount': df_1['amount'].astype('float64')})
df_2 = df_2.assign(**{'ordered_at': pd.to_datetime(df_2['ordered_at'])})
```

---

## Null-handling nodes

### Drop nulls — `dropNulls`

Remove rows with missing values.

| Config key | Type | Required | Description |
|---|---|---|---|
| `how` | string | No | `any` (default) drops a row with any null; `all` only if every value is null |
| `subset` | string[] | No | Only consider these columns |

```python
df_2 = df_1.dropna(subset=['amount'])
```

### Fill nulls — `fillNulls`

Replace missing values using a strategy.

| Config key | Type | Required | Description |
|---|---|---|---|
| `strategy` | string | No | `constant` (default), `mean`, `median`, `mode`, `min`, `max`, `zero`, `ffill`, `bfill` |
| `value` | any | Conditional | Required when `strategy` is `constant` |
| `columns` | string[] | No | Limit to these columns (otherwise all) |

```python
# strategy: "constant", value: "Unknown", columns: ["region"]
df_2 = df_1.assign(**{c: df_1[c].fillna('Unknown') for c in ['region']})
```

---

## Row nodes

### Filter rows — `filterRows`

Keep rows matching a condition.

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Column to test |
| `operator` | string | Yes | See operators below |
| `value` | any | Conditional | Required except for `isnull` / `notnull` |
| `value2` | any | Conditional | Upper bound, required for `between` |

**Operators:** `==`, `!=`, `>`, `>=`, `<`, `<=`, `isnull`, `notnull`,
`between` (needs `value2`), `in` (comma-separated or a list), `contains`,
`startswith`, `endswith`.

```python
df_2 = df_1[df_1['amount'] > 0]
```

### Sort rows — `sortRows`

Sort by one or more columns.

| Config key | Type | Required | Description |
|---|---|---|---|
| `columns` | string[] | Yes | Sort keys (in priority order) |
| `ascending` | bool \| bool[] | No | Default `true`; pass a list for per-column direction |
| `na_position` | string | No | `last` (default) or `first` |

```python
df_2 = df_1.sort_values(by=['amount'], ascending=False)
```

### Limit rows — `limitRows`

Keep a slice of rows.

| Config key | Type | Required | Description |
|---|---|---|---|
| `n` | int | Yes | Number of rows to keep (≥ 0) |
| `offset` | int | No | Skip this many rows first (default 0) |

```python
df_2 = df_1.head(100)
```

### Sample rows — `sampleRows`

Take a random sample.

| Config key | Type | Required | Description |
|---|---|---|---|
| `n` | int | Conditional | Number of rows (use this **or** `frac`) |
| `frac` | float | Conditional | Fraction in `(0, 1]` |
| `seed` | int | No | Random seed for reproducibility |

```python
df_2 = df_1.sample(frac=0.1, random_state=42)
```

### Remove duplicates — `removeDuplicates`

Drop duplicate rows.

| Config key | Type | Required | Description |
|---|---|---|---|
| `subset` | string[] | No | Only consider these columns |
| `keep` | string \| false | No | `first` (default), `last`, or `false` (drop all duplicates) |

```python
df_2 = df_1.drop_duplicates(keep='first')
```

---

## Text nodes

### Replace values — `replaceValues`

Substitute values in a column.

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Column to edit |
| `to_replace` | any | Yes | Value (or regex pattern) to find |
| `value` | any | Yes | Replacement value |
| `regex` | bool | No | Treat `to_replace` as a regex (default `false`) |

```python
df_2 = df_1.assign(**{'region': df_1['region'].replace('N', 'North')})
```

### String transform — `stringTransform`

Apply a string operation to a column.

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Column to transform |
| `operation` | string | Yes | `lower`, `upper`, `strip`, `title`, `capitalize`, `len`, `replace`, `pad` |
| `find` | string | Conditional | Required for `replace` |
| `replace_with` | string | No | Replacement for `replace` (default empty) |
| `width` | int | Conditional | Target width, required for `pad` |
| `fill_char` | string | No | Pad character (default space) |
| `side` | string | No | `left` (default) or `right` for `pad` |

```python
df_2 = df_1.assign(**{'region': df_1['region'].astype('string').str.strip()})
```

---

## Numeric nodes

### Round numbers — `roundNumbers`

Round numeric columns to a number of decimals.

| Config key | Type | Required | Description |
|---|---|---|---|
| `columns` | string[] | Yes | Numeric columns to round |
| `decimals` | int | No | Decimal places (default 0) |

```python
df_2 = df_1.assign(**{c: df_1[c].round(2) for c in ['amount']})
```

### Remove outliers — `removeOutliers`

Drop or clip outliers in numeric columns.

| Config key | Type | Required | Description |
|---|---|---|---|
| `columns` | string[] | Yes | Numeric columns to scan |
| `method` | string | No | `iqr` (default), `zscore`, or `percentile` |
| `action` | string | No | `drop` (default) or `clip` to the bounds |
| `factor` | float | No | IQR multiplier (default `1.5`) |
| `threshold` | float | No | z-score threshold (default `3.0`) |
| `lower` / `upper` | float | No | Percentile bounds (default `1.0` / `99.0`) |

```python
# method: iqr, action: drop
df_2 = df_1
for _col in ['amount']:
    s = df_2[_col]
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df_2 = df_2[s.between(lo, hi) | s.isna()]
```

### Bin column — `binColumn`

Bucket a numeric column into labeled bins (a new column).

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Numeric column to bin |
| `new_column` | string | Yes | Name of the new bin column |
| `bins` | int | No | Number of bins (≥ 2, default 4) |
| `method` | string | No | `equalwidth` (default) or `quantile` |
| `labels` | string[] | No | Custom labels (one per bin) |

```python
df_2 = df_1.assign(**{'amount_band': pd.cut(df_1['amount'], bins=4, labels=None).astype('string')})
```

---

## Reshape & combine nodes

### Calculated column — `calculatedColumn`

Add a column computed from an expression over existing columns.

| Config key | Type | Required | Description |
|---|---|---|---|
| `column_name` | string | Yes | New column name |
| `expression` | string | Yes | Arithmetic expression, e.g. `price * quantity` |

```python
df_2 = df_1.assign(**{'total': df_1.eval('price * quantity')})
```

### Group by + aggregate — `groupByAggregate`

Group rows and compute aggregates.

| Config key | Type | Required | Description |
|---|---|---|---|
| `group_by` | string[] | Yes | Grouping columns |
| `aggregations` | object | Yes | `{ "col": "func" }` |

**Aggregation functions:** `sum`, `mean`, `count`, `min`, `max`, `median`,
`nunique`.

```python
df_2 = df_1.groupby(['region']).agg({'amount': 'sum'}).reset_index()
```

### Join — `join`

Combine two inputs (`left`, `right`) on a key.

| Config key | Type | Required | Description |
|---|---|---|---|
| `on` | string \| string[] | Conditional | Key(s) present in both frames |
| `left_on` / `right_on` | string \| string[] | Conditional | Use when key names differ (supply both) |
| `how` | string | No | `inner` (default), `left`, `right`, `outer` |
| `suffixes` | [string, string] | No | Suffixes for overlapping columns (default `_x`, `_y`) |

```python
df_3 = pd.merge(df_1, df_2, on=['customer_id'], how='left', suffixes=('_x', '_y'))
```

### Union / Concat — `concatRows`

Stack multiple inputs row-wise (no config). Connect two or more upstream nodes.

```python
df_3 = pd.concat([df_1, df_2], ignore_index=True)
```

### Pivot — `pivot`

Reshape long → wide.

| Config key | Type | Required | Description |
|---|---|---|---|
| `index` | string \| string[] | Yes | Row key(s) |
| `columns` | string | Yes | Column whose values become new columns |
| `values` | string | Yes | Column to aggregate into the cells |
| `aggfunc` | string | No | Aggregation (default `sum`) |

```python
df_2 = df_1.pivot_table(index=['region'], columns='month', values='amount', aggfunc='sum').reset_index()
```

### Unpivot — `unpivot`

Reshape wide → long (pandas `melt`).

| Config key | Type | Required | Description |
|---|---|---|---|
| `id_vars` | string[] | Yes | Columns to keep as identifiers |
| `value_vars` | string[] | No | Columns to unpivot (defaults to the rest) |
| `var_name` | string | No | Name for the variable column (default `variable`) |
| `value_name` | string | No | Name for the value column (default `value`) |

```python
df_2 = df_1.melt(id_vars=['region'], value_vars=None, var_name='variable', value_name='value')
```

### Extract date parts — `extractDateParts`

Add columns for parts of a date/datetime column.

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Date/datetime column |
| `parts` | string[] | Yes | Any of `year`, `month`, `day`, `weekday`, `hour` |

```python
_dt = pd.to_datetime(df_1['ordered_at'])
df_2 = df_1.assign(**{'ordered_at_year': _dt.dt.year, 'ordered_at_month': _dt.dt.month})
```

---

## Choosing the right node

| I want to... | Use |
|--------------|-----|
| Remove columns | Drop columns |
| Fix column names | Rename columns |
| Keep only some columns | Select columns |
| Change a column's type | Cast types |
| Remove rows with missing values | Drop nulls |
| Fill missing values | Fill nulls |
| Remove duplicate rows | Remove duplicates |
| Keep rows matching a condition | Filter rows |
| Create a new computed column | Calculated column |
| Sum / count / average by group | Group by + aggregate |
| Combine two datasets on a key | Join |
| Stack datasets row-wise | Union / Concat |
| Reshape long ↔ wide | Pivot / Unpivot |
| Bucket a number into bands | Bin column |
| Split a date into year/month/… | Extract date parts |

## Current limitations

| Limitation | Workaround |
|-----------|-----------|
| No window functions | Use group by + join |
| Join takes two inputs at a time | Chain multiple join nodes |
| No if/else branching | Use multiple filter paths |
| `calculatedColumn` evaluates arithmetic expressions | For complex logic, export and edit the Python |

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
