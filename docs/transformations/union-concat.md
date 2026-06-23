---
title: Union / Concat
search: union concat stack append rows combine multiple inputs variadic
description: Stack multiple inputs row-wise into one frame
---

# Union / Concat — `concatRows`

Stack multiple inputs row-wise (no config). This is the variadic node — connect
**two or more** upstream nodes to its input handle and they're concatenated in
order.

## Use cases

- Combine monthly files into one dataset.
- Append a new batch to an existing one before further cleaning.

## Configuration

This node has **no configuration** — it stacks whatever inputs are connected.

## Generated Python code

```python
df_3 = pd.concat([df_1, df_2], ignore_index=True)
```

## Tips & common mistakes

- **Align columns first.** Inputs with different column names produce sparse rows
  (missing columns become null) — use [Rename columns](./rename-columns.md) /
  [Select columns](./select-columns.md) to match schemas.
- Concat stacks **rows**; to combine *columns* on a key use [Join](./join.md).
- Use [Remove duplicates](./remove-duplicates.md) afterward if sources overlap.

## See also

- [Join](./join.md) · [Remove duplicates](./remove-duplicates.md)
