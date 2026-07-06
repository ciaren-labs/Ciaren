---
title: Build an Advanced Plugin (scikit-learn)
description: A step-by-step guide to a realistic Ciaren plugin — a scikit-learn MLPClassifier that trains through a custom node (persisting to MLflow, emitting a typed model reference) and doubles as a model type inside the core Train Classifier.
search: advanced plugin scikit-learn sklearn mlpclassifier neural network machine learning hyperparameters validation node runtime example
---

# Build an Advanced Plugin: a scikit-learn Classifier

The [first-plugin tutorial](/plugins/first-plugin) builds the smallest node that
works. This one builds a **realistic** node: it trains a scikit-learn
[`MLPClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html)
with real hyperparameters, validates its config thoroughly, runs end-to-end, and
exports runnable scikit-learn code.

The finished plugin lives in the repo at
[`examples/plugins/mlp-classifier-plugin/`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/mlp-classifier-plugin)
and ships **bundled** in the Explore catalog, so a fresh install can try it
immediately. Open it alongside this page for the complete source.

::: tip What makes it "advanced"
Six things the Hello node skips: **multiple hyperparameters**, **input validation**
that fails fast with clear messages, an **optional third-party dependency**
(scikit-learn) imported safely, **faithful code export** of a multi-line body,
**model persistence** through the host's MLflow-backed ModelStore, and a
**contributed model type** that appears inside the core Train Classifier node.
:::

## The one design decision that shapes everything

A plugin node's runtime is **pandas in → pandas out**. Ciaren converts to and from
the active engine (pandas/polars) around your code. That means a plugin node
returns **DataFrames, not model objects** — the contract carries dataframes.

So a train node doesn't hand back a fitted estimator. It persists the estimator
through the host's **ModelStore** (`context.models` — it becomes an MLflow
artifact) and emits a one-row **model reference** frame on a typed `model`
output handle, plus a **metrics** frame on a second handle. The reference is
what the core **Predict** and **Feature Importance** nodes consume; the raw
model never travels through the graph. See
[ML Model Plugins](/plugins/ml-model-plugins) for the full contract.

## 1. Scaffold the package

```text
mlp-classifier-plugin/
├── ciaren_mlp/
│   ├── __init__.py
│   └── plugin.py
├── ciaren-plugin.json      # generated from the code (step 5)
└── pyproject.toml
```

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ciaren-mlp-classifier-plugin"
version = "0.2.0"
requires-python = ">=3.12"
dependencies = ["scikit-learn>=1.3", "pandas>=2.0"]

[project.entry-points."ciaren.plugins"]
mlp_classifier = "ciaren_mlp.plugin:MlpClassifierPlugin"
```

## 2. Validate the hyperparameters up front

Validation is what separates a toy from a usable node. Do it **before**
scikit-learn runs, so the editor and the exported code agree on what "valid" means
and the user gets a clear message instead of a stack trace from deep inside sklearn.

Centralize it in one `resolve_config` that merges defaults, checks every field, and
returns typed values. `validate_config` just calls it and discards the result.

```python
ACTIVATIONS = ("identity", "logistic", "tanh", "relu")
SOLVERS = ("lbfgs", "sgd", "adam")

DEFAULT_CONFIG = {
    "target_column": "", "feature_columns": [],
    "hidden_layer_sizes": "100", "activation": "relu", "solver": "adam",
    "alpha": 0.0001, "learning_rate_init": 0.001, "max_iter": 200,
    "test_size": 0.2, "random_state": 42, "stratify": True,
}

def resolve_config(config: dict) -> dict:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    target = str(cfg["target_column"]).strip()
    if not target:
        raise ValueError("mlpClassifierTrain: 'target_column' is required")
    if cfg["activation"] not in ACTIVATIONS:
        raise ValueError(f"'activation' must be one of {ACTIVATIONS}")
    if cfg["solver"] not in SOLVERS:
        raise ValueError(f"'solver' must be one of {SOLVERS}")
    test_size = float(cfg["test_size"])
    if not 0.0 < test_size < 1.0:
        raise ValueError("'test_size' must be between 0 and 1 (exclusive)")
    # …check alpha >= 0, learning_rate_init > 0, max_iter > 0, parse hidden_layer_sizes…
    return { "target_column": target, "test_size": test_size, ... }
```

`hidden_layer_sizes` is worth special handling — accept an int, a list, or a
`"64,32"` string, and coerce to the tuple of positive ints scikit-learn expects:

```python
def parse_hidden_layers(value) -> tuple[int, ...]:
    if isinstance(value, int) and not isinstance(value, bool):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    elif isinstance(value, str):
        items = [p.strip() for p in value.split(",") if p.strip()]
    else:
        raise ValueError("'hidden_layer_sizes' has an unsupported type")
    sizes = [int(n) for n in items]                       # raises on "abc"
    if not sizes or any(n <= 0 for n in sizes):
        raise ValueError("'hidden_layer_sizes' must be positive integers, e.g. '64,32'")
    return tuple(sizes)
```

See the full validation (every field, with `_as_int`/`_as_float` helpers) in the
example's `plugin.py`.

## 3. Write the runtime

Two rules for depending on scikit-learn:

1. **Import it lazily**, inside `execute`/`to_python_code` — never at module top
   level. Then the plugin still registers and shows in the catalog on machines
   without scikit-learn; running the node raises a clear "install it" message.
2. **Validate the data**, not just the config — target present, features present
   and **numeric** (an MLP can't train on strings).

The runtime overrides `execute_with_context` (not plain `execute`) because it
needs two host services: the **preview flag** and the **ModelStore**.

```python
from app.plugin_api import ModelRef, NodeContext, NodeRuntime

class MlpClassifierTrainRuntime(NodeRuntime):
    def validate_config(self, config):
        resolve_config(config)            # raise ValueError on anything unsupported

    def execute_with_context(self, inputs, config, context: NodeContext):
        import pandas as pd
        p = resolve_config(config)

        # Editor previews run on sampled data — don't fit or persist anything.
        if context.in_preview:
            placeholder = ModelRef(task_type="classification", model_type="mlp_classifier",
                                   target_column=p["target_column"])
            return {"model": placeholder.to_frame(), "metrics": pd.DataFrame()}

        try:
            from sklearn.metrics import accuracy_score
            from sklearn.model_selection import train_test_split
            from sklearn.neural_network import MLPClassifier
        except ImportError as exc:
            raise ValueError("mlpClassifierTrain needs scikit-learn — pip install scikit-learn") from exc

        df, target = inputs["in"], p["target_column"]
        if target not in df.columns:
            raise ValueError(f"target column {target!r} is not in the input")
        features = p["feature_columns"] or [c for c in df.columns if c != target]
        non_numeric = [c for c in features if not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            raise ValueError(f"feature columns must be numeric; non-numeric: {non_numeric}")

        X, y = df[features], df[target]
        # Stratify only when valid, else scikit-learn would raise.
        stratify = y if p["stratify"] and y.nunique() > 1 and y.value_counts().min() >= 2 else None
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=p["test_size"], random_state=p["random_state"], stratify=stratify)
        clf = MLPClassifier(
            hidden_layer_sizes=p["hidden_layer_sizes"], activation=p["activation"],
            solver=p["solver"], alpha=p["alpha"], learning_rate_init=p["learning_rate_init"],
            max_iter=p["max_iter"], random_state=p["random_state"])
        clf.fit(X_train, y_train)

        metrics = {
            "n_samples": len(df), "n_features": len(features), "n_classes": len(clf.classes_),
            "train_accuracy": float(accuracy_score(y_train, clf.predict(X_train))),
            "test_accuracy": float(accuracy_score(y_test, clf.predict(X_test))),
            "n_iterations": int(clf.n_iter_), "final_loss": float(clf.loss_),
        }

        # Persist through the host: the estimator becomes an MLflow artifact and
        # only the typed reference travels through the graph.
        if context.models is None:
            raise ValueError("this server has no ML/MLflow support enabled")
        # params + seed land in the reference's model_config_json — the model-wire
        # contract core Cross-Validate rebuilds the estimator from.
        ref = context.models.log_sklearn_model(
            clf, model_type="mlp_classifier", task_type="classification",
            target_column=target, feature_columns=tuple(features),
            params={"hidden_layer_sizes": ",".join(map(str, p["hidden_layer_sizes"])),
                    "activation": p["activation"], "solver": p["solver"],
                    "alpha": p["alpha"], "max_iter": p["max_iter"]},
            metrics={"train_accuracy": metrics["train_accuracy"],
                     "test_accuracy": metrics["test_accuracy"]},
            input_example=X_train.head(5), seed=p["random_state"])
        return {"model": ref.to_frame(), "metrics": pd.DataFrame([metrics])}
```

### Register the node

The spec declares two outputs — a typed **`model`** port (only connects to model
inputs; graph validation enforces it) and a regular `metrics` frame — marks the
node a **flow terminal** (a flow may end at it, since it persists a model), and
ships a **`config_schema`** so the sidebar renders a real form:

```python
class _MlpNodeProvider(NodeProvider):
    def nodes(self):
        return [NodeSpec(
            id="sklearn.mlpClassifierTrain",
            label="MLP Classifier (train)",
            category="ml",
            provider="community.mlp-classifier",
            inputs=(PortSpec(id="in"),),
            outputs=(PortSpec(id="model", type="model"), PortSpec(id="metrics")),
            default_config=dict(DEFAULT_CONFIG),
            capabilities=("node.sklearn.mlp",),
            is_model_sink=True,
            is_flow_terminal=True,
            config_schema={"fields": [
                {"key": "target_column", "label": "Target column", "type": "column", "required": True},
                {"key": "hidden_layer_sizes", "label": "Hidden layers", "type": "string", "default": "100"},
                {"key": "activation", "label": "Activation", "type": "select",
                 "options": ["identity", "logistic", "tanh", "relu"], "default": "relu"},
                # …see the example source for the full field list
            ]},
        )]
    def node_implementations(self):
        return {"sklearn.mlpClassifierTrain": MlpClassifierTrainRuntime()}
```

`category="ml"` slots the node into the ML section of the palette. (Only the
built-in ML nodes are hidden when `CIAREN_ML_ENABLED=false`; a plugin node always
shows once approved.)

### Bonus: put the algorithm inside the core Train Classifier too

The same plugin also registers a **ModelProvider**, so `mlp_classifier` appears
in the standard *Train Classifier* model picker and trains through the core
pipeline (preprocessing, MLflow logging, code export) with zero extra runtime
code — the plugin only supplies the estimator builder and a hyperparameter form
schema:

```python
class MlpClassifierPlugin(Plugin):
    def metadata(self):
        return PluginMetadata(id="community.mlp-classifier", name="MLP Classifier", version="0.2.0")
    def register(self, registry):
        registry.register_node_provider(_MlpNodeProvider())
        registry.register_model_provider(_MlpModelProvider())   # see ML Model Plugins
```

The full `_MlpModelProvider` is a ~30-line class — walk through it in
[ML Model Plugins](/plugins/ml-model-plugins#path-1-contribute-a-model-type).

## 4. Export runnable code

`to_python_code` returns a **multi-line** string of real scikit-learn code, and
`imports()` declares the imports the script needs — Ciaren dedupes and orders them.
Derive helper variable names from the output variable so two training nodes in one
flow can't collide, and read the input variable only *before* assigning the output
(so Ciaren's variable-reuse optimization stays correct):

```python
def imports(self, config):
    return ["from sklearn.metrics import accuracy_score",
            "from sklearn.model_selection import train_test_split",
            "from sklearn.neural_network import MLPClassifier"]

def to_python_code(self, input_vars, output_vars, config):
    p = resolve_config(config)
    inp = input_vars["in"]
    model_var = output_vars.get("model", "mlp_model")      # one variable per output handle
    metrics_var = output_vars.get("metrics", "mlp_metrics")
    feat = f"{model_var}_features"
    return "\n".join([
        f"{feat} = [c for c in {inp}.columns if c != {p['target_column']!r}]",
        f"X_tr, X_te, y_tr, y_te = train_test_split({inp}[{feat}], {inp}[{p['target_column']!r}], "
        f"test_size={p['test_size']!r}, random_state={p['random_state']!r})",
        f"{model_var} = MLPClassifier(hidden_layer_sizes={p['hidden_layer_sizes']!r}, max_iter={p['max_iter']!r})",
        f"{model_var}.fit(X_tr, y_tr)",
        f"{metrics_var} = pd.DataFrame([{{'test_accuracy': accuracy_score(y_te, {model_var}.predict(X_te))}}])",
    ])
```

Because the runtime is pandas-based, Ciaren automatically bridges it into the
**polars** export too (wrapping with `to_pandas()` / `from_pandas()`), so both
exporters work with no extra code.

## 5. Generate the manifest and run it

Don't hand-write the manifest — generate it from the code so the two never drift:

```bash
ciaren-plugin manifest ./mlp-classifier-plugin \
  --entrypoint ciaren_mlp.plugin:MlpClassifierPlugin
```

Then load it and try it on the canvas:

```bash
export CIAREN_PLUGINS_DIR=/path/to/examples/plugins
ciaren serve
```

A CSV with numeric features and a label column → **MLP Classifier (train)**
(set `target_column` in its schema-rendered form) → wire the `model` output into
**Predict** and the `metrics` output into a File Output. Or add the core
**Train Classifier** node and pick *MLP (neural network)* in its model dropdown.
**Export → Python** emits the scikit-learn code either way. A quick dataset to
try:

```bash
python -c "from sklearn.datasets import load_iris; import pandas as pd; \
d=load_iris(as_frame=True); d.frame.rename(columns={'target':'label'}).to_csv('iris.csv', index=False)"
```

## 6. Package, sign, and bundle

Package it into a portable, signed `.ciarenplugin` (see
[Packaging & Distribution](/plugins/packaging-and-distribution)):

```bash
ciaren-plugin pack  ./mlp-classifier-plugin ./mlp.ciarenplugin
ciaren-plugin sign  ./mlp.ciarenplugin --key <private-hex> --key-id my-key-2026
ciaren-plugin verify ./mlp.ciarenplugin
```

To make it appear in your **Explore** catalog, add it to a marketplace index:

```bash
ciaren-plugin index add ./mlp.ciarenplugin --index ./marketplace.json
```

The example plugin does exactly this in
[`build_mlp_classifier_ciarenplugin.py`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/build_mlp_classifier_ciarenplugin.py):
it regenerates the manifest, packs, signs with the demo key, and copies both the
package and its index entry into the bundled catalog — which is why a fresh Ciaren
install lists the MLP Classifier in Explore next to the Hello plugin, ready to install.

## What next?

- **[Writing a Plugin](/plugins/writing-a-plugin)** — the full contract and events
- **[Installing & Managing Plugins](/plugins/managing-plugins)** — the lifecycle
- **[Plugin Security & Permissions](/security/plugin-security)** — the trust model
