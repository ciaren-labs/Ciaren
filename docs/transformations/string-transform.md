---
title: String transform
search: string transform lower upper strip title capitalize len replace pad text
description: Apply a string operation to a text column
---

# String transform — `stringTransform`

Apply a string operation to a column.

## Use cases

- Normalize casing (`lower`/`upper`/`title`/`capitalize`) and trim whitespace
  (`strip`).
- Replace a substring, measure length (`len`), or zero-pad codes (`pad`).

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `column` | string | Yes | Column to transform |
| `operation` | string | Yes | `lower`, `upper`, `strip`, `title`, `capitalize`, `len`, `replace`, `pad` |
| `find` | string | Conditional | Required for `replace` |
| `replace_with` | string | No | Replacement for `replace` (default empty) |
| `width` | int | Conditional | Target width, required for `pad` |
| `fill_char` | string | No | Pad character (default space) |
| `side` | string | No | `left` (default) or `right` for `pad` |

## Generated Python code

```python
df_2 = df_1.assign(**{'region': df_1['region'].astype('string').str.strip()})
```

## Tips & common mistakes

- **`capitalize` vs `title`:** `capitalize` upper-cases only the first character
  of the whole string; `title` upper-cases the first letter of every word.
- **`replace` needs `find`; `pad` needs `width`** — the form blocks saving
  otherwise.
- `len` produces an integer column (character counts), not text.

## See also

- [Replace values](./replace-values.md) · [Split column](./split-column.md)
