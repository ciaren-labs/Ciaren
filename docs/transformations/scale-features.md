---
title: Scale Features with Standard, Min-Max or Robust Scaling
description:
  Scale selected numeric features in Ciaren with standard, min-max or robust
  scaling. Learn fitting limits and run pandas or Polars exports.
search:
  scale features standard scaler minmax normalize z score robust median IQR
---

# Scale Features — `scaleFeatures`

Put selected numeric columns on a comparable scale for exploration.

## Use cases

- Inspect feature values after min-max scaling.
- Prepare numeric dimensions for an exploratory PCA flow.

## What it does

Fits a scikit-learn scaler on the incoming rows and replaces only the selected
columns. `standard` uses mean and standard deviation, `minmax` uses the observed
range, and `robust` uses the median and interquartile range. Other columns and
row order are retained.

This dataframe node is **stateless**: each execution fits a new scaler and emits
only an `out` dataframe. It does not supply a fitted scaler on a model wire. For
train/predict workflows, configure scaling in a train node's Preprocessing
options so the fitted transformation travels with the model.

## Configuration

| Config key | Type     | Required | Description                                 |
| ---------- | -------- | -------- | ------------------------------------------- |
| `columns`  | string[] | Yes      | Non-empty list of existing numeric columns  |
| `method`   | string   | No       | `standard` (default), `minmax`, or `robust` |

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv) and
save it as `customers.csv` beside the script. These are complete exports from
File Input → this node → File Output; additional preparation steps are stated
below.

The example applies `minmax` only to `monthly_charges` and writes
`scale-features.csv`. On this sample the observed minimum becomes zero and
maximum becomes one; the ID, tenure, support-call count and target stay
unchanged.

The node configuration is:

```json
{
  "method": "minmax",
  "columns": ["monthly_charges"]
}
```

Both flow engines run this ML step through pandas/scikit-learn. The Polars
script includes the actual conversion into pandas and back into Polars.

### pandas

```python
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

df_customers = pd.read_csv('customers.csv')
df_customers = df_customers.copy()
df_customers[['monthly_charges']] = MinMaxScaler().fit_transform(df_customers[['monthly_charges']])
df_customers.to_csv('scale-features.csv', index=False)
```

### Polars

```python
import polars as pl
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_eager_2 = _eager_1.copy()
_eager_2[['monthly_charges']] = MinMaxScaler().fit_transform(_eager_2[['monthly_charges']])
df_1 = pl.from_pandas(_eager_2)
df_1.write_csv('scale-features.csv')
```

## Tips & common mistakes

- Do not independently fit this node on train and test branches: the parameters
  would differ. Use the train node's bundled preprocessing for that workflow.
- Select actual features rather than IDs or target columns.
- Fill missing values deliberately with [Fill nulls](./fill-nulls.md) when the
  next operation requires complete numeric data.
- Min-max scaling describes the fitted data's range; it is not a general
  guarantee about unseen values.

## See also

- [Train/Test Split](./train-test-split.md) ·
  [Reduce Dimensions](./reduce-dimensions.md)
- [ML Quick Start](../guide/ml-quickstart.md)
- [Preprocessing pitfalls in scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html)
