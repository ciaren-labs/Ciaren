# FlowFrame ML Extension — Architecture & Implementation Guide

**Status:** Design phase — under development
**Scope:** Supervised and unsupervised tabular ML (scikit-learn, XGBoost, LightGBM)  
**Depends on:** MLflow 3 (artifact store + registry), existing ETL node/executor/scheduler architecture

---

## 1. Vision & Scope

FlowFrame ML extends the drag-and-drop ETL canvas to cover the full tabular ML lifecycle:

```
raw data → clean → engineer features → split → train → evaluate → register → predict
```

Every step is a node. Every run is reproducible. The user never writes boilerplate.

### What is in scope

- **Supervised learning:** classification, regression (binary, multiclass, multi-output)
- **Unsupervised learning:** clustering (K-Means, DBSCAN), dimensionality reduction (PCA, t-SNE for visualization)
- **Feature engineering:** scaling, encoding, selection, imputation
- **Evaluation:** standard metrics, confusion matrix, feature importance, learning curves
- **Model registry:** version, tag, promote/demote via MLflow 3
- **Scheduling:** periodic retraining on refreshed dataset versions (reuses existing scheduler)
- **Code export:** generated sklearn/XGBoost Python matching the visual graph, very popular Sklearn compatible models can be used as well

### What is explicitly out of scope (v1)

- Deep learning / neural networks (PyTorch, TensorFlow) — separate canvas metaphor
- Distributed training (Spark ML, Ray Train) — different infrastructure contract
- Real-time serving / model endpoints (use MLflow Serving or BentoML separately)
- NLP, computer vision, time-series-specific models (LSTM, Prophet) — deferred
- Online learning / streaming

---

## 2. Dependency Strategy

### Install extras pattern

```toml
# pyproject.toml
[project.optional-dependencies]
ml = [
    "scikit-learn>=1.5",
    "xgboost>=2.0",
    "lightgbm>=4.0",
    "mlflow>=3.0",
    "joblib>=1.3",       # safe model serialization
]
```

The base install never imports any ML library. ML nodes check availability at registration time
and surface a clear install hint if the extra is missing — identical to how SQL connectors
handle missing drivers today (`ConnectionCard` disabled state with pip hint).

### Why these specific libraries

| Library | Rationale |
|---|---|
| **scikit-learn** | Unified API (`fit`/`predict`/`transform`), Pipeline-compatible, every algorithm documented |
| **XGBoost** | Best single-model performance on tabular data; sklearn-compatible API |
| **LightGBM** | Faster than XGBoost on large datasets; handles categoricals natively |
| **MLflow 3** | Artifact store + registry + experiment tracking; local-first (SQLite backend); avoids building our own |
| **joblib** | Safe model serialization (replaces pickle); industry standard for sklearn |


### Why NOT pickle for model serialization

`pickle.loads()` executes arbitrary code. A malicious `.pkl` file passed to `mlPredict` would
give the attacker RCE on the FlowFrame server. We use `joblib` for sklearn models and
`xgboost.Booster.save_model()` (JSON format) for XGBoost. The executor validates the file
extension and MIME type before loading. See Security section §6.

---

## 3. Node Catalog

### 3.1 Input/Output (no changes needed)

Existing `csvInput`, `parquetInput`, `sqlInput` nodes feed ML flows unchanged.
The dataset versioning system (immutable `DatasetVersion` snapshots) already provides
the reproducibility guarantee we need.

### 3.2 Feature Engineering Nodes

These are pure dataframe → dataframe transforms. They fit the current `BaseTransformation`
contract with zero executor changes. Register in `app/engine/registry.py`.

| Node type | Operation | Key config fields |
|---|---|---|
| `scaleFeatures` | StandardScaler / MinMaxScaler / RobustScaler | `method`, `columns` |
| `encodeCategories` | OneHotEncoder / OrdinalEncoder / TargetEncoder | `method`, `columns`, `drop_first` |
| `imputeMissing` | Mean / Median / Mode / Constant / KNN imputer | `strategy`, `columns`, `fill_value` |
| `selectFeatures` | Variance threshold, SelectKBest, correlation filter | `method`, `k`, `threshold` |
| `createInteractions` | PolynomialFeatures on selected columns | `columns`, `degree`, `include_bias` |
| `reduceDimensions` | PCA (transform only — for visualization or compression) | `n_components`, `method` |

We can add more if we see it as useful

**Edge case — scaler state:** A scaler fitted on training data must be applied to test/predict
data with the same parameters (mean, std, etc.). The `scaleFeatures` node is **stateless in
the graph** — it refits on whatever dataframe arrives. This is correct for the training
branch. For prediction, the scaler parameters must come from the saved model artifact
(the `mlTrain` node bundles preprocessing into an `sklearn.Pipeline` — see §4).

