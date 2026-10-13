---
title: Classifier Model for Cross-Validation
description: Configure an unfitted classifier in Ciaren for cross-validation. Learn model wires, feature selection, preprocessing and runnable pandas or Polars exports.
search: classifier model unfitted classification model definition cross validation
---

# Classifier Model — `mlClassifierModel`

Compare classification algorithms before fitting a final model for predictions.

## What it does

Reads the incoming column schema and emits an **unfitted model definition** on
its `model` output. It carries the algorithm, target, feature names,
hyperparameters and preprocessing. The definition does not fit the data,
create an MLflow run or save a trained artifact; `model_uri` and
`mlflow_run_id` are null.

Connect the same dataset to this node's `in` input and to
[Cross-Validate](./cross-validate.md)'s `in` input. Connect this node's purple
`model` output to Cross-Validate's `model` input. Cross-Validate builds and fits
a fresh pipeline within each fold. Definition nodes do not have a data output.

This node accepts classification models only. It has no training-row minimum,
because it does not train; Cross-Validate requires at least ten incoming rows.
The target and selected features must exist, the target cannot also be a
feature, and the configured feature-count limit applies.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `model_type` | string | Yes | An algorithm for this node's task; editor default: `logistic_regression` |
| `target_column` | string | Yes | Existing target column; the editor starts blank |
| `feature_columns` | string[] | No | Existing predictors; omitted or `[]` selects all columns except the target |
| `hyperparameters` | object | No | Algorithm-specific settings; defaults to `{}` and then the estimator defaults |
| `preprocessing` | object | No | Numeric/categorical column lists, imputation and scaling; see below |
| `seed` | integer | Yes | Reproducibility seed; editor default `42` |

With empty or omitted `preprocessing`, numeric and categorical columns are
inferred from the chosen features. Numeric columns use median imputation and
standard scaling; categorical columns use most-frequent imputation and one-hot
encoding. For an explicit nonempty preprocessing object, supply
`numeric_columns` and/or `categorical_columns`: missing lists are empty. If both
lists are empty, the estimator receives the raw features without preprocessing.

Numeric options are `numeric_strategy` (`standard_scaler`, `minmax_scaler`,
`robust_scaler`, or another value to omit scaling) and `impute_numeric` (default
`median`). Categorical imputation uses `impute_categorical` (default
`most_frequent`). These steps are fitted inside each Cross-Validate fold.

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv)
and save it as `customers.csv` in the directory where you run the script.
These complete exports define a `logistic_regression` model and send it to three-fold
K-Fold Cross-Validate, then write `classifier-model-scores.csv`.

The target is `churn` and the features are `tenure`, `monthly_charges`, `support_calls`; the customer ID is
excluded. The output has three rows containing the fold number, accuracy, weighted F1 and actual fit time.
The sample is a small demonstration, so its scores are not evidence of model
quality on a real customer population. Fit times vary between executions.

The definition-node configuration is:

```json
{
  "model_type": "logistic_regression",
  "target_column": "churn",
  "feature_columns": [
    "tenure",
    "monthly_charges",
    "support_calls"
  ],
  "seed": 42
}
```

The Cross-Validate configuration is `cv_strategy="kfold"`, `n_splits=3` and
`seed=42`. Both flow engines use pandas/scikit-learn at the ML boundary. Run the
export in an environment with Ciaren installed: Cross-Validate imports Ciaren's
registered model builder (`app.ml.models`). It does not create a final model
artifact or contact an MLflow tracking service.

### pandas

