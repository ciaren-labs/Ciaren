---
title: Evaluate ML Predictions and Model Metrics
description: Evaluate held-out predictions in Ciaren. Learn classification, regression and clustering metrics, output tables, and complete pandas or Polars export examples.
---

# Evaluate — `mlEvaluate`

Turn scored rows into a metrics table you can inspect or save as CSV.

## What it does

Connect [Predict](./predict.md)'s `out` to `in`. Supervised evaluation needs
both the true target and the prediction in this frame; it does not take a model
wire, fit a model or call a tracking service. The `out` table has `metric` and
`value` columns, one row per computed scalar. Run metadata also contains the
metrics and task type. Preview passes the incoming rows through without
computing metrics, so its table differs from a completed run.

Use held-out predictions to estimate performance. Scores on training rows can
be optimistic, and a four-row demonstration is not a production validation.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `task_type` | string | Yes | `classification`, `regression` or `clustering`; editor default `classification` |
| `target_column` | string | For supervised tasks | True labels or values; editor starts blank |
| `prediction_column` | string | Yes | Predicted labels, values or cluster IDs; editor default `prediction` |
| `metrics` | string[] | No | Default `[]`; an empty list uses the task defaults below |
| `proba_columns` | string[] | No | Class probabilities for runtime ROC-AUC; default `[]` |
| `feature_columns` | string[] | No | Clustering features; omitted or empty selects numeric columns except the cluster label |

Classification defaults are `accuracy`, `precision`, `recall` and `f1`.
Precision, recall and F1 use weighted averaging and `zero_division=0`.
Optional runtime metrics are `roc_auc` and `confusion_matrix`. Binary ROC-AUC
uses the second of two probability columns for the positive class; align them
with the classifier's class order. Missing probability configuration or a
`ValueError` during ROC-AUC computation warns and omits that metric. An
undefined score, such as a binary target containing only one class, can instead
remain `NaN` with a warning; check for a finite value before interpreting it.
Confusion-matrix entries become
rows such as `cm_true0_pred1`; indices are positions, not class labels.

Regression defaults are `rmse`, `mae`, `r2` and `mape`; `residual_std` is also
supported. RMSE and MAE use the target's units. MAPE is a fraction, not a
percentage, and is unstable around zero targets. Residual standard deviation
uses the population convention. R² can be negative.

Clustering defaults are `silhouette` and `davies_bouldin`. Runtime warns and
returns no metrics when there are fewer than two distinct clusters or every
row has its own cluster. Exported clustering scripts do not include this guard
and may raise instead. Specify relevant features to avoid scoring an ID column.
Unknown metric names are ignored; choose only the names listed here.

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

This example trains Ridge to predict `monthly_charges` from `tenure` and
`support_calls`, then evaluates the four held-out predictions. The target is
excluded from the training features. The non-stratified split uses seed `42`.
Both complete scripts write `evaluate.csv` with five metric rows.

ROC-AUC and confusion-matrix metrics are omitted by the current export even
when a runtime flow requests them; the script inserts a note. The example
uses only metrics reproduced by both execution paths.

The consumer configuration is:

```json
{
  "task_type": "regression",
  "target_column": "monthly_charges",
  "prediction_column": "prediction",
  "metrics": [
    "rmse",
    "mae",
    "r2",
    "mape",
    "residual_std"
  ]
}
```

The Train configuration is:

```json
{
  "model_type": "ridge",
  "target_column": "monthly_charges",
  "feature_columns": [
    "tenure",
    "support_calls"
  ],
  "seed": 42
}
```

### pandas

