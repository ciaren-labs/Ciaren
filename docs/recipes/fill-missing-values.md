---
title: Fill Missing Values
description: Replace nulls/NaNs with a mean, median, mode, constant, or forward/backward fill — per column.
search: recipe fill missing values nulls nan impute mean median mode constant forward fill
---

# Fill Missing Values

Use the **Fill Nulls** node to replace missing values instead of dropping the
rows. It works on both the polars and pandas engines.

**You'll use:** File Input → Fill Nulls → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"survey.csv"},
  {"type":"clean","label":"Fill Nulls","detail":"age → median · region → \"Unknown\""},
  {"type":"output","label":"File Output","detail":"survey_filled.csv"}
]' />

## Steps

1. **File Input** — select your dataset.
2. **Fill Nulls** — choose a strategy per group of columns:
   - **Numeric:** `strategy: "median"` (or `"mean"`) with `columns: ["age"]`.
   - **Categorical:** `strategy: "constant"`, `value: "Unknown"`,
     `columns: ["region"]`.
   - **Ordered/time-series:** `strategy: "forward"` (carry the last value forward)
     or `"backward"`.
   Add a second Fill Nulls node when different columns need different strategies.
3. **File Output** — write the filled result.

## Before / after

<DataTransform
  transform="Fill Nulls (age → median, region → 'Unknown')"
  :before='{
    "columns":["age","region"],
    "rows":[[25,"North"],[null,"South"],[40,null]]
  }'
  :after='{
    "columns":["age","region"],
    "rows":[[25,"North"],[32.5,"South"],[40,"Unknown"]]
  }'
  :highlight='["age","region"]'
/>

## Tips

- **For modeling**, prefer imputing *inside* the model — a train node's
  **Advanced → Preprocessing** applies the same fill at predict time. See
  [Feature Engineering](/examples/feature-engineering).
- **Want to drop instead of fill?** Use [Drop Nulls](/transformations/drop-nulls).

## See also

- [Fill Nulls](/transformations/fill-nulls) · [Drop Nulls](/transformations/drop-nulls)
- [Recipes](/recipes/overview)
