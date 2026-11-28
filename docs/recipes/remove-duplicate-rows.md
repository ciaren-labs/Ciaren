---
title: Remove Duplicate Rows
description: "Remove duplicate rows in Ciaren with the Remove Duplicates node: drop exact copies or keep one row per key column, and sort first to choose which row survives."
search: recipe remove duplicates deduplicate distinct unique rows keep first last subset sort newest
---

# Remove Duplicate Rows

A contacts export lists the same email more than once, and you want one row per
contact, keeping the most recent one. **Remove Duplicates** drops repeated rows;
a **Sort Rows** step before it decides which of the repeats survives.

**You'll use:** [File Input](/transformations/file-input) →
[Sort Rows](/transformations/sort-rows) →
[Remove Duplicates](/transformations/remove-duplicates) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"contacts.csv"},
  {"type":"clean","label":"Sort Rows","detail":"updated_at · descending"},
  {"type":"clean","label":"Remove Duplicates","detail":"subset: email · keep first"},
  {"type":"output","label":"File Output","detail":"contacts_unique"}
]' />

## Sample data

Save this as `contacts.csv`. Ada appears twice with different names, and the
last row is an exact copy of Lin.

```csv
name,email,updated_at
Ada,ada@x.io,2024-01-03
Lin,lin@x.io,2024-02-11
Ada L.,ada@x.io,2024-03-20
Lin,lin@x.io,2024-02-11
```

## Steps

1. On **Datasets**, upload `contacts.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `contacts.csv`.
3. Add **Sort Rows**. Set **Sort by columns** to `updated_at` and **Order** to
   Descending, so the newest row of each contact comes first.
4. Add **Remove Duplicates**. Set **Subset (optional)** to `email` and **Keep**
   to first occurrence.
5. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `contacts_unique`. Connect the nodes in order and click **Run**.

:::tip Prefer to describe it?
With a provider key set up, upload the sample data, open a blank flow in the same project and ask the [Flow assistant](/guide/flow-assistant), for example: "keep one row per email, the one with the latest updated_at." Review the proposed nodes and settings, then choose **Apply and save**. The manual steps above build the same flow. The assistant never runs a flow, so click **Run** yourself.
:::

## Result

| name | email | updated_at |
| --- | --- | --- |
| Ada L. | `ada@x.io` | 2024-03-20 |
| Lin | `lin@x.io` | 2024-02-11 |

Both engines and both exports return these two rows in this order.

![With keep first, the row that comes first in the current order survives: as loaded, the older Ada stays; after sorting newest first, the newest Ada stays](/illustrations/recipes/remove-duplicates-keep.svg)

## Choose the subset

The **Subset (optional)** field decides which columns must match for two rows to
count as duplicates.

![With an empty subset only the exact copy of Lin is dropped and both Adas stay; with subset email, one row per email remains](/illustrations/recipes/remove-duplicates-subset.svg)

- Leave it empty to drop only rows that match in every column. On the sample
  this removes the second Lin and keeps 3 rows, because `Ada` and `Ada L.`
  differ in `name`.
- Set it to `email` to keep one row per email, whatever the other columns say.

## Check the result

Save the flow, click **Preview**, select the **Remove Duplicates** node and
click **Run preview**. You should see 2 rows, and the `ada@x.io` row should read
`Ada L.` with `2024-03-20`. If it reads `Ada`, the Sort Rows node is missing,
set to Ascending, or connected after Remove Duplicates.

## Pitfalls

- **Without a sort, "first" means file order.** Remove Duplicates does not look
  at dates. The same flow without Sort Rows keeps `Ada` from 2024-01-03.
- **Keys must match exactly.** `Ada@X.io` and `ada@x.io` with a trailing space
  are both different from `ada@x.io`. Clean the key first, see
  [Clean Messy Text](/recipes/clean-messy-text).
- **The output keeps the sorted order.** Add another Sort Rows after Remove
  Duplicates if you need the rows in a different order.
- **To report duplicates instead of dropping them**, use
  [Assert Unique](/transformations/assert-unique), which fails or warns when a
  key repeats.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `contacts.csv` from the script's folder and
writes `contacts_unique.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_contacts = pd.read_csv('contacts.csv')

df_contacts = (
    df_contacts.sort_values('updated_at', ascending=False)
    .drop_duplicates(subset='email')
)

df_contacts.to_csv('contacts_unique.csv', index=False)
```

```python [Polars]
import polars as pl

df_contacts = pl.read_csv('contacts.csv')

df_contacts = (
    df_contacts.sort('updated_at', descending=True, nulls_last=True)
    .unique(subset='email', keep='first', maintain_order=True)
)

df_contacts.write_csv('contacts_unique.csv')
```

:::

## See also

- [Remove Duplicates](/transformations/remove-duplicates)
- [Sort Rows](/transformations/sort-rows)
- [Recipes](/recipes/overview)
