---
title: Sample rows
search: sample rows random subset frac fraction seed reproducible
description: Take a reproducible random sample of rows, by count or fraction
---

# Sample rows — `sampleRows`

Take a reproducible random sample. A `seed` is **required** so the same rows are
selected on every run — important for pipelines you preview, schedule, or export.

<DataTransform
  :before='[
    ["id","name","score"],
    [1,"Alice",88],
    [2,"Bob",72],
    [3,"Carol",95],
    [4,"Dave",61],
    [5,"Eve",79],
    [6,"Frank",84],
    [7,"Grace",91]
  ]'
  config="frac=0.4  seed=42"
  :after='[
    ["id","name","score"],
    [3,"Carol",95],
    [6,"Frank",84],
    [1,"Alice",88]
  ]'
/>

## Use cases

- Build a small, representative subset for quick iteration.
- Down-sample a large dataset before an expensive step.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `n` | int | Conditional | Number of rows (use this **or** `frac`) |
| `frac` | float | Conditional | Fraction in `(0, 1]` |
| `seed` | int | **Yes** | Random seed — required so the sample is reproducible |

Provide exactly one of `n` or `frac`. The `seed` must be an integer; a sample
without one is rejected so runs stay reproducible.

## Generated Python code

```python
df_2 = df_1.sample(frac=0.1, random_state=42)
```

## Tips & common mistakes

- The `seed` is required: it's what makes a scheduled or exported flow sample the
  same rows every run. Change it to draw a different (but still repeatable) sample.
- For a *positional* slice (top N) rather than a random one, use
  [Limit rows](./limit-rows.md).

## See also

- [Limit rows](./limit-rows.md) · [Filter rows](./filter-rows.md)