### 3.3 `trainTestSplit` — Two-output node

```
         ┌──► [train out]
[in] ───►│
         └──► [test out]
```

Config:
```json
{
  "test_size": 0.2,
  "stratify_column": "target",  // null = no stratification
  "seed": 42                    // REQUIRED — no default, enforced at validate_config
}
```

**Seed is required, not optional.** Allowing random splits silently breaks reproducibility.
The `validate_config` method raises `ValidationError` if `seed` is absent or null.

**Stratification edge cases:**
- Stratify on a column with fewer than 2 samples per class → raise `ValidationError` with
  count info: `"Class 'X' has only 1 sample — cannot stratify. Reduce test_size or merge classes."`
- Stratify on a regression target → warn in logs; do not block (the user may want it for
  distribution analysis)

Executor change needed: the node returns `{"train": df_train, "test": df_test}` — two keys.
The graph validation must allow two outgoing edges from this node with `sourceHandle` = `"train"`
and `"test"`. Add `trainTestSplit` to `node_kinds.MULTI_OUTPUT_NODES` with declared handle names.

### 3.4 `mlTrain` — The central node

```
[train data] ──► [mlTrain] ──► [model ref out]
                               [train metrics out]  (optional second output)
```

Config:
```json
{
  "model_type": "random_forest_classifier",
  "target_column": "churn",
  "feature_columns": ["tenure", "monthly_charges", "contract"],
  "hyperparameters": {
    "n_estimators": 200,
    "max_depth": 10,
    "class_weight": "balanced"
  },
  "cross_validate": true,
  "cv_folds": 5,
  "seed": 42,
  "mlflow_experiment": "churn_model"  // optional; defaults to flow name
}
```

**Supported model types (v1):**

| Task | Model type string | Library |
|---|---|---|
| Binary classification | `logistic_regression`, `random_forest_classifier`, `xgboost_classifier`, `lightgbm_classifier`, `svm_classifier`, `knn_classifier` | sklearn / xgboost / lgbm |
| Multiclass | Same strings — task inferred from target cardinality | |
| Regression | `linear_regression`, `ridge`, `lasso`, `random_forest_regressor`, `xgboost_regressor`, `lightgbm_regressor`, `svr` | sklearn / xgboost / lgbm |
| Clustering | `kmeans`, `dbscan`, `agglomerative` | sklearn |
| Dimensionality reduction (fit) | `pca_fit` | sklearn |

**What `mlTrain.execute()` does:**

1. Validates config (target column exists, feature columns exist, no overlap)
2. Checks for data leakage: if `target_column` appears in `feature_columns` → `ValidationError`
3. Checks minimum sample count: `< 10` rows → error; `< 50` rows → warning in logs
4. Builds `sklearn.Pipeline([('preprocessor', ...), ('model', ...)])` — preprocessing is
   bundled INTO the model artifact so prediction uses identical transforms
5. Fits the pipeline on the incoming dataframe
6. Runs cross-validation if `cross_validate=True` (scoring happens inside `execute()`)
7. Calls `mlflow.sklearn.log_model()` to persist artifact + metadata
8. Returns `{"out": training_df, "model": model_ref_df}` where `model_ref_df` is a
   single-row dataframe: `{"mlflow_run_id": "...", "model_uri": "runs:/.../model", "task_type": "classification"}`

**Why bundle preprocessing into the Pipeline:**
If scaler/encoder live in separate upstream nodes and the user wires them incorrectly
(e.g., fits on full dataset before split), they silently leak distribution info into the
test set. Bundling preprocessing into the `mlTrain` Pipeline ensures the scaler is always
fitted only on training data, regardless of what upstream nodes do.

This means `scaleFeatures` / `encodeCategories` upstream of `mlTrain` are for *exploration
and preview only*. The `mlTrain` config has a `preprocessing` section that replicates
those operations inside the Pipeline:

```json
{
  "preprocessing": {
    "numeric_columns": ["tenure", "monthly_charges"],
    "numeric_strategy": "standard_scaler",
    "categorical_columns": ["contract"],
    "categorical_strategy": "onehot",
    "impute_numeric": "median",
    "impute_categorical": "most_frequent"
  }
}
```

This is explicit in the config form, not inferred from upstream connections.

### 3.5 `mlPredict` — Load model and score

```
[data] ──────────► [mlPredict] ──► [data + predictions]
[model ref] ────►
```

Config:
```json
{
  "model_uri": null,    // if null, reads from the "model" input handle
  "output_column": "predicted_churn",
  "output_proba_columns": ["proba_0", "proba_1"],  // null = no probabilities
  "batch_size": null    // null = predict all at once; int = chunked for memory safety
}
```

