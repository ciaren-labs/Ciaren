---
title: Machine Learning Nodes
description: Reference for Ciaren's ML nodes — split, feature engineering, train, predict, evaluate.
search: ml machine learning train predict evaluate split scale encode pca feature importance
layout: doc
---

# Machine Learning Nodes

These nodes appear under **Machine Learning** in the palette by default — a
plain `pip install ciaren` already includes scikit-learn and MLflow. See the
[ML Quick Start](../guide/ml-quickstart.md) for an end-to-end walkthrough.

All ML nodes run on scikit-learn (with optional XGBoost / LightGBM via
`pip install "ciaren[ml]"`) and convert to pandas at the model boundary, so
they work whether the flow's engine is polars or pandas.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"CSV Input","detail":"dataset with target"},
    {"type":"ml","label":"Train / Test Split","detail":"seed + stratify"},
    {"type":"ml","label":"Scale Features","detail":"normalize numerics"},
    {"type":"ml","label":"Train Classifier","detail":"model → MLflow"},
    {"type":"ml","label":"Predict","detail":"test data + model wire"},
    {"type":"ml","label":"Evaluate","detail":"accuracy · AUC · F1"},
    {"type":"output","label":"File Output","detail":"metrics table"}
  ]'
/>

## What Evaluate produces

<DataTransform
  transform="Evaluate (task=classification, prediction_column=prediction)"
  :before='{
    "columns":["customer_id","churn","prediction"],
    "rows":[[1,1,1],[2,0,0],[3,0,1]]
  }'
  :after='{
    "columns":["metric","value"],
    "rows":[["accuracy",0.6667],["precision",0.5],["recall",1.0],["f1",0.6667]]
  }'
/>

## Train / Test Split

Splits incoming rows into a training set and a test set. **Two outputs:** `train`
and `test` — wire each to the right place.

| Field | Type | Notes |
| --- | --- | --- |
| Test size | number (0–1) | Fraction held out for testing. |
| Stratify by | column | Optional. Preserves class balance across splits. |
| Random seed | integer | **Required** — the same seed reproduces the split. |

## Feature engineering

These transform features for exploration/preview. For training, prefer the
**Preprocessing** section inside a train node's Advanced options — it bundles the
same steps into the model so they're reapplied identically at predict time.

- **Scale Features** — `standard` (z-score), `minmax` (0–1), or `robust`
  (median/IQR) over chosen numeric columns.
- **Encode Categories** — `onehot` (dummy columns, optional drop-first) or
  `ordinal` (integer codes).
- **Select Features** — `variance` threshold, `correlation` filter, or `kbest`
  (top-K by relevance to a target).
- **Reduce Dimensions** — PCA; keep a number of components or a variance
  fraction. Chosen columns are replaced by `pc_1`, `pc_2`, ….

To fill missing values, use the standard **[Fill Nulls](./fill-nulls.md)**
cleaning node (mean / median / mode / constant / forward- / backward-fill) — it
works on both engines. For training, a train node's Advanced → Preprocessing also
imputes inside the model pipeline so the same fill is applied at predict time.

## Train nodes

Training is split into one node per task, so each model picker only shows
relevant algorithms: **Train Classifier**, **Train Regressor**, **Train
Clustering**, **Train Dim. Reduction**, and **Train Forecaster** (time-series —
defined as a scaffold; models coming soon). They all fit a model and log it to
MLflow, and each emits a single `model` output (the purple wire) — wire it into
**Predict** or **Feature Importance**.

**Basic config:** model (scoped to the node's task), target column (supervised
nodes), feature columns (empty = all but the target), the model's common
hyperparameters, and the required seed.

**Advanced options** (modal): the full hyperparameter set, preprocessing
(numeric scaling + imputation, categorical imputation + one-hot), and the MLflow
experiment name. Use the dedicated **Cross-Validate** node when you want fold
scores without first training a final model on the full dataset.

Supported models:

| Node | Task | Models |
| --- | --- | --- |
| Train Classifier | Classification | Logistic Regression, Random Forest, XGBoost, LightGBM, SVM, KNN |
| Train Regressor | Regression | Linear, Ridge, Lasso, Random Forest, SVR, XGBoost, LightGBM |
| Train Clustering | Clustering | K-Means, DBSCAN, Agglomerative |
| Train Dim. Reduction | Dimensionality reduction | PCA (fit) |
| Train Forecaster | Time series | _(coming soon)_ |

Guardrails: the seed is required, the target can't also be a feature (leakage),
and row/feature/model-size limits are enforced before training starts.

## Model definition nodes

**Classifier Model** and **Regressor Model** configure an estimator without
fitting it, logging it, registering it, or producing predictions. Their `model`
output is a **model configuration reference**: it carries the algorithm, target,
feature columns, hyperparameters, and preprocessing recipe that another node can
use later.

