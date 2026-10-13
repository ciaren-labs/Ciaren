---
title: "Train Forecaster: Current Availability"
description: "Check Ciaren Train Forecaster availability and reserved configuration. Learn why the built-in forecasting catalog is empty and how to inspect installed models."
---

# Train Forecaster — `mlTrainForecaster`

Check the node's availability before planning a forecasting flow.

## What it does

Train Forecaster is a scaffold for the `timeseries` task. The built-in catalog
currently has no forecasting estimator, so an ordinary installation has no
model to select and the default configuration cannot train a model.
It does not implement a forecast horizon, date handling or backtesting.

The scaffold shares the Train base class: a future compatible model provider
would need to supply a registered estimator for this task. Installed plugins
can extend the catalog; follow a provider's implementation and instructions
rather than assuming the reserved fields implement time-series behavior.
Do not substitute a regression model in this node: task validation rejects it.

## Configuration

These are the fields currently retained by the editor catalog. They do not
constitute a working built-in forecasting configuration.

| Config key | Editor default | Current status |
| --- | --- | --- |
| `model_type` | `""` | No built-in `timeseries` estimator; an empty value fails validation |
| `time_column` | `""` | Reserved field; no built-in time-column processing |
| `target_column` | `""` | Reserved for a provider's target configuration |
| `feature_columns` | `[]` | Shared training field; no built-in forecasting example |
| `hyperparameters` | `{}` | Provider/estimator options if a compatible model is registered |
| `seed` | `42` | Shared Train validation requires an integer seed |

Preview cannot turn the empty model selection into a trained artifact. No
model URI, forecast rows or evaluation scores can be promised for this default
configuration. Use the available classification, regression, clustering or
PCA nodes for the tasks they actually implement.

## Generated Python code

There is no runnable built-in pandas or Polars forecasting pipeline to export.
The following installed-catalog diagnostic includes any registered plugin
models. It is not a forecasting pipeline export. Run it in a Python environment
with Ciaren installed; the current built-in-only catalog prints `[]`.

```python
from app.ml.models import models_for_tasks

print(models_for_tasks(("timeseries",)))
```

A `ridge` or `random_forest_regressor` selection belongs to Train Regressor,
not Train Forecaster, and fails this node's task check.

## Tips and common mistakes

- Treat an empty picker as an unavailable capability, not a missing dataset.
- Setting a time column does not add forecasting algorithms or a horizon.
- A regression workflow on engineered time features is still a regression
  workflow. Use a deliberate time-based evaluation strategy when appropriate;
  this scaffold does not supply one.
- Check a model provider's supported task, dependencies and input contract
  before attempting to use its estimator with this node.

## See also

- [Train Regressor](./train-regressor.md)
- [Cross-Validate](./cross-validate.md)
- [ML model plugins](/plugins/ml-model-plugins)
- [ML quick start](../guide/ml-quickstart.md)