Security critical: `model_uri` if provided by config must be validated against an allowlist
of schemes: `runs:/`, `models:/`, and the local artifact store path under `DATA_DIR`.
Absolute paths outside `DATA_DIR` are rejected. See §6.

**Edge cases:**
- Model was trained on different feature columns → raise `ValidationError` listing the diff:
  `"Model expects ['tenure', 'contract'] but input has ['tenure', 'monthly_charges']"`
- Task type is `clustering` → no `predict_proba`; `output_proba_columns` is ignored with a warning
- Memory: for large dataframes, chunked prediction via `batch_size` prevents OOM;
  default is `None` (all at once) but the config form warns when `rows > 1_000_000`

### 3.6 `mlEvaluate` — Metrics node

```
[predictions] ──► [mlEvaluate] ──► [metrics dataframe]
```

Config:
```json
{
  "task_type": "classification",   // or "regression", "clustering"
  "target_column": "churn",
  "prediction_column": "predicted_churn",
  "proba_columns": ["proba_0", "proba_1"],
  "metrics": ["f1_weighted", "roc_auc", "precision", "recall", "confusion_matrix"]
}
```

Returns a dataframe with one row per metric (long format) so it can feed a `csvOutput` or
be previewed in the canvas node inspector.

For clustering: silhouette score, Davies-Bouldin index, inertia (if K-Means).
For regression: RMSE, MAE, R², MAPE, residual std.

### 3.7 `featureImportance` — Explainability node (optional, v1)

Takes the `model ref` output from `mlTrain` and returns a dataframe:

```
feature_name | importance | rank
tenure       | 0.42       | 1
contract     | 0.31       | 2
```

Works for: tree-based models (`.feature_importances_`), linear models (`.coef_`),
XGBoost (gain/weight/cover).
Does NOT support: SVM, KNN — raises `ValidationError` with explanation.

---

## 4. Executor Changes

### 4.1 Multi-output handle support

Current contract: `execute()` returns `{"out": df}`.

New contract (backward-compatible): `execute()` may return any dict of named dataframes.
The executor resolves outgoing edges by matching `edge.sourceHandle` to the key:

```python
# graph.py — node_kinds additions
MULTI_OUTPUT_NODES = {
    "trainTestSplit": ["train", "test"],
    "mlTrain": ["out", "model"],     # "out" = training data passthrough; "model" = ref df
}
```

Backward compatibility: if `sourceHandle` is absent on an edge and the node has only
one output key, use it. If there are multiple keys and no handle specified, raise
`GraphValidationError`.

### 4.2 ML-aware NodeResult

Extend `NodeResultRead` (in `app/schemas/run.py`) with optional ML fields:

```python
class NodeResultRead(BaseModel):
    node_id: str
    type: str
    label: str | None
    status: str
    rows: int | None
    columns: list[str]
    sample: list[dict[str, Any]]
    error: str | None
    duration_ms: float | None
    # ML-specific — None for non-ML nodes
    ml_metrics: dict[str, float] | None = None
    mlflow_run_id: str | None = None
    model_uri: str | None = None
    task_type: str | None = None
    cv_scores: list[float] | None = None
```

These fields are stored in the existing `node_results_json` blob on `FlowRun` — no new
DB table needed for v1. A `MLFlowRun` table can be added in v2 if query patterns demand it.

### 4.3 Timeout handling for long-running training

The current `RUN_TIMEOUT_SECONDS` is a global setting. ML training can take minutes to hours.
Add a per-schedule `run_timeout_seconds` override field to `Schedule`:

```python
# app/db/models/schedule.py
run_timeout_seconds: Mapped[int | None]  # None = use global setting
```

When the executor starts a run triggered by a schedule, it reads this field and passes it
to the timeout wrapper instead of the global default.

For manual runs, a `FlowRunCreate.timeout_seconds` optional field lets the API caller
specify a per-run timeout.

### 4.4 Process mode for ML training

Training is CPU-bound. Set `EXECUTION_MODE=process` for ML-heavy deployments.
The executor already supports `ProcessPoolExecutor` — no changes needed. Document this
prominently in the ML setup guide.

**Caveat:** sklearn models are picklable (required for process mode). XGBoost Booster objects
are also picklable. All ML node results must be serializable across the process boundary.
The `model_ref_df` (a pandas DataFrame with string columns) is trivially picklable.

---

## 5. MLflow 3 Integration

### 5.1 Configuration

```python
# app/core/config.py additions
ML_ENABLED: bool = False            # Feature flag; false until fully shipped
MLFLOW_TRACKING_URI: str = "./mlruns"  # Local default; set to remote for teams
MLFLOW_REGISTRY_URI: str | None = None  # None = same as tracking URI
ML_ARTIFACT_DIR: str = ".data/ml_artifacts"  # Local artifact root
ML_MAX_MODEL_SIZE_MB: int = 500     # Reject models larger than this on save
```

