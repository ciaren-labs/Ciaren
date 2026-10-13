---
title: Reduce Dimensions with PCA
description:
  Replace selected Ciaren numeric features with PCA components while keeping
  other columns. Configure component counts and run pandas or Polars exports.
search:
  reduce dimensions PCA principal components explained variance prefix seed
---

# Reduce Dimensions — `reduceDimensions`

Compress selected numeric features into principal components for exploration.

## Use cases

- Inspect a lower-dimensional representation of correlated numeric features.
- Retain IDs and targets while replacing explicitly selected feature columns.

## What it does

Fits PCA on the selected columns, removes those original columns and appends
components named `<prefix>_1`, `<prefix>_2`, and so on. Other columns and row
order are retained. If `columns` is absent or empty, every numeric column is
selected, including numeric IDs or targets.

An integer component count is capped to the smaller of the number of selected
columns and rows. A fraction between zero and one requests an explained-variance
fraction. The node emits only an `out` dataframe and refits PCA on each input;
it does not expose a reusable fitted PCA model.

## Configuration

| Config key     | Type             | Required | Description                                                                           |
| -------------- | ---------------- | -------- | ------------------------------------------------------------------------------------- |
| `method`       | string           | No       | Only `pca` is supported; it is the default                                            |
| `columns`      | string[]         | No       | Selected numeric columns; empty or omitted selects all numeric columns                |
| `n_components` | integer or float | Yes      | Positive integer count, or a fraction strictly between 0 and 1; booleans are rejected; editor starts at `2` |
| `prefix`       | string           | No       | Component name prefix; default `pc`                                                   |
| `seed`         | integer or null  | No       | Optional PCA random state; editor starts at `42`, omitted API value is null           |

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv) and
save it as `customers.csv` beside the script. These are complete exports from
File Input → this node → File Output; additional preparation steps are stated
below.

The flow standardizes `tenure`, `monthly_charges` and `support_calls` with
[Scale Features](./scale-features.md), then fits two PCA components with
`seed: 42`. It writes `reduce-dimensions.csv` with `customer_id`, `churn`,
`pc_1` and `pc_2`. The ID and target stay unchanged.

The node configuration is:

```json
{
  "method": "pca",
  "columns": ["tenure", "monthly_charges", "support_calls"],
  "n_components": 2,
  "prefix": "pc",
  "seed": 42
}
```

Both flow engines run this ML step through pandas/scikit-learn. The Polars
script includes the actual conversion into pandas and back into Polars.

### pandas

```python
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

df_customers = pd.read_csv('customers.csv')
df_customers = df_customers.copy()
df_customers[['tenure', 'monthly_charges', 'support_calls']] = StandardScaler().fit_transform(df_customers[['tenure', 'monthly_charges', 'support_calls']])
_cols = ['tenure', 'monthly_charges', 'support_calls']
_pca = PCA(n_components=min(2, len(_cols), len(df_customers)), random_state=42)
_comp = _pca.fit_transform(df_customers[_cols])
_names = [f'pc_{i + 1}' for i in range(_comp.shape[1])]
df_customers = pd.concat([df_customers.drop(columns=_cols), pd.DataFrame(_comp, columns=_names, index=df_customers.index)], axis=1)
df_customers.to_csv('reduce-dimensions.csv', index=False)
```

### Polars

```python
import polars as pl
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_eager_2 = _eager_1.copy()
_eager_2[['tenure', 'monthly_charges', 'support_calls']] = StandardScaler().fit_transform(_eager_2[['tenure', 'monthly_charges', 'support_calls']])
df_1 = pl.from_pandas(_eager_2)
_eager_3 = df_1.to_pandas()
_cols = ['tenure', 'monthly_charges', 'support_calls']
_pca = PCA(n_components=min(2, len(_cols), len(_eager_3)), random_state=42)
_comp = _pca.fit_transform(_eager_3[_cols])
_names = [f'pc_{i + 1}' for i in range(_comp.shape[1])]
_eager_4 = pd.concat([_eager_3.drop(columns=_cols), pd.DataFrame(_comp, columns=_names, index=_eager_3.index)], axis=1)
df_2 = pl.from_pandas(_eager_4)
df_2.write_csv('reduce-dimensions.csv')
```

## Tips & common mistakes

- Choose feature columns explicitly to avoid replacing an ID or target.
- PCA centers values but does not scale different units automatically; this
  exploratory example scales first.
- `1` means one component; `1.0` is not a valid variance fraction for this node.
- Scaling and PCA here refit on the incoming frame. Do not fit them
  independently on held-out data; retain fitted transformations in a pipeline
  for evaluation or prediction.
- Integer counts are capped; fractions are passed through to scikit-learn.

## See also

- [Scale Features](./scale-features.md) ·
  [Select Features](./select-features.md)
- [Train/Test Split](./train-test-split.md)
- [PCA in scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)
