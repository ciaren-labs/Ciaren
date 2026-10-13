---
title: Combine Columns with Fallback Values
description: Choose the first available value from two columns in Ciaren with Coalesce Columns, preserve missing values, and export runnable pandas or Polars.
search: recipe coalesce fallback first non null combine columns pandas polars
---

# Combine Columns with Fallback Values

Choose a primary email when it exists, otherwise use a backup email. Coalesce
checks columns in order and copies the first non-null value into a new column.

**You'll use:** [File Input](/transformations/file-input) →
[Coalesce Columns](/transformations/coalesce-columns) →
[File Output](/transformations/file-output).

## Steps

1. Upload your CSV on **Datasets** and select it in **File Input**.
2. Add **Coalesce Columns** with `columns: ["primary_email", "backup_email"]`
   and `new_column: email`.
3. Leave `keep_original: true` to compare the source and result columns.
4. Preview the node. A row with two missing values should still have null
   in `email`.
5. Connect **File Output**, choose CSV, and run the flow.

## Before / after

| primary_email | backup_email | email |
| --- | --- | --- |
| `ada@example.com` | `ada.backup@example.com` | `ada@example.com` |
| null | `grace@example.com` | `grace@example.com` |
| null | null | null |
| empty string | `lin@example.com` | empty string |

## Exported Python

These runnable examples use the same configuration. The transformation lines
come from Ciaren's code generators.

### pandas

```python
import pandas as pd

df_1 = pd.DataFrame({
    'primary_email': ['ada@example.com', None, None, ''],
    'backup_email': ['ada.backup@example.com', 'grace@example.com', None, 'lin@example.com'],
})
df_2 = df_1.assign(email=lambda _d: _d['primary_email'].where(pd.notna, _d['backup_email']))
print(df_2)
```

### Polars

```python
import polars as pl

df_1 = pl.DataFrame({
    'primary_email': ['ada@example.com', None, None, ''],
    'backup_email': ['ada.backup@example.com', 'grace@example.com', None, 'lin@example.com'],
})
df_2 = df_1.with_columns(pl.coalesce([pl.col('primary_email'), pl.col('backup_email')]).alias('email'))
print(df_2)
```

## Tips

- Put the most trusted column first. Coalesce does not compare or merge two
  non-null values.
- An empty string is not null, so it takes priority over the backup. If empty
  text means missing in your source, normalize it to null first.
- Set `keep_original: false` only after checking the output, to drop the
  source columns.
- To join pieces of text together, use
  [Combine Columns](/transformations/combine-columns).

## See also

- [Coalesce Columns](/transformations/coalesce-columns)
- [Fill Missing Values](/recipes/fill-missing-values)
- [Recipes](/recipes/overview)
