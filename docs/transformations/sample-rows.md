---
title: Sample rows
search: sample rows random subset frac fraction seed reproducible
description: Take a random sample of rows, by count or fraction
---

# Sample rows — `sampleRows`

Take a random sample.

## Use cases

- Build a small, representative subset for quick iteration.
- Down-sample a large dataset before an expensive step.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `n` | int | Conditional | Number of rows (use this **or** `frac`) |
| `frac` | float | Conditional | Fraction in `(0, 1]` |
| `seed` | int | No | Random seed for reproducibility |

Provide exactly one of `n` or `frac`.

## Generated Python code

```python
df_2 = df_1.sample(frac=0.1, random_state=42)
```

## Tips & common mistakes

- **Set a `seed`** so a scheduled flow samples the same rows every run.
- For a *positional* slice (top N) rather than a random one, use
  [Limit rows](./limit-rows.md).

## See also

- [Limit rows](./limit-rows.md) · [Filter rows](./filter-rows.md)
