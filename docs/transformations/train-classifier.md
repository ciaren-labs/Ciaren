---
title: "Train Classification Models with MLflow"
description: "Train classifiers in Ciaren with fitted preprocessing and MLflow artifacts. Learn model wires, training metrics, limits, and runnable pandas or Polars exports."
---

# Train Classifier — `mlTrainClassifier`

Fit a final classification model for scoring new rows.

## What it does

Connect training rows to `in`. The `model` output is a one-row reference,
not the training data or a live Python estimator. It records `mlflow_run_id`,
`model_uri`, `task_type`, `model_type`, `target_column`, `feature_columns_json`
and `model_config_json`. Run metadata contains the model URI, run ID and the
training metrics described below.

Runtime fits a scikit-learn pipeline, checks its serialized size and saves it
to MLflow. If saving fails, the node fails rather than returning a usable model
reference. Preview skips fitting and logging and emits a placeholder with null
run ID and URI; configuration and schema checks can still fail during preview.

Use the purple `model` wire with [Predict](./predict.md), then evaluate
held-out labels with [Evaluate](./evaluate.md). Supported built-in model types
are `logistic_regression`, `random_forest_classifier`, `svm_classifier`,
`knn_classifier`, `xgboost_classifier` and `lightgbm_classifier`. The last two
need their optional libraries (`pip install "ciaren[ml]"`). Installed plugins
can add model types; follow that provider's requirements.

Training metadata reports `train_accuracy` and `train_f1_weighted` on the rows
used to fit the model. Those are training scores, not held-out evaluation.
For fold-based model comparison, use an unfitted
[Classifier Model](./classifier-model.md) with [Cross-Validate](./cross-validate.md).

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `model_type` | string | Yes | This task's algorithm; editor default `random_forest_classifier` |
| `target_column` | string | Yes | Existing target column; editor starts blank |
| `feature_columns` | string[] | No | Default `[]`; explicitly select predictors to exclude IDs and unrelated labels |
| `hyperparameters` | object | No | Default `{}`; estimator options, with host bounds and constructor validation |
| `preprocessing` | object | No | Default omitted; infer numeric and categorical features, or supply explicit lists |
| `seed` | integer | Yes | Editor default `42`; builders with a random-state option use it unless a hyperparameter overrides it |
| `mlflow_experiment` | string | No | Experiment name; omitted or blank uses `ciaren` |

Omitted or empty features select all columns except the target. The target
cannot also be a feature; exclude customer IDs explicitly.

### Preprocessing and limits

With omitted or empty `preprocessing`, numeric features use median imputation
and standard scaling. Categorical features use most-frequent imputation and
one-hot encoding with unknown categories ignored. These steps are fitted on
this node's training rows and travel inside the saved pipeline.

For a nonempty preprocessing object, supply `numeric_columns` and/or
`categorical_columns`: absent lists are empty and columns outside those lists
are dropped. If both lists are empty, preprocessing is omitted and the raw
selected features reach the estimator. Numeric options are `numeric_strategy`
(`standard_scaler`, `minmax_scaler`, `robust_scaler`, or another value to omit
scaling), `impute_numeric` (default `median`) and `impute_categorical`
(default `most_frequent`).

Runtime requires at least ten rows and warns below fifty. Default host limits
are 5,000,000 training rows, 500 selected features and 500 MB of serialized
model data. Row and feature limits apply before fitting; model size is checked
after fitting and before saving. Configure them with
`CIAREN_ML_MAX_TRAINING_ROWS`, `CIAREN_ML_MAX_FEATURE_COLUMNS` and
`CIAREN_ML_MAX_MODEL_SIZE_MB`. The default hyperparameter numeric bound is
100,000 (`CIAREN_ML_MAX_HYPERPARAMETER_VALUE`).

MLflow tracking defaults to `./mlruns`; set `CIAREN_MLFLOW_TRACKING_URI` for a
configured store. Load only trusted artifacts: MLflow/joblib deserialization
can execute Python code, and URI/path checks do not sandbox that code.

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv)
and save it as `customers.csv` beside the script. The sample has 16 rows;
Train/Test Split uses `test_size=0.25` and `seed=42` to keep 12 training rows
separate from four held-out rows. Install Ciaren with its ML dependencies to
run the scripts. Polars exports cross into pandas/scikit-learn for fitting.

These are complete exports from the flow generator. They fit a pipeline in
memory; they do not create an MLflow run, save a model artifact, reproduce run
metadata metrics or enforce Ciaren's runtime row/feature/model-size guards.
The editor's trained-model reference becomes the actual pipeline variable in
the script. To retain an exported model, add your own trusted persistence step.

The example fits a 20-tree random forest on `churn`, with `tenure`,
`monthly_charges` and `support_calls` as predictors. The split is stratified by
`churn`. Connect `train` to Train Classifier, its model wire to Predict, and
`test` to Predict's data input. Predict writes four rows to
`train-classifier.csv`; predictions are `0, 1, 0, 1` in customer order
`8, 3, 14, 13`. The sample is too small to establish real-world model quality.

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
df_4['prediction'] = df_3.predict(df_2[_model_features])
df_4.to_csv('train-classifier.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import mlflow.sklearn
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
_eager_7['prediction'] = _eager_5.predict(_eager_6[_model_features])
df_3 = pl.from_pandas(_eager_7)
df_3.write_csv('train-classifier.csv')
```

## Tips and common mistakes

- Split before training. Fitted preprocessing stays inside the model rather
  than being refitted independently on the held-out branch.
- Probability support depends on the estimator. For `svm_classifier`, request
  `probability=true` in hyperparameters if you need `predict_proba`.
- Training scores can be optimistic; use held-out evaluation or cross-validation.
- Save failures mean no usable artifact was returned. On Windows, a long MLflow
  artifact path can cause this; use a shorter tracking path and rerun.

## See also

- [Predict](./predict.md)
- [Evaluate](./evaluate.md)
- [Classifier Model](./classifier-model.md)
- [Feature Importance](./feature-importance.md)
- [ML quick start](../guide/ml-quickstart.md)
