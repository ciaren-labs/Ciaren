---
title: Combine Columns with Fallback Values
description: Pick the first available value from several columns in Ciaren with Coalesce Columns, such as a primary email with a backup, and see why a blank value still wins. Includes the pandas and Polars export.
search: recipe coalesce fallback first non null combine columns primary backup email pandas polars
---

# Combine Columns with Fallback Values

A contact list has a `primary_email` and a `backup_email`, and you want one
`email` column: the primary address when there is one, otherwise the backup.
**Coalesce Columns** checks the columns in the order you list them and copies
the first value that is not null into a new column.

**You'll use:** [File Input](/transformations/file-input) →
[Coalesce Columns](/transformations/coalesce-columns) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"contacts.csv"},
  {"type":"transform","label":"Coalesce Columns","detail":"primary_email, backup_email → email"},
  {"type":"output","label":"File Output","detail":"contacts_email"}
]' />

## Sample data

Save this as `contacts.csv`. Customer 2 has no primary email, customer 3 has
neither, and customer 4 has a single space as the primary email.

```csv
customer_id,primary_email,backup_email
1,ada@example.com,ada.backup@example.com
2,,grace@example.com
3,,
4," ",lin@example.com
```

## Steps

1. On **Datasets**, upload `contacts.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `contacts.csv`.
3. Add **Coalesce Columns**. In **Columns (in priority order)** pick
   `primary_email` first, then `backup_email`. Set **New column** to `email`.
4. Leave **Keep the original columns** checked for now, so you can compare
   each source column with the result.
5. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `contacts_email`. Connect the nodes in order and click **Run**.

:::tip Prefer to describe it?
With a provider key set up, upload the sample data, open a blank flow in the same project and ask the [Flow assistant](/guide/flow-assistant), for example: "create an email column from primary_email, falling back to backup_email." Review the proposed nodes and settings, then choose **Apply and save**. The manual steps above build the same flow. The assistant never runs a flow, so click **Run** yourself.
:::

## Result

| customer_id | primary_email | backup_email | email |
| --- | --- | --- | --- |
| 1 | `ada@example.com` | `ada.backup@example.com` | `ada@example.com` |
| 2 | null | `grace@example.com` | `grace@example.com` |
| 3 | null | null | null |
| 4 | `" "` | `lin@example.com` | `" "` |

![Coalesce reads primary_email, then backup_email, and copies the first value that is not null; the single space in row 4 is not null, so it wins](/illustrations/recipes/coalesce-first-non-null.svg)

## Check the result

Save the flow, click **Preview**, select the Coalesce Columns node and click
**Run preview**. Customer 2 should show `grace@example.com` in `email` and
customer 3 should show null. Customer 4 shows an `email` that looks empty: that
is the space, and it is the row to fix.

## Pitfalls

- **Blank text is not null.** A space, or an empty text produced by an earlier
  Strip spaces step, counts as a value and wins over the backup. If a blank
  should mean missing, fix it in the source file: an empty CSV cell is read as
  null.
- **Order is priority.** Put the most trusted column first. Coalesce never
  compares two values that are both set; customer 1 gets the primary address
  even though a backup exists.
- **Both missing stays missing.** Add [Fill Nulls](/transformations/fill-nulls)
  after Coalesce if `email` needs a placeholder.
- **Uncheck Keep the original columns** only after checking the result. The
  output then has `customer_id` and `email` only.
- **To join text from several columns**, such as first and last name, use
  [Combine Columns](/transformations/combine-columns) instead.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `contacts.csv` from the script's folder and
writes `contacts_email.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_contacts = pd.read_csv('contacts.csv')
df_contacts = df_contacts.assign(email=lambda _d: _d['primary_email'].where(pd.notna, _d['backup_email']))
df_contacts.to_csv('contacts_email.csv', index=False)
```

```python [Polars]
import polars as pl

df_contacts = pl.read_csv('contacts.csv')
df_contacts = df_contacts.with_columns(pl.coalesce([pl.col('primary_email'), pl.col('backup_email')]).alias('email'))
df_contacts.write_csv('contacts_email.csv')
```

:::

## See also

- [Coalesce Columns](/transformations/coalesce-columns)
- [Fill Missing Values](/recipes/fill-missing-values)
- [Recipes](/recipes/overview)
