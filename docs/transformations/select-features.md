---
title: Select Features by Variance, Correlation or Top-K
description:
  Select Ciaren numeric features by variance, correlation or target relevance.
  Understand retained columns and run pandas and Polars exports.
search:
  select features variance threshold correlation kbest top k feature selection
  target
---

# Select Features — `selectFeatures`

Remove numeric fields using variance, correlation or relevance to a target.

## Use cases

- Remove constant or low-variance numeric columns.
- Compare a smaller set of numeric predictors during exploration.

## What it does

`variance` drops numeric columns that do not exceed the variance threshold.
`correlation` computes absolute pairwise correlation and drops the later column
of pairs above the threshold, preserving original ordering. Both examine all
numeric columns and leave non-numeric columns in place.

`kbest` considers numeric columns other than the target, keeps up to `k`
selected features, and retains the target and non-feature columns in their
original order. Its scorer is `f_regression` for a numeric target with more than
20 distinct values; otherwise it is `f_classif`. The node refits on every input
and emits a dataframe, not a fitted selector.

## Configuration

| Config key      | Type    | Required    | Description                                                                   |
| --------------- | ------- | ----------- | ----------------------------------------------------------------------------- |
| `method`        | string  | No          | `variance` (default), `correlation`, or `kbest`                               |
| `threshold`     | number  | No          | When omitted: `0.0` for variance, `0.9` for correlation. Not used by `kbest`  |
| `target_column` | string  | For `kbest` | Existing target column; excluded from candidate features                      |
| `k`             | integer | For `kbest` | Positive integer, capped to available numeric features; editor starts at `10` |

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv) and
save it as `customers.csv` beside the script. These are complete exports from
File Input → this node → File Output; additional preparation steps are stated
below.

The flow first uses [Drop columns](./drop-columns.md) to remove `customer_id`.
Then `kbest` selects two predictors of `churn` and writes `select-features.csv`.
It keeps the 16 rows, the target and two numeric feature columns.

The node configuration is:

```json
{
  "method": "kbest",
  "target_column": "churn",
  "k": 2
}
```

Both flow engines run this ML step through pandas/scikit-learn. The Polars
script includes the actual conversion into pandas and back into Polars.

### pandas

```python
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif, f_regression

df_customers = pd.read_csv('customers.csv')
df_customers = df_customers.drop(columns=['customer_id'])
_features = [c for c in df_customers.select_dtypes(include='number').columns if c != 'churn']
_scorer = f_regression if (pd.api.types.is_numeric_dtype(df_customers['churn']) and df_customers['churn'].nunique() > 20) else f_classif
_sel = SelectKBest(_scorer, k=min(2, len(_features))).fit(df_customers[_features], df_customers['churn'])
_kept = [c for c, kp in zip(_features, _sel.get_support()) if kp]
df_customers = df_customers.drop(columns=[c for c in _features if c not in _kept])
df_customers.to_csv('select-features.csv', index=False)
```

### Polars

```python
import polars as pl
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif, f_regression

df_customers = pl.read_csv('customers.csv')
df_customers = df_customers.drop(['customer_id'])
_eager_1 = df_customers.to_pandas()
_features = [c for c in _eager_1.select_dtypes(include='number').columns if c != 'churn']
_scorer = f_regression if (pd.api.types.is_numeric_dtype(_eager_1['churn']) and _eager_1['churn'].nunique() > 20) else f_classif
_sel = SelectKBest(_scorer, k=min(2, len(_features))).fit(_eager_1[_features], _eager_1['churn'])
_kept = [c for c, kp in zip(_features, _sel.get_support()) if kp]
_eager_2 = _eager_1.drop(columns=[c for c in _features if c not in _kept])
df_1 = pl.from_pandas(_eager_2)
df_1.write_csv('select-features.csv')
```

## Tips & common mistakes

- The catalog starts with variance threshold zero. Check the threshold when
  changing methods rather than assuming the editor applies the omitted-key
  correlation default.
- Variance/correlation do not distinguish numeric IDs or targets from features;
  either can be dropped.
- `kbest` chooses its scorer from target dtype and distinct-value count. A small
  continuous target can be treated as classification; inspect whether that is
  appropriate.
- Fit feature selection only on training rows when evaluating a model. This node
  does not persist a selector for a separate test branch; export and retain a
  fitted selector in your own pipeline when needed.
- If no numeric feature survives a variance threshold, scikit-learn raises an
  error; lower the threshold or change the input.

## See also

- [Train/Test Split](./train-test-split.md) ·
  [Reduce Dimensions](./reduce-dimensions.md)
- [Drop columns](./drop-columns.md)
- [Feature-selection leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)
