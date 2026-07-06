---
title: Pivot a Table
description: Turn long rows into a wide summary — spread one column's values into new columns, aggregating the values.
search: recipe pivot table long to wide reshape crosstab summary
---

# Pivot a Table

The **Pivot** node spreads the unique values of one column into new columns,
filling each cell by aggregating a values column. It's the classic "long → wide"
reshape.

**You'll use:** File Input → Pivot → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"sales_long.csv"},
  {"type":"transform","label":"Pivot","detail":"index region · columns month · values amount"},
  {"type":"output","label":"File Output","detail":"sales_wide.csv"}
]' />

## Steps

1. **File Input** — select your long-format dataset.
2. **Pivot** — set:
   - `index: ["region"]` — the row key(s)
   - `columns: "month"` — the column whose values become new columns
   - `values: "amount"` — the column to aggregate into the cells
   - `aggfunc: "sum"` — how to combine collisions (default `sum`)
3. **File Output** — write the wide table.

## Before / after

<DataTransform
  transform="Pivot (index=region, columns=month, values=amount, aggfunc=sum)"
  :before='{
    "columns":["region","month","amount"],
    "rows":[["North","Jan",100],["North","Feb",120],["South","Jan",80]]
  }'
  :after='{
    "columns":["region","Jan","Feb"],
    "rows":[["North",100,120],["South",80,null]]
  }'
/>

South has no Feb row in the source data, so its `Feb` cell comes out **null**
(`pivot_table` doesn't fill missing index/column combinations by default) —
add a [Fill Nulls](/transformations/fill-nulls) node after Pivot if you want
those cells to read `0` instead.

## Tips

- New column names come from the **values** found in `columns` at run time.
- **Need the inverse** (wide → long)? Use [Unpivot](/transformations/unpivot).

## See also

- [Pivot](/transformations/pivot) · [Unpivot](/transformations/unpivot) · [Group by + Aggregate](/transformations/group-by-aggregate)
- [Recipes](/recipes/overview)
