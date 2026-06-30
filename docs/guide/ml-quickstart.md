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
default. To point at an existing MLflow server, either set the env var:

```bash
FLOWFRAME_MLFLOW_TRACKING_URI=http://your-mlflow:5000   # or sqlite:///./mlflow.db
```

…or edit the built-in **Local MLflow** connection in the **Connections** page
(see below) — the connection is the source of truth and overrides the env var.

Check it's ready with `flowframe check` — you should see `ml: ok`. When ML is
off or the extra isn't installed, the **Machine Learning** palette section is
simply hidden.

### The MLflow connection

When ML is enabled, FlowFrame seeds a **Local MLflow** connection (under
**Connections → Experiment tracking**) pointing at `./mlruns`. It works just
like the Local Storage connection: click **Test connection** to verify the
tracking store is reachable, or edit its **Tracking URI** to point at a remote
server (`http://host:5000`), a SQLite store (`sqlite:///mlflow.db`), or another
folder. Every training run and the **ML Models** page read the tracking URI from
this connection, so changing it re-points MLflow everywhere — no restart needed.

## ML pipeline at a glance

<FlowPipeline
  :nodes='[
    {"type":"input","label":"CSV Input","detail":"churn dataset"},
    {"type":"ml","label":"Train / Test Split","detail":"seed + stratify"},
    {"type":"ml","label":"Scale Features","detail":"normalize numeric cols"},
    {"type":"ml","label":"Train Classifier","detail":"Random Forest → MLflow"},
    {"type":"ml","label":"Predict","detail":"test output + model wire"},
    {"type":"ml","label":"Evaluate","detail":"accuracy, AUC, F1"},
    {"type":"output","label":"File Output","detail":"save metrics"}
  ]'
/>

:::tip Purple model wire
**Train/Test Split** has two output handles: `train` and `test`. The train handle
feeds **Scale Features** and then **Train Classifier**. The test handle feeds the data
input of **Predict** directly. **Train Classifier** has a second output — the **model**
handle — which connects via a purple wire to **Predict**'s model input.
:::

## The nodes

Open a flow and expand **Machine Learning** in the node palette:

| Node | What it does |
| --- | --- |
| **Train / Test Split** | Splits rows into `train` and `test` outputs (seed required). |
| **Scale Features** | Standardize / normalize numeric columns. |
| **Encode Categories** | One-hot or ordinal encoding for text columns. |
| **Select Features** | Keep the most useful columns (variance / correlation / top-K). |
| **Reduce Dimensions** | Compress numeric columns with PCA. |
| **Classifier / Regressor Model** | Define an unfitted model for Cross-Validate. |
| **Train Classifier** | Fit a model and log it to MLflow. |
| **Predict** | Score rows with a trained model. |
| **Evaluate** | Compute metrics from predictions. |
| **Feature Importance** | Rank which features the model relied on. |
| **Cross-Validate** | Estimate generalization for a connected model with k-fold, stratified, time-series, group, or other CV strategies. |

## Build the flow

1. **Input** — drag a **CSV Input** and pick your dataset (it needs a target
   column, e.g. `churn`).
2. **Train / Test Split** — connect the input. Set a **seed** (required for
   reproducibility) and, for classification, stratify on your target.
3. **Train Classifier** — connect the split's **train** output.
   - Pick a **Model** (grouped by task). Random Forest is a solid default.
   - Choose the **Target column** (`churn`). Leave **Feature columns** empty to
     use every other column.
   - Tweak basic hyperparameters inline, or open **Advanced options** for the
     full set, tracking, and preprocessing.
4. **Predict** — connect the split's **test** output to its data input, and the
   Train Classifier's **model** output (the purple wire) to its model input.
5. **Evaluate** — connect Predict. Set the task type and the prediction column
   (`prediction`); choose metrics or accept the defaults.
6. **Output** — connect a **File Output** to Evaluate to save the metrics table.

::: tip Multi-output nodes
Train / Test Split has two outputs (`train`, `test`). Train Classifier emits a
`model` output. Drag from the specific handle you need. The **purple** wire is a
model reference; blue wires are data.
:::

## Run it and read the results

Run the flow, then open the run. The run detail page shows the full DAG with green checkmarks on every node and row counts at each step:

![Run detail for an ML flow — csvInput, scaleFeatures, trainTestSplit, mlTrainClassifier, featureImportance, mlPredict, mlEvaluate, and two csvOutput nodes all succeeded](/screenshots/run-detail.png)

Click the **Train Classifier** node to see its **Machine learning** panel:

- training metrics,
- a confusion-matrix heatmap (classification),
- the model URI and MLflow run id,
- a **Register in registry** button to promote the model (name + optional stage).

Click the **Evaluate** node for the held-out test metrics, and **Feature
Importance** (wire it to the model output) for an importance bar chart.

## Use a registered model in production

Once a model is registered, a **Predict** node can reference it directly instead
of a wired model — set its **Model URI** to the alias shown in the Register dialog,
e.g. `models:/churn@production` (MLflow 3 uses `@alias`, not the old `/Stage`
syntax), or a specific version like `models:/churn/1`. Re-pointing the alias to a
new version in MLflow means scheduled prediction flows pick it up automatically,
no flow edits needed.

## Browse your models

The **Models** page (in the top nav, shown only when ML is enabled) is a
dedicated view over everything MLflow tracked:

![ML Models page — registered models with version cards, key metrics, production/staging aliases, and Flow+Run lineage links](/screenshots/models.png)

- **Registered Models** — every registered model with its versions, aliases
  (e.g. `@production`), key metrics, and **lineage links back to the FlowFrame
  flow and run** that produced each version.
- **Experiments** — a leaderboard of training runs per experiment, with the
  best value in each metric column highlighted (RMSE/MAE treated as
  lower-is-better) so you can compare runs at a glance:

![ML Models → Experiments tab — leaderboard of training runs ranked by metric, with the champion run highlighted by a trophy icon](/screenshots/models-experiments.png)

## Try the demo flows

When the `[ml]` extra is installed, the built-in **Demo** project includes four
ready-to-run ML flows: *Iris — Quick Classifier*, *Iris — Train, Validate &
Evaluate*, *House Prices — Regression*, and *Iris — PCA Explore*. Boot with
`flowframe serve --run-seed-flows` to run them all once on first start, so the
Runs history and the Models page are populated out of the box.

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