`MLFLOW_TRACKING_URI` accepts the same formats MLflow does: `sqlite:///path`,
`http://mlflow-server:5000`, `databricks`, etc. The local default requires no setup.

### 5.2 Experiment naming convention

```
flowframe/{project_name}/{flow_name}
```

If `mlflow_experiment` is set in node config, it overrides this. The experiment is
auto-created on first run if it doesn't exist.

### 5.3 What gets logged to MLflow per training run

```python
mlflow.log_params({
    "model_type": config["model_type"],
    "feature_columns": json.dumps(config["feature_columns"]),
    "target_column": config["target_column"],
    "seed": config["seed"],
    "train_rows": len(X_train),
    "sklearn_version": sklearn.__version__,
    "flowframe_run_id": flow_run_id,  # back-pointer to FlowFrame run
    "dataset_version_id": dataset_version_id,  # reproducibility anchor
    **hyperparameters,
})

mlflow.log_metrics(metrics_dict)  # RMSE, F1, etc.

mlflow.sklearn.log_model(pipeline, "model", input_example=X_train.head(5))
# or: mlflow.xgboost.log_model(...)
```

The `flowframe_run_id` tag in MLflow lets you trace any registered model back to the
exact FlowFrame run (and thus the exact `graph_json` and `DatasetVersion`) that produced it.

### 5.4 Model registry integration

A model can be promoted from the run artifact to the registry:

```
POST /api/runs/{run_id}/ml/register
Body: { "model_name": "churn-predictor", "stage": "Staging" }
```

This calls `mlflow.register_model(model_uri, name)`. No ML logic in the route — pure MLflow client call.
Stages: `None → Staging → Production → Archived` (MLflow 3 lifecycle).

The `mlPredict` node can reference a registered model by name+stage:
```json
{ "model_uri": "models:/churn-predictor/Production" }
```

This means production prediction flows never need to be updated when a model is retrained —
promote the new version to Production in the registry and the next scheduled run picks it up.

---

## 6. Security

### 6.1 Model artifact path validation

The `mlPredict` node accepts a `model_uri` from config (user-supplied). This must be
validated before any file I/O:

```python
_ALLOWED_MODEL_URI_SCHEMES = {"runs:/", "models:/"}

def validate_model_uri(uri: str, data_dir: str) -> str:
    """Raise ValidationError if uri is not a safe MLflow URI or within DATA_DIR."""
    for scheme in _ALLOWED_MODEL_URI_SCHEMES:
        if uri.startswith(scheme):
            return uri  # Let MLflow client resolve; it validates run/model existence
    # Treat as local path
    resolved = Path(uri).resolve()
    artifact_root = Path(data_dir, "ml_artifacts").resolve()
    try:
        resolved.relative_to(artifact_root)
    except ValueError:
        raise ValidationError(
            f"model_uri {uri!r} is outside the allowed artifact directory. "
            f"Use a 'runs:/' or 'models:/' URI, or a path under {artifact_root}."
        )
    return str(resolved)
```

### 6.2 No pickle for model loading

`joblib.load()` is used instead of `pickle.load()` for all sklearn artifacts. XGBoost models
are saved/loaded with `.save_model()` / `.load_model()` (JSON format, not pickle).

When loading a model from `mlPredict`, the executor checks the file extension:
- `.joblib` → allowed (sklearn Pipeline)
- `.json` → allowed (XGBoost native)
- `.pkl` / `.pickle` → **rejected** with `ValidationError`
- Any other extension → rejected

If a user somehow points `model_uri` at a `.pkl` file in the artifact dir, the load is
blocked before it executes.

### 6.3 Hyperparameter injection

Hyperparameters are passed to model constructors as `**dict`. Any key that maps to a
valid sklearn constructor parameter is accepted; unknown keys raise `TypeError` from
sklearn, which is caught and surfaced as `ValidationError`.

The executor does NOT `eval()` or `exec()` any hyperparameter value. All values must be
JSON-native (number, string, bool, null, array, object). If a value is a string that looks
like Python code (e.g., `"lambda x: x**2"`), it is passed as a literal string, which
sklearn will reject at fit time with a clear error.

### 6.4 Resource limits

```python
# Settings
ML_MAX_TRAINING_ROWS: int = 5_000_000   # Reject training jobs larger than this
ML_MAX_FEATURE_COLUMNS: int = 500       # Prevents accidental one-hot explosion
ML_MAX_MODEL_SIZE_MB: int = 500         # Reject artifact save if file exceeds this
```

