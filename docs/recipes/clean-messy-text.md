---
title: Clean Messy Text in a CSV
description: Trim whitespace and normalize email casing in Ciaren with two String Transform nodes, then export the same cleaning steps as pandas or Polars.
search: recipe clean messy text csv trim whitespace lowercase email pandas polars
---

# Clean Messy Text in a CSV

An email such as `"  ADA@EXAMPLE.COM "` will not match `ada@example.com` in a
join. Trim the spaces, then make the casing consistent before matching records.

**You'll use:** [File Input](/transformations/file-input) →
[String Transform](/transformations/string-transform) → String Transform →
[File Output](/transformations/file-output).

## Steps

1. Upload your CSV on **Datasets**, then select it in **File Input**.
2. Add **String Transform** with `column: email` and `operation: strip`.
3. Connect a second **String Transform** with `column: email` and
   `operation: lower`.
4. Preview the second node. The column should contain trimmed, lowercase text.
5. Connect **File Output**, choose CSV, and run the flow to download the result.

## Before / after

| Original email | Cleaned email |
| --- | --- |
| `"  ADA@EXAMPLE.COM "` | `ada@example.com` |
| `Grace@Example.com` | `grace@example.com` |
| null | null |

## Exported Python

These runnable examples use the same input and node configuration. The
transformation lines come from Ciaren's code generators; replace the example
dataframe with your file input when running them on your data.

### pandas

```python
import pandas as pd

df_1 = pd.DataFrame({'email': ['  ADA@EXAMPLE.COM ', 'Grace@Example.com', None]})
df_2 = df_1.assign(email=lambda _d: _d['email'].astype('string').str.strip())
df_3 = df_2.assign(email=lambda _d: _d['email'].astype('string').str.lower())
print(df_3)
```

### Polars

```python
import polars as pl

df_1 = pl.DataFrame({'email': ['  ADA@EXAMPLE.COM ', 'Grace@Example.com', None]})
df_2 = df_1.with_columns(pl.col('email').cast(pl.Utf8).str.strip_chars())
df_3 = df_2.with_columns(pl.col('email').cast(pl.Utf8).str.to_lowercase())
print(df_3)
```

## Tips

- Clean both inputs before a [Join](/transformations/join), so the keys use
  the same format. Keep a copy of the original field if you need to audit it.
- Empty text is still text; trimming does not turn an empty string into null.
- Use `lower` only where casing is irrelevant. Passwords and case-sensitive
  identifiers should keep their original values.
- Cleaning an email does not validate its address or guarantee delivery.

## See also

- [String Transform](/transformations/string-transform)
- [Remove Duplicate Rows](/recipes/remove-duplicate-rows)
- [Recipes](/recipes/overview)
