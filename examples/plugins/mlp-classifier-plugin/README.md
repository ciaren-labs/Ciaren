# MLP Classifier — advanced example Ciaren plugin

A realistic, non-trivial plugin. It contributes one node,
`sklearn.mlpClassifierTrain`, that trains a scikit-learn
[`MLPClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html)
on the input data and outputs a **metrics summary** (train/test accuracy,
iterations, final loss).

Where the [Hello plugin](../hello-node-plugin/) is the smallest thing that works,
this one shows what a production-shaped plugin looks like:

- **Several hyperparameters** — `hidden_layer_sizes`, `activation`, `solver`,
  `alpha`, `learning_rate_init`, `max_iter`, `test_size`, `random_state`, `stratify`.
- **Thorough config validation** — every hyperparameter is checked with a clear
  error before scikit-learn ever runs (`resolve_config`), so the editor and the
  exported code agree on what is valid.
- **An executable runtime** — trains and evaluates on pandas, so it runs in preview
  and runs on both the pandas and polars engines.
- **Python-code export** — `to_python_code` emits real, runnable scikit-learn code.

## What it outputs

The node returns a **one-row DataFrame**, not a model object — the plugin runtime
contract carries dataframes, not estimators. That row summarizes the run:

| column | meaning |
|--------|---------|
| `n_samples`, `n_features`, `n_classes` | shape of the training problem |
| `train_accuracy`, `test_accuracy` | accuracy on the train / held-out split |
| `n_iterations`, `final_loss` | optimizer iterations and final training loss |
| `hidden_layer_sizes`, `activation`, `solver` | the hyperparameters used |

## Requirements

The node needs **numeric feature columns** and a **target column** to predict.
`scikit-learn` (and `pandas`) must be installed — `pip install .` pulls them in.
scikit-learn is imported lazily, so the node still appears in the catalog without
it and only errors (with a clear message) when you run it.

## Try it

**Local directory (no install):** point Ciaren at the parent directory:

```bash
export CIAREN_PLUGINS_DIR=/path/to/examples/plugins
ciaren serve
```

Then on the canvas: a **CSV Input** with numeric feature columns and a label
column → **MLP Classifier (train + evaluate)** (set `target_column`) → **Preview**.
You'll see the metrics row. **Export → Python** emits the scikit-learn training code.

A tiny dataset to try it on (`iris`-style, all numeric):

```bash
python -c "from sklearn.datasets import load_iris; import pandas as pd; \
d=load_iris(as_frame=True); df=d.frame.rename(columns={'target':'label'}); \
df.to_csv('iris.csv', index=False)"
```

Set `target_column` to `label` and leave `feature_columns` empty to use the rest.

## Signed `.ciarenplugin` package

A pre-built, **signed** package ships in [`../dist/`](../dist/) and is bundled into
the Explore catalog, so a fresh Ciaren install lists it ready to install (alongside
the Hello plugin). It is signed with the same throwaway **demo** key as the Hello
example. Rebuild after editing:

```bash
python examples/plugins/build_mlp_classifier_ciarenplugin.py
```

## How it was built, step by step

See the tutorial: **[Build an Advanced Plugin (scikit-learn)](../../../docs/plugins/advanced-plugin-sklearn.md)**.
