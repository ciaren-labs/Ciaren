---
title: Clean Messy Text in a CSV
description: Trim spaces and lowercase an email column in Ciaren with two String Transform nodes, so the same address matches in a join or deduplication. Includes the pandas and Polars export.
search: recipe clean messy text csv trim whitespace strip lowercase email normalize pandas polars
---

# Clean Messy Text in a CSV

The email `"  ADA@EXAMPLE.COM "` does not match `ada@example.com` in a join or
in Remove Duplicates, although both belong to the same person. Strip the
surrounding spaces, then lowercase the text, so equal addresses become equal
values.

**You'll use:** [File Input](/transformations/file-input) →
[String Transform](/transformations/string-transform) → String Transform →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"customers.csv"},
  {"type":"transform","label":"String Transform","detail":"email · Strip spaces"},
  {"type":"transform","label":"String Transform","detail":"email · Lowercase"},
  {"type":"output","label":"File Output","detail":"customers_clean"}
]' />

## Sample data

Save this as `customers.csv`. Customers 1 and 4 have the same address written
two ways, customer 3 has no email, and customer 5 has only spaces.

```csv
customer_id,email
1,"  ADA@EXAMPLE.COM "
2,Grace@Example.com
3,
4,ada@example.com
5,"   "
```

## Steps

1. On **Datasets**, upload `customers.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `customers.csv`.
3. Add **String Transform**. Set **Column** to `email` and click the **Strip
   spaces** operation. It removes spaces at the start and end of each value.
4. Add a second **String Transform**. Set **Column** to `email` and click
   **Lowercase**. One node applies one operation, so the two steps need two
   nodes.
5. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `customers_clean`. Connect the nodes in order and click **Run**.

## Result

| customer_id | email |
| --- | --- |
| 1 | `ada@example.com` |
| 2 | `grace@example.com` |
| 3 | null |
| 4 | `ada@example.com` |
| 5 | empty text (`""`) |

![Customer 1 and customer 4 emails differ by spaces and by case; after Strip spaces they still differ by case, and after Lowercase they are equal](/illustrations/recipes/clean-text-strip-lower.svg)

## Check the result

Save the flow, click **Preview**, select the second String Transform node and
click **Run preview**. Customers 1 and 4 should show the same
`ada@example.com`. If customer 1 still shows spaces or capitals, one of the
two String Transform nodes is not in the chain before the node you preview.
Their order does not matter.

## Pitfalls

- **Clean both sides of a join.** Apply the same steps to the key column of
  each input before a [Join](/transformations/join), or the keys still differ.
- **Only spaces become empty text, not null.** Customer 5 ends up as `""`,
  which Fill Nulls and Coalesce do not treat as missing. In a CSV output an
  empty text and a null can look the same, so check them in the preview.
- **Strip spaces does not touch inner spaces.** `ada @example.com` keeps its
  space. Use the **Find & Replace** operation for characters inside the value.
- **Lowercase only where case carries no meaning.** Keep passwords, tokens and
  case-sensitive IDs as they are. Cleaning does not check that an address is
  valid or deliverable.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `customers.csv` from the script's folder and
writes `customers_clean.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_customers = pd.read_csv('customers.csv')

df_customers = (
    df_customers.assign(email=lambda _d: _d['email'].astype('string').str.strip())
    .assign(email=lambda _d: _d['email'].astype('string').str.lower())
)

df_customers.to_csv('customers_clean.csv', index=False)
```

```python [Polars]
import polars as pl

df_customers = pl.read_csv('customers.csv')

df_customers = (
    df_customers.with_columns(pl.col('email').cast(pl.Utf8).str.strip_chars())
    .with_columns(pl.col('email').cast(pl.Utf8).str.to_lowercase())
)

df_customers.write_csv('customers_clean.csv')
```

:::

## See also

- [String Transform](/transformations/string-transform)
- [Remove Duplicate Rows](/recipes/remove-duplicate-rows)
- [Recipes](/recipes/overview)
