---
title: Build an Advanced Plugin (scikit-learn)
description: A step-by-step guide to a realistic Ciaren plugin — a scikit-learn MLPClassifier training node with hyperparameters, thorough config validation, an executable runtime, and Python-code export.
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
Four things the Hello node skips: **multiple hyperparameters**, **input validation**
that fails fast with clear messages, an **optional third-party dependency**
(scikit-learn) imported safely, and **faithful code export** of a multi-line body.
:::

## The one design decision that shapes everything

A plugin node's runtime is **pandas in → pandas out**. Ciaren converts to and from
the active engine (pandas/polars) around your code. That means a plugin node
returns **DataFrames, not model objects** — the contract carries dataframes.

So a "train" node can't hand back a fitted estimator. Instead, ours trains *and
evaluates*, and returns a **one-row metrics DataFrame** (train/test accuracy,
iterations, loss). That fits the contract, runs on both engines, and exports
cleanly. It's the right shape for an example; for a node that persists a model,
see the built-in ML nodes and the [architecture notes](/plugins/overview).

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
version = "0.1.0"
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

```python
class MlpClassifierTrainRuntime(NodeRuntime):
    def validate_config(self, config):
        resolve_config(config)            # raise ValueError on anything unsupported

    def execute(self, inputs, config):
        import pandas as pd
        try:
            from sklearn.metrics import accuracy_score
            from sklearn.model_selection import train_test_split
            from sklearn.neural_network import MLPClassifier
        except ImportError as exc:
            raise ValueError("mlpClassifierTrain needs scikit-learn — pip install scikit-learn") from exc

        df, p = inputs["in"], resolve_config(config)
        target = p["target_column"]
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
        return {"out": pd.DataFrame([{
            "n_samples": len(df), "n_features": len(features), "n_classes": len(clf.classes_),
            "train_accuracy": float(accuracy_score(y_train, clf.predict(X_train))),
            "test_accuracy": float(accuracy_score(y_test, clf.predict(X_test))),
            "n_iterations": int(clf.n_iter_), "final_loss": float(clf.loss_),
        }])}
```

### Register the node

```python
class _MlpNodeProvider(NodeProvider):
    def nodes(self):
        return [NodeSpec(
            id="sklearn.mlpClassifierTrain",
            label="MLP Classifier (train + evaluate)",
            category="ml",
            provider="community.mlp-classifier",
            inputs=(PortSpec(id="in"),), outputs=(PortSpec(id="out"),),
            default_config=dict(DEFAULT_CONFIG),
            capabilities=("node.sklearn.mlp",),
        )]
    def node_implementations(self):
        return {"sklearn.mlpClassifierTrain": MlpClassifierTrainRuntime()}

class MlpClassifierPlugin(Plugin):
    def metadata(self):
        return PluginMetadata(id="community.mlp-classifier", name="MLP Classifier", version="0.1.0")
    def register(self, registry):
        registry.register_node_provider(_MlpNodeProvider())
```

`category="ml"` slots the node into the ML section of the palette. (Only the
built-in ML nodes are hidden when the ML extension is off; a plugin node always
shows once approved.)

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
    inp, out = input_vars["in"], output_vars["out"]
    mlp = f"{out}_mlp"
    return "\n".join([
        f"{out}_features = [c for c in {inp}.columns if c != {p['target_column']!r}]",
        f"X_tr, X_te, y_tr, y_te = train_test_split({inp}[{out}_features], {inp}[{p['target_column']!r}], "
        f"test_size={p['test_size']!r}, random_state={p['random_state']!r})",
        f"{mlp} = MLPClassifier(hidden_layer_sizes={p['hidden_layer_sizes']!r}, max_iter={p['max_iter']!r})",
        f"{mlp}.fit(X_tr, y_tr)",
        f"{out} = pd.DataFrame([{{'test_accuracy': accuracy_score(y_te, {mlp}.predict(X_te))}}])",
    ])
```

Because the runtime is pandas-based, Ciaren automatically bridges it into the
**polars** export too (wrapping with `to_pandas()` / `from_pandas()`), so both
exporters work with no extra code.

## 5. Generate the manifest and run it

Don't hand-write the manifest — generate it from the code so the two never drift:

```bash
ciaren plugin manifest ./mlp-classifier-plugin \
  --entrypoint ciaren_mlp.plugin:MlpClassifierPlugin
```

Then load it and try it on the canvas:

```bash
export CIAREN_PLUGINS_DIR=/path/to/examples/plugins
ciaren serve
```

A CSV with numeric features and a label column → **MLP Classifier (train +
evaluate)** (set `target_column`) → **Preview** shows the metrics row, and
**Export → Python** emits the scikit-learn code. A quick dataset to try:

```bash
python -c "from sklearn.datasets import load_iris; import pandas as pd; \
d=load_iris(as_frame=True); d.frame.rename(columns={'target':'label'}).to_csv('iris.csv', index=False)"
```

## 6. Package, sign, and bundle

Package it into a portable, signed `.ciarenplugin` (see
[Packaging & Distribution](/plugins/packaging-and-distribution)):

```bash
ciaren plugin pack  ./mlp-classifier-plugin ./mlp.ciarenplugin
ciaren plugin sign  ./mlp.ciarenplugin --key <private-hex> --key-id my-key-2026
ciaren plugin verify ./mlp.ciarenplugin
```

To make it appear in your **Explore** catalog, add it to a marketplace index:

```bash
ciaren plugin index add ./mlp.ciarenplugin --index ./marketplace.json
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