`mlTrain.validate_config()` checks row count (from `DatasetVersion.row_count`) before
execution starts, so oversized jobs are rejected at the API layer before consuming CPU.

Memory during training is not bounded at the library level (sklearn has no native memory
cap). Document that users should set `EXECUTION_MODE=process` and OS-level memory limits
(`ulimit -v` on Linux) for shared deployments. For Docker deployments, `--memory` flag is
the recommended guardrail.

### 6.5 Target column leakage detection

Before fitting, validate:

```python
if target_col in feature_cols:
    raise ValidationError(f"target_column '{target_col}' is in feature_columns — data leakage.")

# Check for near-perfect predictors (post-split, on training set only)
for col in feature_cols:
    if df_train[col].nunique() == df_train[target_col].nunique() == len(df_train):
        logger.warning(f"Column '{col}' has unique values for every row — possible ID leakage.")
```

### 6.6 Dataset access for ML runs

ML training nodes read from the same `DatasetVersion` snapshot system as ETL nodes.
No additional access control is needed for v1 (FlowFrame is local-first, single-user).
For multi-user deployments, dataset-level permissions should be addressed at the project
level before the ML extension ships — out of scope here.

---

## 7. Reproducibility Contract

A FlowFrame ML run is reproducible if you can reproduce the same model from the same inputs.
The following are recorded on every ML training run:

| What | Where stored | How used |
|---|---|---|
| `graph_json` snapshot | `FlowRun.graph_snapshot_json` (NEW FIELD) | Re-run exact same graph |
| `DatasetVersion.id` | `FlowRun.input_datasets_json` (existing) | Exact data snapshot |
| `seed` | `mlTrain` config + MLflow param | Deterministic split + model |
| `hyperparameters` | MLflow params + `node_results_json` | Reproduce training |
| Library versions | MLflow params (`sklearn_version`, etc.) | Diagnose drift |
| `mlflow_run_id` | `NodeResult.mlflow_run_id` | Retrieve full MLflow artifact |
| Training metrics | `NodeResult.ml_metrics` + MLflow metrics | Compare runs |

**`graph_snapshot_json` — new field on `FlowRun`:**

Currently, `FlowRun` stores a reference to `Flow.graph_json`, but the flow's graph can be
edited after the run. A new `graph_snapshot_json` column captures the graph at trigger time.
This is a one-line migration: `ALTER TABLE flow_runs ADD COLUMN graph_snapshot_json JSON`.
Both ETL and ML runs benefit from this field.

**What is NOT guaranteed:**

- Floating-point exact reproducibility on different hardware (CPU instruction sets, BLAS
  versions affect float64 ops in sklearn). The seed guarantees identical data splits and
  algorithm random state; it does not guarantee bit-identical weights on ARM vs x86.
- Reproducibility if the MLflow artifact is deleted externally (outside FlowFrame).
  Document: treat `MLFLOW_TRACKING_URI` directory as immutable for any run you want to reproduce.

---

## 8. Dataset Deletion Policy

When a `Dataset` is deleted, the associated `DatasetVersion` files may have been used to
train models. The policy for v1:

**Soft orphan with audit trail:**

1. Deleting a `Dataset` sets `is_disabled = True` and records `deleted_at` (new nullable
   column). The files on disk are **retained** for 30 days (configurable via
   `ML_ARTIFACT_RETENTION_DAYS`).
2. Any `FlowRun` or `MLflow run` that trained on the deleted dataset continues to reference
   the version ID. The UI shows `[dataset deleted]` next to the version badge.
3. If the dataset's files are purged (after retention period or manual purge), the
   `DatasetVersion.location` path no longer resolves. Attempting to re-run a historical
   ML flow on a purged dataset raises a clear error:
   ```
   DatasetVersionError: DatasetVersion 'v3 of customers.csv' was deleted on 2026-07-01.
   To re-run, upload the dataset again or restore from backup.
   ```
4. The model artifact in MLflow is **not affected** by dataset deletion. A trained model
   can still serve predictions even if its training data is gone.

**Block deletion if a live Production model depends on the dataset (v2):**
When a model is in `Production` stage in the MLflow registry and its training dataset
is being deleted, the API returns `409 Conflict` with:
```
"A Production model 'churn-predictor/v3' was trained on this dataset. 
Demote it from Production before deleting."
```

---

## 9. Scheduling ETL + ML Flows

### Pattern A — Separate schedules (recommended for decoupled teams)

```
Schedule A: ETL flow    daily 02:00 UTC → writes DatasetVersion N
Schedule B: ML flow     daily 04:00 UTC → reads latest DatasetVersion (version=null)
```

The 2-hour gap is a safety buffer. For tighter coupling, see Pattern B.

### Pattern B — Single composite flow (recommended for solo or small teams)