```python
import pandas as pd
import json
from app.ml.models import build_estimator
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_validate, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

df_customers = pd.read_csv('customers.csv')
_model_config = {'model_type': 'logistic_regression', 'target_column': 'churn', 'feature_columns': ['tenure', 'monthly_charges', 'support_calls'], 'hyperparameters': None, 'preprocessing': None, 'seed': 42}
_model_config['feature_columns'] = _model_config['feature_columns'] or [c for c in df_customers.columns if c != _model_config['target_column']]
_model_config['hyperparameters'] = _model_config['hyperparameters'] or {}
_model_config['preprocessing'] = _model_config['preprocessing'] or {}
df_1 = pd.DataFrame([{'mlflow_run_id': None, 'model_uri': None, 'task_type': 'classification', 'model_type': 'logistic_regression', 'target_column': _model_config['target_column'], 'feature_columns_json': json.dumps(_model_config['feature_columns']), 'model_config_json': json.dumps(_model_config)}])
_model_ref = df_1.iloc[0]
_model_config = json.loads(_model_ref['model_config_json'])
_task = _model_ref.get('task_type')
_target = _model_config['target_column']
_features = _model_config.get('feature_columns') or [c for c in df_customers.columns if c != _target]
_X = df_customers[_features]
_y = df_customers[_target]
_pre = _model_config.get('preprocessing') or {}
if _pre:
    _numeric = _pre.get('numeric_columns', [])
    _categorical = _pre.get('categorical_columns', [])
else:
    _numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
    _categorical = [c for c in _features if c not in _numeric]
_num_strategy = _pre.get('numeric_strategy', 'standard_scaler')
_scalers = {
    'standard_scaler': StandardScaler,
    'minmax_scaler': MinMaxScaler,
    'robust_scaler': RobustScaler,
}
_transformers = []
if _numeric:
    _num_steps = [('impute', SimpleImputer(strategy=_pre.get('impute_numeric', 'median')))]
    if _num_strategy in _scalers:
        _num_steps.append(('scale', _scalers[_num_strategy]()))
    _transformers.append(('num', Pipeline(_num_steps), _numeric))
if _categorical:
    _cat_steps = [
        ('impute', SimpleImputer(strategy=_pre.get('impute_categorical', 'most_frequent'))),
        ('encode', OneHotEncoder(handle_unknown='ignore')),
    ]
    _transformers.append(('cat', Pipeline(_cat_steps), _categorical))
_steps = []
if _transformers:
    _steps.append(('preprocessor', ColumnTransformer(_transformers, remainder='drop')))
_estimator = build_estimator(
    _model_config['model_type'],
    _model_config.get('hyperparameters'),
    _model_config.get('seed'),
)
_steps.append(('model', _estimator))
_pipeline = Pipeline(_steps)
_cv = KFold(n_splits=3, shuffle=True, random_state=42)
_scoring = []
if not _scoring:
    if _task == 'classification':
        _scoring = ['accuracy', 'f1_weighted']
    else:
        _scoring = ['r2', 'neg_root_mean_squared_error']
_scores = cross_validate(_pipeline, _X, _y, cv=_cv, scoring=_scoring, return_train_score=False)
_rows = []
_n_folds = len(_scores['fit_time'])
for _i in range(_n_folds):
    _row = {'fold': _i + 1}
    for _m in _scoring:
        _v = _scores['test_' + _m][_i]
        _row[_m[4:] if _m.startswith('neg_') else _m] = -_v if _m.startswith('neg_') else _v
    _row['fit_time_s'] = _scores['fit_time'][_i]
    _rows.append(_row)
df_2 = pd.DataFrame(_rows)
df_2.to_csv('classifier-model-scores.csv', index=False)
```

### Polars

