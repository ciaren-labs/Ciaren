---
title: Map values
search: map values lookup recode case when default mapping
description: Recode column values via a lookup, with an optional default
---

# Map values — `mapValues`

Map column values to new values via a lookup (CASE-WHEN-style), with an optional
default for unmapped values.

## Use cases

- Recode grades to outcomes (`A`/`B` → `Pass`).
- Translate codes to labels, sending anything unmapped to a default.

## What it does

Looks up each value in the mapping table and replaces it. With `use_default: true`,
anything not in the mapping gets the `default` value.

<DataTransform
  transform="Map values (mapping: A→Pass, B→Pass; default=Fail; new_column=result)"
  :before='{
    "columns":["student","grade"],
    "rows":[["Alice","A"],["Bob","C"],["Carol","B"],["Dave","F"]]
  }'
  :after='{
    "columns":["student","grade","result"],
    "rows":[["Alice","A","Pass"],["Bob","C","Fail"],["Carol","B","Pass"],["Dave","F","Fail"]]
  }'
  :highlight='["result"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Column whose values are mapped |
| `mapping` | object | Yes | `{ "value": "becomes" }` |
| `new_column` | string | No | Write to a new column (empty = overwrite `column`) |
| `default` | any | No | Value for anything not in the mapping |
| `use_default` | bool | No | When `true`, unmapped values become `default`; otherwise they're kept as-is |

## Generated Python code

```python
# mapping: {"A": "Pass", "B": "Pass"}, default "Fail"
df_2 = df_1.assign(**{'result': df_1['grade'].map({'A': 'Pass', 'B': 'Pass'})
    .where(df_1['grade'].isin(['A', 'B']), 'Fail')})
```

## Tips & common mistakes

- **Without `use_default`, unmapped values pass through unchanged.** Turn it on to
  funnel everything else into `default`.
- Set `new_column` to keep the original column alongside the recoded one.
- For one-to-one substitutions (with optional regex) prefer
  [Replace values](./replace-values.md); for if/else logic over several columns,
  use [Conditional column](./conditional-column.md).

## See also

- [Replace values](./replace-values.md) · [Conditional column](./conditional-column.md)