```
csvInput ──► dropNulls ──► featureEngineer ──► trainTestSplit
                                                    ├──[train]──► mlTrain ──► mlEvaluate ──► csvOutput(metrics)
                                                    └──[test]───────────────► mlEvaluate
```

One schedule, one run history, one place to check if something broke.
The ETL prefix runs first (topological order), the ML suffix runs after.

### Pattern C — Trigger ML retraining from ETL run completion (v2)

A `Schedule.trigger_on_flow_id` field would let the ML schedule fire automatically when
a specific ETL flow run succeeds. Out of scope for v1 — implement Patterns A and B first.

### Scheduler settings for ML workloads

```bash
FLOWFRAME_RUN_TIMEOUT_SECONDS=7200        # 2 hours default for ML flows
FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS=2 # Allow ETL + ML to run in parallel
FLOWFRAME_EXECUTION_MODE=process          # True parallelism for CPU-bound training
```

Set `run_timeout_seconds` on the `Schedule` record to override the global default
per-schedule (see §4.3).

---

## 10. Code Export for ML Flows

The `to_python_code()` method on each ML node generates runnable scikit-learn code.
Export produces a self-contained script with no FlowFrame dependencies:

```python
# Generated by FlowFrame ML export

import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import mlflow

# Load data
df_0 = pd.read_parquet("customers.parquet")  # DatasetVersion 3

# Feature engineering
df_1 = df_0.dropna(subset=["tenure", "monthly_charges"])

# Train/test split
df_train, df_test = train_test_split(
    df_1, test_size=0.2, stratify=df_1["churn"], random_state=42
)

# Build pipeline (preprocessing + model)
pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42)),
])
X_train = df_train[["tenure", "monthly_charges", "contract"]]
y_train = df_train["churn"]
pipeline.fit(X_train, y_train)

# Evaluate
X_test = df_test[["tenure", "monthly_charges", "contract"]]
y_test = df_test["churn"]
print(classification_report(y_test, pipeline.predict(X_test)))

# Save
joblib.dump(pipeline, "model.joblib")
```

The export does NOT include MLflow calls (the generated script is for standalone use).
A separate "export with tracking" option can include `mlflow.start_run()` wrappers.

---

## 11. Frontend Canvas Integration

### Node palette additions

New palette section **"Machine Learning"** below the existing "Transform" section.
Nodes render identically to ETL nodes (card + icon + config panel).

### Multi-output handle rendering

`trainTestSplit` needs two source handles labeled `train` and `test`.
React Flow already supports multiple source handles on a node — this is the same pattern
as the existing `join` node's dual target handles, just mirrored to the source side.

```tsx
// Example handle layout for trainTestSplit
<Handle type="source" position={Position.Right} id="train" style={{ top: "35%" }} />
<Handle type="source" position={Position.Right} id="test"  style={{ top: "65%" }} />
```

### ML run detail panel

The run detail page (`/runs/:id`) adds an **ML Metrics** tab when any node in the run
has `ml_metrics` populated. It shows:
- Metrics table (metric name, value, comparison to previous run if available)
- Confusion matrix (for classification) rendered as a heatmap
- Feature importance bar chart (if `featureImportance` node present)
- Link to MLflow UI (`MLFLOW_TRACKING_URI` + `/experiments/...`)

### Model ref wire color

Edges carrying `model ref` dataframes (from `mlTrain → mlPredict`) are rendered in a
distinct color (e.g., purple) vs. data edges (blue). This makes the graph readable at a
glance: blue = data flow, purple = model flow.

---

## 12. Error Handling Reference

Covers cases that are not obvious and would otherwise produce silent failures or confusing errors:

| Situation | Behavior |
|---|---|
| `feature_columns` contains a column dropped upstream | `ValidationError` at graph validation time (column schema propagated through nodes) |
| Training set has only one class after split | `ValidationError`: `"Training set has only 1 class for 'churn'. Use stratify or increase train_size."` |
| Model fit raises `ConvergenceWarning` | Captured as `NodeResult.warning`; run still succeeds |
| XGBoost not installed, user adds `xgboost_classifier` | `NodeResult.status = "failed"`, `error = "XGBoost not installed. Run: pip install flowframe[ml]"` |
| `mlPredict` node receives data with extra columns not in training features | Warning logged; extra columns are dropped before predict (consistent with sklearn Pipeline behavior) |
| `mlPredict` node receives data with missing training features | `ValidationError`: lists the missing columns |
| MLflow tracking server unreachable | Training still succeeds; artifact stored locally; warning: `"MLflow server unreachable — run logged locally only"` |
| Training produces a model file > `ML_MAX_MODEL_SIZE_MB` | `ValidationError` after fit, before MLflow log: prevents bloating artifact store |
| `cv_folds=5` but training set has < 5 rows | `ValidationError`: `"Cannot run 5-fold CV with only 3 training rows."` |
| `dbscan` clustering produces all noise (-1 label) | Warning: `"DBSCAN assigned all points to noise. Try adjusting eps or min_samples."` |
| PCA `n_components` > number of features | Silently capped by sklearn; logged as info |
| `trainTestSplit` with `test_size=0.99` leaves 1 training row | `ValidationError`: training set must have `>= 10 rows` |