```python
import polars as pl
import json
import pandas as pd
from app.ml.models import build_estimator
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_validate, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_model_config = {'model_type': 'logistic_regression', 'target_column': 'churn', 'feature_columns': ['tenure', 'monthly_charges', 'support_calls'], 'hyperparameters': None, 'preprocessing': None, 'seed': 42}
_model_config['feature_columns'] = _model_config['feature_columns'] or [c for c in _eager_1.columns if c != _model_config['target_column']]
_model_config['hyperparameters'] = _model_config['hyperparameters'] or {}
_model_config['preprocessing'] = _model_config['preprocessing'] or {}
_eager_2 = pd.DataFrame([{'mlflow_run_id': None, 'model_uri': None, 'task_type': 'classification', 'model_type': 'logistic_regression', 'target_column': _model_config['target_column'], 'feature_columns_json': json.dumps(_model_config['feature_columns']), 'model_config_json': json.dumps(_model_config)}])
_eager_3 = df_customers.to_pandas()
_model_ref = _eager_2.iloc[0]
_model_config = json.loads(_model_ref['model_config_json'])
_task = _model_ref.get('task_type')
_target = _model_config['target_column']
_features = _model_config.get('feature_columns') or [c for c in _eager_3.columns if c != _target]
_X = _eager_3[_features]
_y = _eager_3[_target]
_pre = _model_config.get('preprocessing') or {}
if _pre:
    _numeric = _pre.get('numeric_columns', [])
    _categorical = _pre.get('categorical_columns', [])
else:
    _numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
    _categorical = [c for c in _features if c not in _numeric]
_num_strategy = _pre.get('numeric_strategy', 'standard_scaler')
_scalers = {
    'standard_scaler': StandardScaler,
    'minmax_scaler': MinMaxScaler,
    'robust_scaler': RobustScaler,
}
_transformers = []
if _numeric:
    _num_steps = [('impute', SimpleImputer(strategy=_pre.get('impute_numeric', 'median')))]
    if _num_strategy in _scalers:
        _num_steps.append(('scale', _scalers[_num_strategy]()))
    _transformers.append(('num', Pipeline(_num_steps), _numeric))
if _categorical:
    _cat_steps = [
        ('impute', SimpleImputer(strategy=_pre.get('impute_categorical', 'most_frequent'))),
        ('encode', OneHotEncoder(handle_unknown='ignore')),
    ]
    _transformers.append(('cat', Pipeline(_cat_steps), _categorical))
_steps = []
if _transformers:
    _steps.append(('preprocessor', ColumnTransformer(_transformers, remainder='drop')))
_estimator = build_estimator(
    _model_config['model_type'],
    _model_config.get('hyperparameters'),
    _model_config.get('seed'),
)
_steps.append(('model', _estimator))
_pipeline = Pipeline(_steps)
_cv = KFold(n_splits=3, shuffle=True, random_state=42)
_scoring = []
if not _scoring:
    if _task == 'classification':
        _scoring = ['accuracy', 'f1_weighted']
    else:
        _scoring = ['r2', 'neg_root_mean_squared_error']
_scores = cross_validate(_pipeline, _X, _y, cv=_cv, scoring=_scoring, return_train_score=False)
_rows = []
_n_folds = len(_scores['fit_time'])
for _i in range(_n_folds):
    _row = {'fold': _i + 1}
    for _m in _scoring:
        _v = _scores['test_' + _m][_i]
        _row[_m[4:] if _m.startswith('neg_') else _m] = -_v if _m.startswith('neg_') else _v
    _row['fit_time_s'] = _scores['fit_time'][_i]
    _rows.append(_row)
_eager_4 = pd.DataFrame(_rows)
df_1 = pl.from_pandas(_eager_4)
df_1.write_csv('classifier-model-scores.csv')
```

## Tips and common mistakes

- Use a definition for evaluation; use a Train node when you need a saved
  model for Predict or Feature Importance. A definition cannot supply fitted
  predictions.
- List predictors explicitly when the input includes IDs or columns that
  would leak the answer. Empty `feature_columns` includes every non-target
  column, including IDs.
- When configuring preprocessing explicitly, include the column lists. Setting
  only a scaling strategy leaves no selected preprocessing columns.
- Keep standalone feature engineering out of the evaluation's full-data branch
  when it learns from the data. Put imputation, scaling and encoding in the
  model definition so they are fitted within each fold.

## See also

- [Cross-Validate](./cross-validate.md)
- [Regressor Model](./regressor-model.md)
- [Machine Learning nodes](./machine-learning.md#train-nodes) — final training
- [ML Quick Start](../guide/ml-quickstart.md)
