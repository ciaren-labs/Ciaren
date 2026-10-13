---
title: Encode Categories with One-Hot or Ordinal Codes
description:
  Encode Ciaren categorical features with one-hot flags or ordinal codes.
  Understand column changes and fitting limits in pandas and Polars flows.
search:
  encode categories onehot one hot ordinal categorical dummy columns drop first
---

# Encode Categories — `encodeCategories`

Turn the values of selected categorical fields into flags or codes.

## Use cases

- Inspect one-hot columns for a discrete category.
- Explore ordinal codes before choosing a model preprocessing strategy.

## What it does

With `onehot`, pandas `get_dummies` replaces the selected columns with category
flags; `drop_first` optionally omits the first category per column. Other
columns and rows remain. With `ordinal`, an `OrdinalEncoder` fits string
representations of the selected values and replaces those columns with numeric
codes.

The node fits on each incoming frame and emits only `out`, not a saved encoder.
Ordinal codes and one-hot schemas can change when the observed categories
change. Use the train node's bundled categorical preprocessing for a fitted
encoder that will be reused at prediction time.

## Configuration

| Config key   | Type     | Required | Description                                               |
| ------------ | -------- | -------- | --------------------------------------------------------- |
| `columns`    | string[] | Yes      | Non-empty list of existing columns to treat as categories |
| `method`     | string   | No       | `onehot` (default) or `ordinal`                           |
| `drop_first` | boolean  | No       | Default `false`; used only by `onehot`                    |

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv) and
save it as `customers.csv` beside the script. These are complete exports from
File Input → this node → File Output; additional preparation steps are stated
below.

Here the discrete `support_calls` count is treated as a category with `onehot`
and `drop_first: false`. The scripts write `encode-categories.csv`:
`support_calls` is replaced by `support_calls_<value>` flags, with one active
flag per row. All other fields, including `churn`, remain unchanged.

The node configuration is:

```json
{
  "method": "onehot",
  "columns": ["support_calls"],
  "drop_first": false
}
```

Both flow engines run this ML step through pandas/scikit-learn. The Polars
script includes the actual conversion into pandas and back into Polars.

### pandas

```python
import pandas as pd

df_customers = pd.read_csv('customers.csv')
df_customers = pd.get_dummies(df_customers, columns=['support_calls'], drop_first=False)
df_customers.to_csv('encode-categories.csv', index=False)
```

### Polars

```python
import polars as pl
import pandas as pd

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_eager_2 = pd.get_dummies(_eager_1, columns=['support_calls'], drop_first=False)
df_1 = pl.from_pandas(_eager_2)
df_1.write_csv('encode-categories.csv')
```

## Tips & common mistakes

- A selected column is treated as categorical even when its values are numeric.
  Choose this intentionally.
- High-cardinality IDs can create many dummy columns; do not encode an ID merely
  because it is present.
- Do not fit separate encoders on train and test data or assume independently
  fitted ordinal codes have the same meaning.
- Ordinal values are stringified before fitting; fill missing values first if
  you need an explicit missing-value category.

## See also

- [Train/Test Split](./train-test-split.md) ·
  [Select Features](./select-features.md)
- [Fill nulls](./fill-nulls.md)
- [ML Quick Start](../guide/ml-quickstart.md)
