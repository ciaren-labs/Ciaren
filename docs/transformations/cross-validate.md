---
title: Cross-Validate Classification and Regression Models
description: Evaluate classifier or regressor definitions in Ciaren with cross-validation. Configure folds, scoring and preprocessing, then export pandas or Polars code.
search: cross validate cross validation kfold stratified group time series model scores
---

# Cross-Validate — `mlCrossValidate`

Measure how a classifier or regressor performs on held-out folds without
creating a final trained model.

## What it does

Takes data on `in` and an unfitted model definition on `model`. Connect a
[Classifier Model](./classifier-model.md) or
[Regressor Model](./regressor-model.md), not a Train node. The definition supplies
the algorithm, target, features, hyperparameters and preprocessing.

Fits a fresh estimator and its preprocessing on each fold's training rows,
then scores the held-out rows. It emits one `out` row per split with `fold`, the
chosen metric columns and `fit_time_s`. Classification defaults to `accuracy`
and `f1_weighted`; regression defaults to `r2` and `root_mean_squared_error`.
Timing records the actual fit duration in seconds and varies across runs.

In the application, run metadata also includes per-fold scores and their
mean/standard deviation. No final model artifact or MLflow training run is
created. Preview does not fit models and returns an empty score frame. This
node can end a flow itself, or its scores can feed File Output.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `cv_strategy` | string | No | Resampling strategy; default `kfold`, options below |
| `n_splits` | integer | No | At least `2`; default `5`, ignored by `leave_one_out` |
| `n_repeats` | integer | No | At least `1`; default `1`, only for `repeated_kfold` |
| `test_size` | number | No | Strictly between `0` and `1`; default `0.2`, only for shuffle-split strategies |
| `shuffle` | boolean | No | Default `true`; controls K-Fold and Stratified K-Fold shuffling |
| `group_column` | string | For Group K-Fold | Existing column whose values keep related rows together |
| `scoring` | string[] | No | Empty or omitted uses task defaults; allowed metrics below |
| `seed` | integer | Yes | Required even for deterministic strategies; editor default `42` |

| Strategy value | Use |
| --- | --- |
| `kfold` | Divide rows into K held-out folds |
| `stratified_kfold` | Preserve classification label proportions per fold |
| `shuffle_split` | Repeated random train/test splits |
| `stratified_shuffle_split` | Random splits that preserve classification label proportions |
| `group_kfold` | Keep rows with the same group value in one fold |
| `time_series_split` | Ordered rows: train on earlier observations, test on later ones |
| `repeated_kfold` | Repeat K-Fold with fresh shuffled splits |
| `leave_one_out` | Hold out each row in turn; one fit per row |

Classification metrics: `accuracy`, `balanced_accuracy`, `f1_weighted`,
`f1_macro`, `precision_weighted`, `recall_weighted`, `roc_auc`.
Regression metrics: `r2`, `neg_root_mean_squared_error`, `neg_mean_absolute_error`,
`neg_mean_squared_error`, `neg_mean_absolute_percentage_error`.

Negative scikit-learn loss scores are negated and renamed for the output:
`neg_mean_absolute_error` becomes positive `mean_absolute_error`, for example.
The `scoring` configuration still uses the original `neg_` name.

At least ten rows are required. Fold count cannot exceed row count for fold
strategies; stratification also needs enough rows per class. Only classification
models can use stratified strategies. Group K-Fold needs enough distinct groups.
The target must exist and cannot be a feature; configured training-row and
feature-count limits also apply.

## Generated Python code

Download the [customer sample CSV](/samples/ml-classification/customers.csv)
and save it as `customers.csv` in the directory where you run the script.
The flow sends this dataset to both Classifier Model and Cross-Validate, wires
the definition's `model` output into Cross-Validate, and saves
`cross-validate-scores.csv` with File Output.

The definition uses logistic regression to predict `churn` from `tenure`,
`monthly_charges` and `support_calls`. It explicitly applies median imputation
and robust scaling to those numeric features within each fold. The evaluation
configuration is:

```json
{
  "cv_strategy": "stratified_kfold",
  "n_splits": 2,
  "shuffle": true,
  "seed": 42
}
```

The output has two rows: `fold`, `accuracy`, `f1_weighted`, `fit_time_s`. Both
score columns are `1.0` on this tiny illustrative sample; this does not measure
performance on real customer data. Fit times change with each run.

Both flow engines run ML through pandas/scikit-learn. Run these actual complete
exports in an environment with Ciaren installed: the registered model builder
is imported from `app.ml.models`. No final model is persisted.

### pandas

```python
import pandas as pd
import json
from app.ml.models import build_estimator
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

df_customers = pd.read_csv('customers.csv')
_model_config = {'model_type': 'logistic_regression', 'target_column': 'churn', 'feature_columns': ['tenure', 'monthly_charges', 'support_calls'], 'hyperparameters': None, 'preprocessing': {'numeric_columns': ['tenure', 'monthly_charges', 'support_calls'], 'numeric_strategy': 'robust_scaler'}, 'seed': 42}
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
_cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=42)
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
df_2.to_csv('cross-validate-scores.csv', index=False)
```

### Polars

```python
import polars as pl
import json
import pandas as pd
from app.ml.models import build_estimator
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

df_customers = pl.read_csv('customers.csv')
_eager_1 = df_customers.to_pandas()
_model_config = {'model_type': 'logistic_regression', 'target_column': 'churn', 'feature_columns': ['tenure', 'monthly_charges', 'support_calls'], 'hyperparameters': None, 'preprocessing': {'numeric_columns': ['tenure', 'monthly_charges', 'support_calls'], 'numeric_strategy': 'robust_scaler'}, 'seed': 42}
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
_cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=42)
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
df_1.write_csv('cross-validate-scores.csv')
```

## Tips and common mistakes

- Connect the definition's purple model wire and the data wire separately.
  Train Classifier/Regressor outputs are intentionally rejected.
- Keep rows in time order for Time Series Split. Group K-Fold is useful for
  repeated observations of one customer; exclude the group ID from features
  when it should not be a predictor.
- Configure learned preprocessing in the model definition. Fitting a standalone
  scaler on all data before cross-validation leaks held-out information.
- Select metrics for the model's task. ROC AUC requires an estimator with a
  compatible probability or decision-function output and suitable class labels.
- Leave-One-Out fits as many estimators as there are rows. Use it for small
  datasets; K-Fold is usually cheaper.
- After choosing the model, use a Train node to fit the final artifact. This
  node's scores cannot feed Predict's model input.

## See also

- [Classifier Model](./classifier-model.md)
- [Regressor Model](./regressor-model.md)
- [Train/Test Split](./train-test-split.md)
- [Machine Learning nodes](./machine-learning.md)
- [ML Quick Start](../guide/ml-quickstart.md#add-cross-validation)
