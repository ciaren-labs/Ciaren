---
title: Train/Test Split for Model Evaluation
description:
  Split Ciaren data into training and test outputs with a required seed,
  optional stratification and row limits. Includes pandas and Polars scripts.
search: train test split holdout seed stratify classification evaluation sklearn
---

# Train / Test Split — `trainTestSplit`

Reserve separate rows for training and evaluation before fitting a model.

## Use cases

- Hold out a test set for classification or regression.
- Preserve class proportions approximately with stratification.

## What it does

The `in` dataframe becomes two outputs, `train` and `test`. Every row appears in
exactly one output; columns are retained and pandas indexes are reset. Wire
`train` to a train node and `test` to Predict. The seed reproduces the split for
the same input and settings.

At least **10 training rows** must remain. Stratification requires at least two
examples per class, and both subsets must have room for the classes. A
continuous regression target is not a suitable stratification key.

## Configuration

| Config key        | Type           | Required | Description                                                              |
| ----------------- | -------------- | -------- | ------------------------------------------------------------------------ |
| `test_size`       | number         | No       | Fraction strictly between 0 and 1; default `0.2`                         |
| `stratify_column` | string or null | No       | Class column, or null for an unstratified split                          |
| `seed`            | integer        | Yes      | Required by validation; the editor starts at `42`. Booleans are rejected |

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv) and
save it as `customers.csv` beside the script. These are complete exports from
File Input → this node → File Output; additional preparation steps are stated
below.

The 16-row customer sample is split with `test_size: 0.25`, `seed: 42` and
`stratify_column: churn`. The scripts write 12 rows to `train.csv` and four to
`test.csv`; each subset contains both classes.

The node configuration is:

```json
{
  "test_size": 0.25,
  "stratify_column": "churn",
  "seed": 42
}
```

Both flow engines run this ML step through pandas/scikit-learn. The Polars
script includes the actual conversion into pandas and back into Polars.

### pandas

```python
import pandas as pd
from sklearn.model_selection import train_test_split

df_customers = pd.read_csv('customers.csv')
df_1, df_2 = train_test_split(df_customers, test_size=0.25, random_state=42, stratify=df_customers['churn'])
df_1 = df_1.reset_index(drop=True)
df_2 = df_2.reset_index(drop=True)
df_1.to_csv('train.csv', index=False)
df_2.to_csv('test.csv', index=False)
```

### Polars

```python
import polars as pl
import pandas as pd
from sklearn.model_selection import train_test_split

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_eager_2, _eager_3 = train_test_split(_eager_1, test_size=0.25, random_state=42, stratify=_eager_1['churn'])
_eager_2 = _eager_2.reset_index(drop=True)
_eager_3 = _eager_3.reset_index(drop=True)
df_1 = pl.from_pandas(_eager_2)
df_2 = pl.from_pandas(_eager_3)
df_1.write_csv('train.csv')
df_2.write_csv('test.csv')
```

## Tips & common mistakes

- Split before fitting scalers, encoders, feature selection or PCA. Never fit a
  transformation on held-out rows.
- Too few rows or a rare class can make a split invalid; reducing test size must
  still leave room for every stratified class.
- Keep the two handles separate. Sending training rows to Evaluate measures
  training performance rather than held-out performance.

## See also

- [ML Quick Start](../guide/ml-quickstart.md)
- [Scale Features](./scale-features.md) ·
  [Encode Categories](./encode-categories.md)
- [Model definitions and cross-validation](./machine-learning.md#model-definition-nodes)
