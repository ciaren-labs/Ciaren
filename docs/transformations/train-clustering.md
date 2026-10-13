---
title: "Train and Save Clustering Models"
description: "Fit clustering models in Ciaren and save them to MLflow. Learn model wires, K-Means predictions, training metrics, and runnable pandas or Polars exports."
---

# Train Clustering — `mlTrainClustering`

Fit and save an unsupervised clustering model.

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

Built-in model types are `kmeans`, `dbscan` and `agglomerative`. They train
without a target. K-Means exposes `predict` and can score new rows through
[Predict](./predict.md). DBSCAN and Agglomerative Clustering do not expose that
method; their saved models cannot be used with the current Predict node.
This Train node returns a model reference, not a frame of cluster labels.

Training metadata includes `inertia` when the estimator exposes it and
`silhouette` when the clustering label-count guard permits it. Silhouette is
calculated on the fitted preprocessing output. All-noise DBSCAN results warn
and omit silhouette. These are training diagnostics rather than held-out scores.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `model_type` | string | Yes | This task's algorithm; editor default `kmeans` |
| `feature_columns` | string[] | No | Default `[]`; explicitly select predictors to exclude IDs and unrelated labels |
| `hyperparameters` | object | No | Default `{}`; estimator options, with host bounds and constructor validation |
| `preprocessing` | object | No | Default omitted; infer numeric and categorical features, or supply explicit lists |
| `seed` | integer | Yes | Editor default `42`; builders with a random-state option use it unless a hyperparameter overrides it |
| `mlflow_experiment` | string | No | Experiment name; omitted or blank uses `ciaren` |

Omitted or empty features select every input column. There is no automatic
target or ID exclusion: pin meaningful numeric features rather than including
customer IDs or known labels such as `churn`.

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

The example fits K-Means with `n_clusters=2` on `tenure`, `monthly_charges`
and `support_calls`. Only the 12 training rows fit the scaler and clusters.
Wire the model and four held-out rows into Predict with `output_column="cluster"`.
The output `train-clustering.csv` contains customers `1, 2, 6, 15` with cluster
IDs `0, 1, 1, 0`. Cluster IDs are arbitrary identifiers, not an ordered scale.

The Train configuration is:

```json
{
  "model_type": "kmeans",
  "feature_columns": [
    "tenure",
    "monthly_charges",
    "support_calls"
  ],
  "hyperparameters": {
    "n_clusters": 2
  },
  "seed": 42
}
```

### pandas

```python
import pandas as pd
import joblib
import mlflow.sklearn
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
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
df_3 = Pipeline([('preprocessor', _preprocessor), ('model', KMeans(n_clusters=2, random_state=42))])
df_3.fit(_X)
df_4 = df_2.copy()
_model_features = list(getattr(df_3, 'feature_names_in_', df_2.columns))
df_4['cluster'] = df_3.predict(df_2[_model_features])
df_4.to_csv('train-clustering.csv', index=False)
```

### polars

```python
import polars as pl
import joblib
import mlflow.sklearn
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
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
_eager_5 = Pipeline([('preprocessor', _preprocessor), ('model', KMeans(n_clusters=2, random_state=42))])
_eager_5.fit(_X)
_eager_6 = df_2.to_pandas()
_eager_7 = _eager_6.copy()
_model_features = list(getattr(_eager_5, 'feature_names_in_', _eager_6.columns))
_eager_7['cluster'] = _eager_5.predict(_eager_6[_model_features])
df_3 = pl.from_pandas(_eager_7)
df_3.write_csv('train-clustering.csv')
```

## Tips and common mistakes

- Select features explicitly. An ID or existing label changes the distances
  used by the model if you include it as a predictor.
- Adjust cluster count, scaling and features together; a training silhouette
  alone does not validate that the groups are useful.
- Do not wire DBSCAN or Agglomerative models into Predict. Their estimators
  lack a method for assigning these saved clusters to new rows.
- Feature Importance requires tree importance or linear coefficients;
  these clustering estimators do not provide them.

## See also

- [Predict](./predict.md)
- [Evaluate](./evaluate.md)
- [Scale Features](./scale-features.md)
- [Train/Test Split](./train-test-split.md)
- [ML quick start](../guide/ml-quickstart.md)
