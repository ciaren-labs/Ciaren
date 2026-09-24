---
title: String transform
search: string transform lower upper strip title capitalize len replace pad regex extract text
description: Apply a string operation to a text column
---

# String transform — `stringTransform`

Apply a string operation to a column.

## Use cases

- Normalize casing (`lower`/`upper`/`title`/`capitalize`) and trim whitespace
  (`strip`).
- Replace a substring, measure length (`len`), zero-pad codes (`pad`), or pull a
  capture group out of a value (`regex_extract`).

## What it does

Applies the chosen operation to every value in the target column in place.
Chain multiple String transform nodes (one per operation) for multi-step cleaning.

<DataTransform
  transform="String transform: lower(email), then strip(name)"
  :before='{
    "columns":["name","email"],
    "rows":[["  Ada L ","ADA@EXAMPLE.COM"],["Grace H","GRACE@EXAMPLE.COM"]]
  }'
  :after='{
    "columns":["name","email"],
    "rows":[["Ada L","ada@example.com"],["Grace H","grace@example.com"]]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Column to transform |
| `operation` | string | Yes | `lower`, `upper`, `strip`, `title`, `capitalize`, `len`, `replace`, `pad`, `regex_extract` |
| `find` | string | Conditional | Required for `replace` |
| `replace_with` | string | No | Replacement for `replace` (default empty) |
| `width` | int | Conditional | Target width, required for `pad` |
| `fill_char` | string | No | Pad character (default space) |
| `side` | string | No | `left` (default) or `right` for `pad` |
| `pattern` | string | Conditional | Regular expression with capturing groups; required for `regex_extract` |
| `group` | int | No | Capture group to keep for `regex_extract` (default `1`) |

## Generated Python code

```python
df_2 = df_1.assign(region=lambda _d: _d['region'].astype('string').str.strip())
```

## Tips & common mistakes

- **`capitalize` vs `title`:** `capitalize` upper-cases only the first character
  of the whole string; `title` upper-cases the first letter of every word.
- **`replace` needs `find`; `pad` needs `width`** — the form blocks saving
  otherwise.
- `len` produces an integer column (character counts), not text.
- **`regex_extract`** keeps one capture group. A non-matching row becomes null.
  Example: pattern `@(.+)$` and group `1` turns `ada@example.com` into
  `example.com`.
- Python `re` and Polars (Rust regex) do not share every feature. Avoid
  look-around and backreferences if the flow must run on both engines.

## See also

- [Replace values](./replace-values.md) · [Split column](./split-column.md)