Use these nodes with **Cross-Validate**. Cross-validation needs to fit one fresh
clone of the estimator per fold, with preprocessing refit inside each fold. If a
flow used a Train node as the input to Cross-Validate, it would first train a
final full-data model and then train the fold models too. Ciaren avoids that
ambiguous and wasteful pattern by accepting only **Classifier Model** or
**Regressor Model** on Cross-Validate's `model` input.

Use the nodes this way:

| Goal | Use | Why |
| --- | --- | --- |
| Estimate generalization or compare settings | **Classifier/Regressor Model → Cross-Validate** | Cross-Validate owns the fold fitting loop and returns fold scores. |
| Produce the final artifact for scoring or registration | **Train Classifier/Regressor → Predict / Feature Importance / Register Model** | Train nodes fit once on their input data and log the trained model to MLflow. |
| Do both evaluation and deployment | First evaluate with **Model → Cross-Validate**, then train the chosen setup with **Train** | Keeps evaluation separate from the final artifact so users know exactly what was fitted. |

## Predict

Scores rows with a trained model, adding a prediction column.

| Field | Notes |
| --- | --- |
| Model URI | Optional. By alias `models:/churn@production` or version `models:/churn/1` (MLflow 3 uses `@alias`, not `/Stage`). Leave empty to use the wired model. |
| Prediction column | Name of the new output column (default `prediction`). |
| Probability columns | Optional, classifiers — one name per class. |

The input columns are matched to the model's expected features (missing features
error; extra columns are dropped).

## Evaluate

Computes metrics from predictions and returns a long-format `metric` / `value`
table.

- **Classification:** accuracy, precision, recall, f1, ROC-AUC (needs probability
  columns), confusion matrix.
- **Regression:** RMSE, MAE, R², MAPE, residual std.
- **Clustering:** silhouette, Davies-Bouldin.

## Feature Importance

Takes a train node's **model** output and returns `feature_name` / `importance` /
`rank`. Works for tree-based and linear models; SVM (non-linear) and KNN are not
supported.

## Cross-Validate

Estimates how well a connected classifier or regressor **generalizes** by
re-fitting and scoring it across resampling folds, rather than reporting a single
train score. It takes a **Classifier Model** or **Regressor Model** node's
`model` output, reuses that model definition's algorithm, target, feature
columns, hyperparameters, and preprocessing, and does not persist a final model.
It returns a tidy `fold | <metric> …` frame (one row per fold) and surfaces the
per-fold scores plus the mean/std on the run's ML view. Preprocessing from the
connected model definition is refit **inside each fold**, so the scores aren't
inflated by leakage.

It has two inputs: `in` for the data to resample and `model` for a Classifier
Model or Regressor Model reference. It is a valid flow terminal on its
own (no output node required), or you can wire its scores frame onward to an
output.

| Field | Notes |
| --- | --- |
| Model input | Connect the `model` output from Classifier Model or Regressor Model. Train Classifier and Train Regressor outputs are intentionally rejected. |
| Strategy | The resampling scheme (see below). |
| Folds / Splits | How many folds to evaluate (ignored by Leave-One-Out). |
| Test size | For Shuffle Split strategies — fraction held out each split. |
| Repeats | For Repeated K-Fold — how many times to repeat with a fresh shuffle. |
| Group column | For Group K-Fold — rows sharing a value stay in one fold. |
| Scoring | Optional. Empty uses a sensible default set for the task. |
| Random seed | Required — reproduces the same folds every run. |

Strategies:

| Strategy | When to use |
| --- | --- |
| K-Fold | The default — split rows into k equal folds. |
| Stratified K-Fold | Classification with imbalanced classes (preserves class balance per fold). |
| Shuffle Split | Repeated random train/test splits (control the held-out fraction). |
| Stratified Shuffle Split | Shuffle Split that preserves class balance. |
| Group K-Fold | Keep all rows of a group together (no leakage across groups). |
| Time Series Split | Ordered data — train on the past, test on the future. |
| Repeated K-Fold | K-Fold repeated several times for a more stable estimate. |
| Leave-One-Out | Each row is its own test fold — small datasets only. |

Default scoring is accuracy + weighted F1 (classification) and R² + RMSE
(regression). `neg_*` sklearn scores (RMSE, MAE, …) are negated and renamed in
the report so they read as positive, lower-is-better numbers.

Guardrails: the seed is required, the target can't also be a feature (leakage),
stratified strategies require a classification model, Group K-Fold requires a
group column, and the fold count can't exceed the row count.

## See also

- [ML Quick Start](../guide/ml-quickstart.md)
- [Scheduling](../guide/scheduling.md) — periodic retraining
- [All transformations](./overview.md)
