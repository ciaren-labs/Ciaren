---
title: "Fit and Save PCA Models with MLflow"
description: "Fit a PCA model in Ciaren and save its preprocessing to MLflow. Learn model references, explained variance, limits, and runnable pandas or Polars exports."
---

# Train Dim. Reduction — `mlTrainDimReduction`

Fit PCA as a saved model rather than producing a components table.

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

The built-in model type is `pca_fit`. Its fitted preprocessing and PCA are
saved together. This node returns the model reference; it does not add
component columns to the incoming frame. For an immediate components table,
use [Reduce Dimensions](./reduce-dimensions.md), which fits on its incoming
frame without saving a model artifact.

Training metadata contains `explained_variance`, the sum of the fitted PCA
explained-variance ratios. It describes variation retained in the preprocessed
training features and is not a predictive-quality score.

PCA exposes `transform`, not `predict`; the current Predict and Feature
Importance nodes do not consume this artifact. A trusted sklearn loader can
load the saved pipeline for use with `transform` in Python. MLflow may warn
that a PCA model lacks a prediction signature or `python_function` flavor;
the sklearn artifact can still be saved and loaded successfully.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `model_type` | string | Yes | This task's algorithm; editor default `pca_fit` |
| `feature_columns` | string[] | No | Default `[]`; explicitly select predictors to exclude IDs and unrelated labels |
| `hyperparameters` | object | No | Default `{}`; estimator options, with host bounds and constructor validation |
| `preprocessing` | object | No | Default omitted; infer numeric and categorical features, or supply explicit lists |
| `seed` | integer | Yes | Editor default `42`; builders with a random-state option use it unless a hyperparameter overrides it |
| `mlflow_experiment` | string | No | Experiment name; omitted or blank uses `ciaren` |

Omitted or empty features select every input column. Pin the intended
features and exclude IDs and known labels yourself. `n_components` belongs
in `hyperparameters`; choose a value compatible with the fitted feature width
and training-row count.

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

The example fits two components on `tenure`, `monthly_charges` and
`support_calls`, using only 12 training rows. On a parallel branch, File Output
writes the four unchanged held-out rows to `train-dim-reduction.csv`. That CSV
is a data passthrough, not PCA coordinates. The fitted pipeline remains in
`df_3` in the pandas script and `_eager_5` in the Polars script.

To apply the fitted model in your own Python workflow, call that pipeline's
`transform` with the same ordered feature columns. Do not call `fit_transform`
on new rows, which fits a new PCA. This sample retains approximately
`0.985583` of the preprocessed training variance; the full generator exports
below do not append transformations or persistence steps.

The Train configuration is:

```json
{
  "model_type": "pca_fit",
  "feature_columns": [
    "tenure",
    "monthly_charges",
    "support_calls"
  ],
  "hyperparameters": {
    "n_components": 2
  },
  "seed": 42
}
```

### pandas

```python
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler

df_customers = pd.read_csv('customers.csv')
df_1, df_2 = train_test_split(df_customers, test_size=0.25, random_state=42)
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
df_3 = Pipeline([('preprocessor', _preprocessor), ('model', PCA(n_components=2, random_state=42))])
df_3.fit(_X)
df_2.to_csv('train-dim-reduction.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
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
_eager_5 = Pipeline([('preprocessor', _preprocessor), ('model', PCA(n_components=2, random_state=42))])
_eager_5.fit(_X)
df_2.write_csv('train-dim-reduction.csv')
```

## Tips and common mistakes

- Choose Train Dim. Reduction when you need a reusable saved PCA pipeline;
  choose Reduce Dimensions when you need transformed rows in the flow.
- PCA does not produce predictions or tree/linear importance. A model wire
  alone does not make it compatible with Predict or Feature Importance.
- Explain variance in relation to the scaled/encoded features actually fitted,
  rather than treating it as a percentage of prediction accuracy.
- The sample CSV intentionally contains the held-out input unchanged.
  Training and transformation are separate operations.

## See also

- [Reduce Dimensions](./reduce-dimensions.md)
- [Scale Features](./scale-features.md)
- [Select Features](./select-features.md)
- [Train/Test Split](./train-test-split.md)
- [ML quick start](../guide/ml-quickstart.md)
