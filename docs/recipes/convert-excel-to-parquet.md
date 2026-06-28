---
title: Convert Excel to Parquet
description: Read an Excel file and write it back out as a compact, columnar Parquet file — visually, in two nodes.
search: recipe convert excel xlsx to parquet columnar file format
---

# Convert Excel to Parquet

Parquet is a compact, columnar format that's much faster to read than Excel and
keeps column types. Converting takes two nodes.

**You'll use:** File Input → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"data.xlsx"},
  {"type":"output","label":"File Output","detail":"data.parquet"}
]' />

## Steps

1. Upload your `.xlsx` file on the **Datasets** page.
2. **File Input** — select the dataset (FlowFrame reads Excel via `openpyxl`).
3. **File Output** — set `format: parquet` and a name like `data`.
4. **Run**. Download the `.parquet` from the run output.

## Exported Python

```python
import pandas as pd

df_1 = pd.read_excel("data.xlsx")
df_1.to_parquet("data.parquet", index=False)
```

## Tips

- **Pick a specific sheet** in the File Input options if the workbook has several.
- **Going the other way?** Swap the formats — Parquet in, Excel or CSV out.
- **Large files?** Parquet output plus the polars engine (and lazy export) is much
  faster than CSV. See [Engines](/guide/engines).

## See also

- [File input](/transformations/file-input) · [File output](/transformations/file-output)
- [Recipes](/recipes/overview)
