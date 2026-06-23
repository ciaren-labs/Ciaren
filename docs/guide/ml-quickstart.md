---
title: Machine Learning Quick Start
description: Train, evaluate, and use a model visually with FlowFrame's ML nodes.
search: machine learning ml train model predict mlflow scikit-learn
layout: doc
---

# Machine Learning Quick Start

FlowFrame's optional ML extension adds nodes for the full tabular ML lifecycle —
clean → engineer features → split → train → evaluate → predict — on the same
drag-and-drop canvas. Models are tracked with [MLflow](https://mlflow.org).

This guide builds a churn classifier in about 10 minutes.

## Prerequisites

The ML nodes only appear when the extension is **installed and enabled**:

```bash
pip install "flowframe[ml]"     # scikit-learn, xgboost, lightgbm, mlflow, joblib
```

`flowframe init` provisions a local MLflow store (`./mlruns`) and enables ML by
default. To point at an existing MLflow server instead, set:

```bash
FLOWFRAME_MLFLOW_TRACKING_URI=http://your-mlflow:5000   # or sqlite:///./mlflow.db
```

Check it's ready with `flowframe check` — you should see `ml: ok`. When ML is
off or the extra isn't installed, the **Machine Learning** palette section is
simply hidden.

## The nodes

Open a flow and expand **Machine Learning** in the node palette:

| Node | What it does |
|---|---|
| **Train / Test Split** | Splits rows into `train` and `test` outputs (seed required). |
| **Scale Features** | Standardize / normalize numeric columns. |
| **Encode Categories** | One-hot or ordinal encoding for text columns. |
| **Impute Missing** | Fill gaps (mean/median/most-frequent/constant/KNN). |
| **Select Features** | Keep the most useful columns (variance / correlation / top-K). |
| **Reduce Dimensions** | Compress numeric columns with PCA. |
| **Train Model** | Fit a model and log it to MLflow. |
| **Predict** | Score rows with a trained model. |
| **Evaluate** | Compute metrics from predictions. |
| **Feature Importance** | Rank which features the model relied on. |

## Build the flow

1. **Input** — drag a **CSV Input** and pick your dataset (it needs a target
   column, e.g. `churn`).
2. **Train / Test Split** — connect the input. Set a **seed** (required for
   reproducibility) and, for classification, stratify on your target.
3. **Train Model** — connect the split's **train** output.
   - Pick a **Model** (grouped by task). Random Forest is a solid default.
   - Choose the **Target column** (`churn`). Leave **Feature columns** empty to
     use every other column.
   - Tweak basic hyperparameters inline, or open **Advanced options** for the
     full set, cross-validation, and preprocessing.
4. **Predict** — connect the split's **test** output to its data input, and the
   Train Model's **model** output (the purple wire) to its model input.
5. **Evaluate** — connect Predict. Set the task type and the prediction column
   (`prediction`); choose metrics or accept the defaults.
6. **Output** — connect a **CSV Output** to Evaluate to save the metrics table.

::: tip Multi-output nodes
Train / Test Split has two outputs (`train`, `test`) and Train Model has two
(`out`, `model`). Drag from the specific handle you need. The **purple** wire is
a model reference; blue wires are data.
:::

## Run it and read the results

Run the flow, then open the run. Click the **Train Model** node to see its
**Machine learning** panel:

- training metrics and cross-validation folds,
- a confusion-matrix heatmap (classification),
- the model URI and MLflow run id,
- a **Register in registry** button to promote the model (name + optional stage).

Click the **Evaluate** node for the held-out test metrics, and **Feature
Importance** (wire it to the model output) for an importance bar chart.

## Use a registered model in production

Once a model is registered, a **Predict** node can reference it directly instead
of a wired model — set its **Model URI** to e.g. `models:/churn/Production`.
Re-promoting a new version in MLflow means scheduled prediction flows pick it up
automatically, no flow edits needed.

## Reproducibility & safety

- Every training run records its seed, the graph snapshot, and the dataset
  versions it read, and tags the MLflow run with back-pointers.
- Models are loaded only from MLflow URIs or the artifact directory; pickle files
  are rejected. Hyperparameters are never executed as code.
- A dataset can't be deleted while a **Production** model was trained on it
  (override with care).

## Next steps

- [ML node reference](../transformations/machine-learning.md)
- [Scheduling](./scheduling.md) — retrain on a cron schedule.
- [Engines](./engines.md) — ML steps run on numpy; the rest of the flow keeps
  its chosen engine.
