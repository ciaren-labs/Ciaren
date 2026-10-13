---
title: Predict Rows with a Trained ML Model
description: Score held-out rows in Ciaren with a trained model. Configure prediction batches and class probabilities, and run complete pandas or Polars export examples.
---

# Predict — `mlPredict`

Add predictions to new rows while keeping their original columns and order.

## What it does

Connect rows to `in` and a Train node's purple `model` output to `model`.
Alternatively, set `model_uri` to an existing trained artifact, such as
`models:/churn@production`. A blank URI uses the wired reference. At runtime,
an explicit nonblank URI overrides that wire. The current export prefers the
wired model when both are supplied; use one source to keep execution consistent.

The `out` frame contains the input columns plus `output_column` and any class
probability columns. When fitted feature names or a Train reference record the
expected features, missing features raise an error and extra columns are
excluded from scoring but remain in the output. An external model without
either source of feature names receives all input columns: select and order
its features yourself before Predict. Fitted preprocessing runs
inside the model; do not independently refit it on the rows being scored.

The model must expose `predict`. An unfitted Classifier/Regressor Model
reference has no trained artifact: use a Train node for prediction. Preview
passes input rows through without loading the model or calculating predictions.
Run the flow to see scored rows.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `model_uri` | string | No | Default `""`; use the wired model or a trusted MLflow URI |
| `output_column` | string | No | Prediction column; default `prediction` |
| `output_proba_columns` | string[] or null | No | Default `[]`; one name per class, in `model.classes_` order |
| `batch_size` | positive integer or null | No | Default `null`; number of rows per `predict` call |

Batching preserves row order and includes the final partial batch. It applies
only to `predict`: requesting probabilities still calls `predict_proba` on the
whole feature frame. The flow and generated script still hold the dataset in
memory; batching does not make them streaming workflows.

If an output name already exists, runtime warns and overwrites that column.
Choose fresh prediction and probability names to preserve existing values.
Probability names must match the model's number of classes. Runtime warns and
skips probabilities for models without `predict_proba`; the current export
calls that method directly, so request probabilities only for supported models.

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

This example predicts `churn` with a 20-tree random forest, trained on
`tenure`, `monthly_charges` and `support_calls`; `customer_id` is excluded.
The split is stratified by `churn`. Four held-out rows are scored in two batches
of two. The probability columns correspond to classes `0` and `1`.

The consumer configuration is:

```json
{
  "output_column": "prediction",
  "output_proba_columns": [
    "p_stay",
    "p_churn"
  ],
  "batch_size": 2
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
import mlflow.sklearn
import numpy as np
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
df_4 = df_2.copy()
_model_features = list(getattr(df_3, 'feature_names_in_', df_2.columns))
_batch_size = 2
if _batch_size is None or len(df_2) <= _batch_size:
    df_4['prediction'] = df_3.predict(df_2[_model_features])
else:
    df_4['prediction'] = np.concatenate([
        df_3.predict(df_2.iloc[_i : _i + _batch_size][_model_features])
        for _i in range(0, len(df_2), _batch_size)
    ])
_proba = df_3.predict_proba(df_2[_model_features])
df_4['p_stay'] = _proba[:, 0]
df_4['p_churn'] = _proba[:, 1]
df_4.to_csv('predict.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import mlflow.sklearn
import numpy as np
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
_eager_6 = df_2.to_pandas()
_eager_7 = _eager_6.copy()
_model_features = list(getattr(_eager_5, 'feature_names_in_', _eager_6.columns))
_batch_size = 2
if _batch_size is None or len(_eager_6) <= _batch_size:
    _eager_7['prediction'] = _eager_5.predict(_eager_6[_model_features])
else:
    _eager_7['prediction'] = np.concatenate([
        _eager_5.predict(_eager_6.iloc[_i : _i + _batch_size][_model_features])
        for _i in range(0, len(_eager_6), _batch_size)
    ])
_proba = _eager_5.predict_proba(_eager_6[_model_features])
_eager_7['p_stay'] = _proba[:, 0]
_eager_7['p_churn'] = _proba[:, 1]
df_3 = pl.from_pandas(_eager_7)
df_3.write_csv('predict.csv')
```

## Tips and common mistakes

- Load only artifacts you trust. MLflow and joblib models can execute Python
  code during loading; a validated URI is not a sandbox.
- Keep training features available with compatible types. A target or customer
  ID can remain in the output without becoming an input to the model.
- A probability is a model estimate, not a guarantee. This small demonstration
  cannot establish quality on a real customer population.
- The sample writes `predict.csv` with four rows. Predictions are `0, 1, 0, 1`,
  in customer order `8, 3, 14, 13`; the input file is unchanged.

## See also

- [Train/Test Split](./train-test-split.md)
- [Evaluate](./evaluate.md)
- [Feature Importance](./feature-importance.md)
- [ML quick start](../guide/ml-quickstart.md)
