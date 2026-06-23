---
title: Machine Learning Nodes
description: Reference for FlowFrame's ML nodes — split, feature engineering, train, predict, evaluate.
search: ml machine learning train predict evaluate split scale encode pca feature importance
layout: doc
---

# Machine Learning Nodes

These nodes appear under **Machine Learning** in the palette when the ML
extension is installed (`pip install "flowframe[ml]"`) and enabled. See the
[ML Quick Start](../guide/ml-quickstart.md) for an end-to-end walkthrough.

All ML nodes run on scikit-learn (with optional XGBoost / LightGBM) and convert
to pandas at the model boundary, so they work whether the flow's engine is polars
or pandas.

## Train / Test Split

Splits incoming rows into a training set and a test set. **Two outputs:** `train`
and `test` — wire each to the right place.

| Field | Type | Notes |
|---|---|---|
| Test size | number (0–1) | Fraction held out for testing. |
| Stratify by | column | Optional. Preserves class balance across splits. |
| Random seed | integer | **Required** — the same seed reproduces the split. |

## Feature engineering

These transform features for exploration/preview. For training, prefer the
**Preprocessing** section inside Train Model's Advanced options — it bundles the
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
works on both engines. For training, Train Model's Advanced → Preprocessing also
imputes inside the model pipeline so the same fill is applied at predict time.

## Train Model

Fits a model and logs it to MLflow. **Two outputs:** `out` (the training data,
passed through) and `model` (a model reference — the purple wire).

**Basic config:** model (grouped by task), target column (supervised models),
feature columns (empty = all but the target), the model's common hyperparameters,
and the required seed.

**Advanced options** (modal): the full hyperparameter set, k-fold cross-validation,
preprocessing (numeric scaling + imputation, categorical imputation + one-hot),
and the MLflow experiment name.

Supported models:

| Task | Models |
|---|---|
| Classification | Logistic Regression, Random Forest, XGBoost, LightGBM, SVM, KNN |
| Regression | Linear, Ridge, Lasso, Random Forest, SVR, XGBoost, LightGBM |
| Clustering | K-Means, DBSCAN, Agglomerative |
| Dimensionality reduction | PCA (fit) |

Guardrails: the seed is required, the target can't also be a feature (leakage),
and row/feature/model-size limits are enforced before training starts.

## Predict

Scores rows with a trained model, adding a prediction column.

| Field | Notes |
|---|---|
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

Takes a Train Model **model** output and returns `feature_name` / `importance` /
`rank`. Works for tree-based and linear models; SVM (non-linear) and KNN are not
supported.

## See also

- [ML Quick Start](../guide/ml-quickstart.md)
- [Scheduling](../guide/scheduling.md) — periodic retraining
- [All transformations](./overview.md)
