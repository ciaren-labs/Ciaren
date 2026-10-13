---
title: Rank ML Features with Feature Importance
description: Rank trained-model features in Ciaren using tree importances or linear coefficients. Learn model wires, top-N output, and runnable pandas or Polars exports.
---

# Feature Importance — `featureImportance`

Inspect which features a trained tree or linear model uses most.

## What it does

Connect a Train node's purple `model` output to this node's only input,
`model`. It loads the trained artifact and emits an `out` frame containing
`feature_name`, `importance` and `rank`, sorted by decreasing importance.
Ranks start at `1`. It does not accept a data wire or train another model.
An unfitted Classifier/Regressor Model definition has no usable `model_uri`
and cannot provide importances.

Tree estimators supply `feature_importances_`. Linear estimators supply
absolute `coef_` values; multiclass coefficients are averaged in absolute
value across classes. Models with neither attribute, such as KNN or an RBF
SVM, raise an error. When preprocessing expands a category, the result ranks
the transformed features separately rather than combining them into one score.

Names come from fitted preprocessing or the model's feature names. If names
cannot be recovered, runtime uses generic names such as `feature_0`.
Preview passes the model-reference frame through without loading the model
or extracting importance; run the flow to obtain the ranked table.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `top_n` | positive integer or null | No | Default `null`; return every feature, or the first N ranked rows |

A limit greater than the feature count returns every available feature.
Tree importances and absolute linear coefficients have different scales;
coefficients are not automatically normalized. Importance does not establish
causality, and correlated features can share or obscure each other's scores.

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv)
and save it as `customers.csv` beside the script. Run with Ciaren installed and
its ML dependencies available. Both engines use pandas/scikit-learn at the ML
boundary; the Polars export converts back for the CSV output.

The sample has 16 rows. Train/Test Split uses `test_size=0.25` and `seed=42`,
so training sees 12 rows and four distinct rows remain held out. The scripts
fit preprocessing on training rows only. In the editor, Train logs an MLflow
model artifact and consumers load its reference. These exports fit a pipeline
in memory and do not save a model or create an MLflow run.

This example trains a 20-tree random forest on `churn`, using `tenure`,
`monthly_charges` and `support_calls` as features. Train/Test Split is
stratified by `churn`; only the 12 training rows fit the model. The four
held-out rows remain unused in importance extraction. `top_n=2` writes two
ranked rows to `feature-importance.csv`.

The consumer configuration is:

```json
{
  "top_n": 2
}
```

The Train configuration is:

```json
{
  "model_type": "random_forest_classifier",
  "target_column": "churn",
  "feature_columns": [
    "tenure",
    "monthly_charges",
    "support_calls"
  ],
  "hyperparameters": {
    "n_estimators": 20
  },
  "seed": 42
}
```

### pandas

```python
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler

df_customers = pd.read_csv('customers.csv')
df_1, df_2 = train_test_split(df_customers, test_size=0.25, random_state=42, stratify=df_customers['churn'])
df_1 = df_1.reset_index(drop=True)
df_2 = df_2.reset_index(drop=True)
_features = ['tenure', 'monthly_charges', 'support_calls']
_X = df_1[_features]
_numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
_categorical = [c for c in _features if c not in _numeric]
_transformers = []
if _numeric:
    _transformers.append(('num', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), _numeric))
if _categorical:
    _transformers.append(('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), _categorical))
_preprocessor = ColumnTransformer(_transformers, remainder='drop')
_y = df_1['churn']
df_3 = Pipeline([('preprocessor', _preprocessor), ('model', RandomForestClassifier(n_estimators=20, random_state=42))])
df_3.fit(_X, _y)
_est = df_3.named_steps.get('model', df_3) if hasattr(df_3, 'named_steps') else df_3
_imp = getattr(_est, 'feature_importances_', None)
if _imp is None:
    _imp = abs(_est.coef_).mean(axis=0) if _est.coef_.ndim > 1 else abs(_est.coef_)
if hasattr(df_3, 'named_steps') and 'preprocessor' in df_3.named_steps:
    _raw = [str(c) for c in df_3[:-1].get_feature_names_out()]
    _names = [next((c[len(p):] for p in ('num__', 'cat__', 'remainder__') if c.startswith(p)), c) for c in _raw]
else:
    _fn = getattr(_est, 'feature_names_in_', None)
    _names = [str(c) for c in _fn] if _fn is not None else [f'feature_{i}' for i in range(len(_imp))]
df_3 = pd.DataFrame({'feature_name': _names, 'importance': _imp}).sort_values('importance', ascending=False).reset_index(drop=True)
df_3['rank'] = df_3.index + 1
df_3 = df_3.head(2)
df_3.to_csv('feature-importance.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_eager_2, _eager_3 = train_test_split(_eager_1, test_size=0.25, random_state=42, stratify=_eager_1['churn'])
_eager_2 = _eager_2.reset_index(drop=True)
_eager_3 = _eager_3.reset_index(drop=True)
df_1 = pl.from_pandas(_eager_2)
df_2 = pl.from_pandas(_eager_3)
_eager_4 = df_1.to_pandas()
_features = ['tenure', 'monthly_charges', 'support_calls']
_X = _eager_4[_features]
_numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
_categorical = [c for c in _features if c not in _numeric]
_transformers = []
if _numeric:
    _transformers.append(('num', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), _numeric))
if _categorical:
    _transformers.append(('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), _categorical))
_preprocessor = ColumnTransformer(_transformers, remainder='drop')
_y = _eager_4['churn']
_eager_5 = Pipeline([('preprocessor', _preprocessor), ('model', RandomForestClassifier(n_estimators=20, random_state=42))])
_eager_5.fit(_X, _y)
_est = _eager_5.named_steps.get('model', _eager_5) if hasattr(_eager_5, 'named_steps') else _eager_5
_imp = getattr(_est, 'feature_importances_', None)
if _imp is None:
    _imp = abs(_est.coef_).mean(axis=0) if _est.coef_.ndim > 1 else abs(_est.coef_)
if hasattr(_eager_5, 'named_steps') and 'preprocessor' in _eager_5.named_steps:
    _raw = [str(c) for c in _eager_5[:-1].get_feature_names_out()]
    _names = [next((c[len(p):] for p in ('num__', 'cat__', 'remainder__') if c.startswith(p)), c) for c in _raw]
else:
    _fn = getattr(_est, 'feature_names_in_', None)
    _names = [str(c) for c in _fn] if _fn is not None else [f'feature_{i}' for i in range(len(_imp))]
_eager_6 = pd.DataFrame({'feature_name': _names, 'importance': _imp}).sort_values('importance', ascending=False).reset_index(drop=True)
_eager_6['rank'] = _eager_6.index + 1
_eager_6 = _eager_6.head(2)
df_3 = pl.from_pandas(_eager_6)
df_3.write_csv('feature-importance.csv')
```

## Tips and common mistakes

- Load only trusted artifacts. MLflow and joblib loading can execute Python
  code; path and URI validation do not isolate the model's code.
- Use a trained model with tree importance or linear coefficients. An
  unsupported estimator cannot produce this table merely by adding a model wire.
- A high rank is not a quality score for the model. Use
  [Evaluate](./evaluate.md) on held-out predictions as a separate check.
- In this sample, the first row is `support_calls` with importance `0.4`;
  the second is `tenure` with importance `0.3`. Tied features can change order
  across library versions; do not interpret their ordering as a measured gap.

## See also

- [Predict](./predict.md)
- [Evaluate](./evaluate.md)
- [Select Features](./select-features.md)
- [ML quick start](../guide/ml-quickstart.md)
