---
title: Machine Learning Nodes
description: Choose among Ciaren's 16 ML nodes for preparation, training, predictions and evaluation. Find configuration, model-wire guidance and pandas or Polars examples.
search: ml machine learning train predict evaluate split scale encode pca feature importance
layout: doc
---

# Machine Learning Nodes

Choose a node below for its configuration, limits and complete examples. The
[ML quick start](../guide/ml-quickstart.md) walks through a held-out classification
flow. A standard Ciaren installation includes scikit-learn and MLflow; optional
XGBoost and LightGBM models need `pip install "ciaren[ml]"`.

ML operations cross into pandas/scikit-learn even in Polars flows. Train nodes
save fitted models to MLflow at runtime; exports fit pipelines in memory without
logging or saving them. Model definitions stay unfitted for cross-validation.

## What Evaluate produces

[Evaluate](./evaluate.md) turns scored rows into a `metric` / `value` table,
one row per computed scalar. Training-node metadata contains training scores;
use held-out predictions or cross-validation to estimate generalization.

## Train / Test Split

[Train/Test Split](./train-test-split.md) has separate `train` and `test` outputs.
Fit on `train`, then connect `test` and the trained model wire to Predict.

## Feature engineering

| Node | Use |
| --- | --- |
| [Scale Features](./scale-features.md) | Scale selected numeric columns |
| [Encode Categories](./encode-categories.md) | Encode categories into numeric features |
| [Select Features](./select-features.md) | Select columns with a supported feature-selection method |
| [Reduce Dimensions](./reduce-dimensions.md) | Fit PCA on incoming rows and output components |

These standalone nodes fit on each incoming frame. To carry the same learned
imputation/scaling/encoding from training to prediction, configure preprocessing
inside a Train node instead of fitting separate transformers on the test branch.

## Train nodes

| Node | Task and availability |
| --- | --- |
| [Train Classifier](./train-classifier.md) | Fit a classification model and save its artifact |
| [Train Regressor](./train-regressor.md) | Fit a regression model and save its artifact |
| [Train Clustering](./train-clustering.md) | Fit K-Means, DBSCAN or Agglomerative Clustering |
| [Train Dim. Reduction](./train-dim-reduction.md) | Save a fitted PCA pipeline; does not output components |
| [Train Forecaster](./train-forecaster.md) | Scaffold; no built-in forecasting estimator |

Each implemented Train node emits one `model` reference containing the saved
artifact URI, not data rows. Predict requires an estimator with `predict`:
PCA, DBSCAN and Agglomerative Clustering do not support that consumer. Feature
Importance requires tree importance or linear coefficients.

Runtime validates row/feature limits before fitting and serialized model size
after fitting, before saving. Preview does not fit or create an MLflow run.
Load only trusted model artifacts; URI/path checks do not sandbox model code.

## Model definition nodes

[Classifier Model](./classifier-model.md) and [Regressor Model](./regressor-model.md)
emit unfitted definitions for Cross-Validate. They do not save final artifacts.
Use a Train node afterward when you need a model for supported consumers.

## Predict

[Predict](./predict.md) accepts rows and a trained model wire or explicit URI.
It adds predictions and optional class probabilities, with configurable batches
for prediction calls. Expected features are aligned when model/reference names
are available; nameless external models need caller-selected columns.

## Evaluate

[Evaluate](./evaluate.md) computes classification, regression or clustering
metrics from scored data. Its reference explains probability requirements,
undefined scores and metrics omitted from exports.

## Feature Importance

[Feature Importance](./feature-importance.md) ranks supported trained-model
features. It does not train a model or establish causal importance.

## Cross-Validate

[Cross-Validate](./cross-validate.md) fits fresh classifier/regressor pipelines
within folds using an unfitted definition. It returns fold scores and fit times,
not a saved final model. Preprocessing is refitted inside each fold.

## See also

- [ML quick start](../guide/ml-quickstart.md)
- [ML model plugins](/plugins/ml-model-plugins)
- [Troubleshooting](../guide/troubleshooting.md)