```python
import pandas as pd
import joblib
import mlflow.sklearn
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler

df_customers = pd.read_csv('customers.csv')
df_1, df_2 = train_test_split(df_customers, test_size=0.25, random_state=42)
df_1 = df_1.reset_index(drop=True)
df_2 = df_2.reset_index(drop=True)
_features = ['tenure', 'support_calls']
_X = df_1[_features]
_numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
_categorical = [c for c in _features if c not in _numeric]
_transformers = []
if _numeric:
    _transformers.append(('num', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), _numeric))
if _categorical:
    _transformers.append(('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), _categorical))
_preprocessor = ColumnTransformer(_transformers, remainder='drop')
_y = df_1['monthly_charges']
df_3 = Pipeline([('preprocessor', _preprocessor), ('model', Ridge(random_state=42))])
df_3.fit(_X, _y)
df_4 = df_2.copy()
_model_features = list(getattr(df_3, 'feature_names_in_', df_2.columns))
df_4['prediction'] = df_3.predict(df_2[_model_features])
_metrics = {
    'rmse': root_mean_squared_error(df_4['monthly_charges'], df_4['prediction']),
    'mae': mean_absolute_error(df_4['monthly_charges'], df_4['prediction']),
    'r2': r2_score(df_4['monthly_charges'], df_4['prediction']),
    'mape': mean_absolute_percentage_error(df_4['monthly_charges'], df_4['prediction']),
    'residual_std': float(np.std(df_4['monthly_charges'] - df_4['prediction'])),
}
df_4 = pd.DataFrame([{'metric': k, 'value': v} for k, v in _metrics.items()])
df_4.to_csv('evaluate.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_eager_2, _eager_3 = train_test_split(_eager_1, test_size=0.25, random_state=42)
_eager_2 = _eager_2.reset_index(drop=True)
_eager_3 = _eager_3.reset_index(drop=True)
df_1 = pl.from_pandas(_eager_2)
df_2 = pl.from_pandas(_eager_3)
_eager_4 = df_1.to_pandas()
_features = ['tenure', 'support_calls']
_X = _eager_4[_features]
_numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
_categorical = [c for c in _features if c not in _numeric]
_transformers = []
if _numeric:
    _transformers.append(('num', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), _numeric))
if _categorical:
    _transformers.append(('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), _categorical))
_preprocessor = ColumnTransformer(_transformers, remainder='drop')
_y = _eager_4['monthly_charges']
_eager_5 = Pipeline([('preprocessor', _preprocessor), ('model', Ridge(random_state=42))])
_eager_5.fit(_X, _y)
_eager_6 = df_2.to_pandas()
_eager_7 = _eager_6.copy()
_model_features = list(getattr(_eager_5, 'feature_names_in_', _eager_6.columns))
_eager_7['prediction'] = _eager_5.predict(_eager_6[_model_features])
df_3 = pl.from_pandas(_eager_7)
_eager_8 = df_3.to_pandas()
_metrics = {
    'rmse': root_mean_squared_error(_eager_8['monthly_charges'], _eager_8['prediction']),
    'mae': mean_absolute_error(_eager_8['monthly_charges'], _eager_8['prediction']),
    'r2': r2_score(_eager_8['monthly_charges'], _eager_8['prediction']),
    'mape': mean_absolute_percentage_error(_eager_8['monthly_charges'], _eager_8['prediction']),
    'residual_std': float(np.std(_eager_8['monthly_charges'] - _eager_8['prediction'])),
}
_eager_9 = pd.DataFrame([{'metric': k, 'value': v} for k, v in _metrics.items()])
df_4 = pl.from_pandas(_eager_9)
df_4.write_csv('evaluate.csv')
```

## Tips and common mistakes

- Keep true labels in the scored data and set the correct task. Numeric
  class labels still require `classification`, not `regression`.
- Compare models on the same held-out rows. Split before fitting learned
  preprocessing, and keep the held-out rows out of training.
- The sample produces approximately `rmse=6.538684`, `mae=5.492843`,
  `r2=0.911528`, `mape=0.087492` and `residual_std=6.456119`.
  Values are rounded here; use the unrounded CSV for comparisons.
- Missing required columns fail the run. Preview does not establish that
  the selected metrics can be computed.

## See also

- [Predict](./predict.md)
- [Train/Test Split](./train-test-split.md)
- [Cross-Validate](./cross-validate.md)
- [ML quick start](../guide/ml-quickstart.md)
