---
title: "Train Regression Models with MLflow"
description: "Train regressors in Ciaren with fitted preprocessing and MLflow artifacts. Learn model wires, regression metrics, limits, and runnable pandas or Polars exports."
---

# Train Regressor — `mlTrainRegressor`

Fit a final regression model to predict a numeric target.

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

Connect the purple `model` wire to [Predict](./predict.md) and evaluate
held-out values with [Evaluate](./evaluate.md). Built-in model types are
`linear_regression`, `ridge`, `lasso`, `random_forest_regressor`, `svr`,
`xgboost_regressor` and `lightgbm_regressor`. The last two require their optional
libraries (`pip install "ciaren[ml]"`); plugins can add further model types.

Training metadata reports `train_r2`, `train_rmse` and `train_mae` on the
training rows. RMSE and MAE use the target's units, and R² can be negative.
Use an unfitted [Regressor Model](./regressor-model.md) with
[Cross-Validate](./cross-validate.md) when you need fold scores.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `model_type` | string | Yes | This task's algorithm; editor default `random_forest_regressor` |
| `target_column` | string | Yes | Existing target column; editor starts blank |
| `feature_columns` | string[] | No | Default `[]`; explicitly select predictors to exclude IDs and unrelated labels |
| `hyperparameters` | object | No | Default `{}`; estimator options, with host bounds and constructor validation |
| `preprocessing` | object | No | Default omitted; infer numeric and categorical features, or supply explicit lists |
| `seed` | integer | Yes | Editor default `42`; builders with a random-state option use it unless a hyperparameter overrides it |
| `mlflow_experiment` | string | No | Experiment name; omitted or blank uses `ciaren` |

Omitted or empty features select all columns except the target. Selecting
the target as a predictor is rejected as leakage. Exclude IDs and unrelated
labels explicitly.

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

The example fits a 20-tree random forest to predict `monthly_charges` from
`tenure` and `support_calls`. The non-stratified split keeps four rows held out.
Connect `train` to Train Regressor, its model wire to Predict, and `test` to
Predict's data input. The output `train-regressor.csv` contains customers
`1, 2, 6, 15` with predictions approximately `82.845, 47.19, 41.505, 82.71`.
These demonstration results do not establish generalization performance.

The Train configuration is:

```json
{
  "model_type": "random_forest_regressor",
  "target_column": "monthly_charges",
  "feature_columns": [
    "tenure",
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
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
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
df_3 = Pipeline([('preprocessor', _preprocessor), ('model', RandomForestRegressor(n_estimators=20, random_state=42))])
df_3.fit(_X, _y)
df_4 = df_2.copy()
_model_features = list(getattr(df_3, 'feature_names_in_', df_2.columns))
df_4['prediction'] = df_3.predict(df_2[_model_features])
df_4.to_csv('train-regressor.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import mlflow.sklearn
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
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
_eager_5 = Pipeline([('preprocessor', _preprocessor), ('model', RandomForestRegressor(n_estimators=20, random_state=42))])
_eager_5.fit(_X, _y)
_eager_6 = df_2.to_pandas()
_eager_7 = _eager_6.copy()
_model_features = list(getattr(_eager_5, 'feature_names_in_', _eager_6.columns))
_eager_7['prediction'] = _eager_5.predict(_eager_6[_model_features])
df_3 = pl.from_pandas(_eager_7)
df_3.write_csv('train-regressor.csv')
```

## Tips and common mistakes

- Keep the target out of selected features, even when it is numeric.
- Train on one branch and score the held-out branch; fitting standalone
  preprocessing on the full dataset can leak information.
- A supplied seed is still required for estimators without a random-state
  option, such as Linear Regression. It does not make every algorithm stochastic.
- For negative held-out R², compare against a baseline and inspect features;
  the value is not necessarily a computation error.

## See also

- [Predict](./predict.md)
- [Evaluate](./evaluate.md)
- [Regressor Model](./regressor-model.md)
- [Train/Test Split](./train-test-split.md)
- [ML quick start](../guide/ml-quickstart.md)