---

## 13. Implementation TODO

Track progress here as features are built and tested.

### Phase 1 — Backend Core (no frontend required)

#### Infrastructure

- [ ] Add `ml = [...]` optional dependency group to `pyproject.toml`
- [ ] Add `ML_ENABLED`, `MLFLOW_TRACKING_URI`, `ML_ARTIFACT_DIR`, `ML_MAX_MODEL_SIZE_MB`,
      `ML_MAX_TRAINING_ROWS`, `ML_MAX_FEATURE_COLUMNS` to `app/core/config.py`
- [ ] Add `graph_snapshot_json` column to `FlowRun` + Alembic migration
- [ ] Add `run_timeout_seconds` column to `Schedule` + Alembic migration
- [ ] Add `ml_metrics`, `mlflow_run_id`, `model_uri`, `task_type`, `cv_scores` fields
      to `NodeResultRead` schema (backward-compatible: all `None` for non-ML nodes)
- [ ] Add `ML_ENABLED` feature flag check to any ML route/node; return `501 Not Implemented` if disabled

#### Executor changes

- [ ] Extend executor to support multi-key execute returns (`{"train": df, "test": df}`)
- [ ] Add `MULTI_OUTPUT_NODES` to `node_kinds.py`
- [ ] Update graph validation to allow `sourceHandle` on edges from multi-output nodes
- [ ] Implement `run_timeout_seconds` per-run override (Schedule → FlowRunCreate → executor)

#### Feature engineering nodes

- [ ] `scaleFeatures` node — implement + tests (all 3 strategies)
- [ ] `encodeCategories` node — implement + tests (onehot, ordinal; handle unknown categories)
- [ ] `imputeMissing` node — implement + tests (all strategies; check no fit-on-test leakage warning)
- [ ] `selectFeatures` node — implement + tests (variance threshold + SelectKBest)
- [ ] `reduceDimensions` (PCA transform only) — implement + tests

#### Core ML nodes

- [ ] `trainTestSplit` node — implement + tests (seed required; stratify edge cases)
- [ ] `mlTrain` node — implement + tests
  - [ ] sklearn classifiers (logistic, RF, SVM, KNN)
  - [ ] sklearn regressors (linear, ridge, lasso, RF, SVR)
  - [ ] XGBoost classifier + regressor
  - [ ] LightGBM classifier + regressor
  - [ ] clustering (KMeans, DBSCAN, Agglomerative)
  - [ ] Pipeline bundling with preprocessing config
  - [ ] Cross-validation support
  - [ ] MLflow logging integration
  - [ ] Leakage detection (target in features, unique-value warning)
  - [ ] Size limit enforcement (`ML_MAX_MODEL_SIZE_MB`)
- [ ] `mlPredict` node — implement + tests
  - [ ] Load from `runs:/` URI
  - [ ] Load from `models:/` URI
  - [ ] Load from local path (within `ML_ARTIFACT_DIR` only)
  - [ ] Reject `.pkl`/`.pickle` extensions
  - [ ] Feature mismatch detection (missing + extra columns)
  - [ ] Batch prediction for large datasets
- [ ] `mlEvaluate` node — implement + tests
  - [ ] Classification metrics (F1, precision, recall, ROC-AUC, confusion matrix)
  - [ ] Regression metrics (RMSE, MAE, R², MAPE)
  - [ ] Clustering metrics (silhouette, Davies-Bouldin)
- [ ] `featureImportance` node — implement + tests (tree-based + linear models)

#### Security

- [ ] `validate_model_uri()` utility — implement + tests (traversal, scheme allowlist)
- [ ] Hyperparameter sanitization (no eval/exec; JSON-native types only)
- [ ] `ML_MAX_TRAINING_ROWS` and `ML_MAX_FEATURE_COLUMNS` enforcement in `validate_config`
- [ ] File extension check on model load (reject `.pkl`)

#### Code generation

- [ ] `to_python_code()` for all ML nodes (standalone sklearn/xgboost/lgbm code)
- [ ] `to_polars_code()` stubs (ML nodes emit pandas code regardless of engine; document why)

### Phase 2 — API & Persistence

