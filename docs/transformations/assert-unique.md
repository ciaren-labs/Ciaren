---
title: Assert unique
description: Fail or warn when a column combination contains duplicate rows
search: assert unique data quality duplicate rows primary key contract check
---

# Assert unique — `assertUnique`

Verify that a set of columns contains no duplicate rows.

The node is **pass-through**: the dataframe leaves unchanged regardless of the
outcome. The violation is recorded in the run's per-node result and either fails
the run (`error` mode) or logs a warning and continues (`warn` mode).

## Use cases

- Verify that a join key or primary key is truly unique before a merge.
- Catch accidental fan-out (duplicate rows) introduced by an upstream join.
- Assert that a deduplication step actually worked.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | list of strings | Yes | Column combination that must be unique |
| `mode` | `"error"` \| `"warn"` | No | `"error"` (default) stops the run; `"warn"` continues and logs |

## Behavior

| Outcome | What happens |
| --- | --- |
| No duplicates across the specified columns | Run continues; `assertion_passed: true` |
| Duplicates found, `mode: "error"` | Run fails; error names the columns and duplicate count |
| Duplicates found, `mode: "warn"` | Run continues; warning recorded with duplicate count |

The per-node result in the run detail always includes `assertion_passed`,
`assertion_violation_count` (number of duplicate rows), and a sample of up to 5
violating rows.

## Generated Python code

```python
# assertUnique: ['order_id'] — mode: error
_dupes = df_1[df_1.duplicated(subset=['order_id'], keep=False)]
if not _dupes.empty:
    _msg = f"assertUnique: {len(_dupes)} duplicate row(s) across columns ['order_id']"
    raise AssertionError(_msg)
df_2 = df_1
```

In `warn` mode the `raise` is replaced by `warnings.warn(...)` and execution
continues.

## Tips & common mistakes

- **Column order doesn't matter.** `["a", "b"]` and `["b", "a"]` check the same
  uniqueness constraint.
- **All rows with the duplicate key are counted.** If `order_id = 7` appears
  three times, the violation count is 3.
- Use [Remove duplicates](./remove-duplicates.md) if you want to *drop* duplicate
  rows instead of asserting they don't exist.

## See also

- [Assert not null](./assert-not-null.md) · [Assert value range](./assert-value-range.md)
- [Remove duplicates](./remove-duplicates.md) · [Join](./join.md)
