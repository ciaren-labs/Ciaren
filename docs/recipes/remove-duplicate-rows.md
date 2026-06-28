---
title: Remove Duplicate Rows
description: Drop exact duplicate rows, or de-duplicate by a key column keeping the first or last occurrence.
search: recipe remove duplicates deduplicate distinct unique rows keep first last
---

# Remove Duplicate Rows

Use the **Remove Duplicates** node to drop repeated rows — either fully identical
rows or duplicates of a key column.

**You'll use:** File Input → Remove Duplicates → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"contacts.csv"},
  {"type":"clean","label":"Remove Duplicates","detail":"subset: email · keep first"},
  {"type":"output","label":"File Output","detail":"contacts_unique.csv"}
]' />

## Steps

1. **File Input** — select your dataset.
2. **Remove Duplicates** — configure how to match:
   - **All columns** (default): drops rows that are identical across every column.
   - **By key:** set `subset: ["email"]` to treat rows with the same `email` as
     duplicates, and `keep: "first"` (or `"last"`) to choose which one survives.
3. **File Output** — write the de-duplicated result.

## Before / after

<DataTransform
  transform="Remove Duplicates (subset: email, keep: first)"
  :before='{
    "columns":["name","email"],
    "rows":[["Ada","ada@x.io"],["Ada","ada@x.io"],["Lin","lin@x.io"]]
  }'
  :after='{
    "columns":["name","email"],
    "rows":[["Ada","ada@x.io"],["Lin","lin@x.io"]]
  }'
/>

## Tips

- **Order matters for `keep`.** Add a [Sort Rows](/transformations/sort-rows) node
  first so "first" or "last" means what you expect (e.g. keep the most recent).
- **Just want to *find* duplicates?** Use an [Assert Unique](/transformations/assert-unique)
  data-quality node to fail or warn when duplicates appear, instead of dropping them.

## See also

- [Remove Duplicates](/transformations/remove-duplicates)
- [Recipes](/recipes/overview)