- [ ] `POST /api/runs/{run_id}/ml/register` — promote run artifact to MLflow registry
- [ ] `GET /api/runs/{run_id}/ml/metrics` — return `ml_metrics` from node results
- [ ] `GET /api/runs/{run_id}/ml/model` — stream model artifact file (with path validation)
- [ ] `GET /api/flows/{flow_id}/ml/experiments` — list MLflow experiments for this flow
- [ ] Dataset soft-delete: add `is_disabled`, `deleted_at`, retention cleanup task
- [ ] `409 Conflict` on dataset delete when a Production model depends on it (v2 blocker check)
- [ ] `GET /api/transformations?category=ml` — filter node types by category

### Phase 3 — Frontend

- [ ] Add `"Machine Learning"` section to node palette
- [ ] Multi-source-handle rendering for `trainTestSplit`
- [ ] Config form for `mlTrain` (model type picker, feature column multi-select, hyperparameter table)
- [ ] Config form for `mlPredict` (model URI input with validation hint)
- [ ] Config form for `mlEvaluate` (task type selector, metric checkboxes)
- [ ] ML Metrics tab on run detail page
- [ ] Confusion matrix heatmap component
- [ ] Feature importance bar chart component
- [ ] Model ref edge color (purple) in React Flow canvas
- [ ] Disabled node state for ML nodes when `ML_ENABLED=false` or library missing (like SQL cards today)
- [ ] MLflow UI deep-link from run detail page

### Phase 4 — Testing

- [ ] Unit tests for every ML node (happy path + each edge case in §12)
- [ ] Integration test: full ETL → trainTestSplit → mlTrain → mlPredict → mlEvaluate pipeline
- [ ] Security tests: path traversal on `model_uri`, `.pkl` rejection, hyperparameter injection attempts
- [ ] Reproducibility test: same seed + same DatasetVersion → identical metrics across two runs
- [ ] Large graph test: ML flow with 2000-node feature engineering prefix (recursion limit — already fixed for ETL)
- [ ] Scheduler test: ML flow fires on cron, respects per-schedule timeout
- [ ] Dataset deletion test: model survives dataset soft-delete; error on re-run after purge

### Phase 5 — Documentation

- [ ] Update `CLAUDE.md` node catalog with ML node types and handles
- [ ] Update `README.md` with ML quick-start (install extras, simple train/predict flow)
- [ ] Add `docs/guide/ml-quickstart.md` with step-by-step tutorial
- [ ] Add `docs/transformations/ml/` reference pages (one per node type)
- [ ] Update `flowframe transformations list` CLI output to show ML nodes when enabled

---

## 14. Context for Future Sessions

### Where to start

1. **`app/engine/registry.py`** — add ML node registrations here (import guard: `if ML_ENABLED`)
2. **`app/engine/node_kinds.py`** — add `MULTI_OUTPUT_NODES` dict and `trainTestSplit`/`mlTrain` entries
3. **`app/engine/executor.py`** — extend `_node_frame()` to handle multi-key returns
4. **`app/engine/transformations/ml/`** — create this directory; one file per node (e.g., `train.py`, `predict.py`, `evaluate.py`, `feature_engineering.py`)
5. **`app/schemas/run.py`** — extend `NodeResultRead` with ML fields (backward-compatible)

### Key invariants to preserve

- `BaseTransformation.execute()` return type changes from `{"out": df}` to `dict[str, AnyFrame]`.
  All existing transformations return `{"out": df}` — this is backward-compatible.
- `validate_config()` must be callable before execution, with only config (no data). Row count
  checks require the `DatasetVersion` metadata, not the actual data — pass it as an optional
  argument from the route handler.
- The graph JSON format (`nodes[].data.config`) is the source of truth. ML node configs
  must be JSON-serializable and round-trip through `graph_json` on `Flow`.

### Patterns to follow from existing code

- Feature availability check → see `app/connectors/providers.py` `_check_available()`
- Driver install hint → see `ConnectionCard` disabled state in frontend
- Safe file path resolution → see `app/connectors/local_storage.py` `_safe_path()` (security audit fix)
- Input validation regex → see `app/schemas/connection.py` `validate_password_env()`
- Test fixture pattern → see `tests/conftest.py` (ASGITransport, `get_settings.cache_clear()`)

### MLflow local setup (no server needed for dev)

```bash
# No server needed — files go to ./mlruns/
export FLOWFRAME_MLFLOW_TRACKING_URI="./mlruns"
export FLOWFRAME_ML_ENABLED=true
flowframe serve

# View runs locally
mlflow ui --backend-store-uri ./mlruns
```

### Branch strategy

Implement on `feature/ml-extension`. Keep ETL and ML code paths completely separated at
the import level — `app/engine/transformations/ml/` should never be imported by the ETL
engine unless `ML_ENABLED=True`. This keeps the base install lean and the test suite fast
for ETL-only contributors.
