"""The MLP Classifier plugin: a neural-network classifier for Ciaren, twice over.

This is the "advanced" companion to the Hello plugin, and it demonstrates both of
the ML extension points added in plugin API 1.1:

1. **A model type for the core Train Classifier node** (``ModelProvider``): the
   ``mlp_classifier`` model type appears in the standard *Train Classifier* model
   picker next to the built-ins, and trains through the exact same pipeline —
   preprocessing bundled into the sklearn ``Pipeline``, hyperparameter
   sanitization, size limits, MLflow logging, and code export. The plugin only
   supplies the estimator builder and the hyperparameter form schema.

2. **A standalone train node** (``sklearn.mlpClassifierTrain``): a plugin node
   with a typed ``model`` output. It fits an ``MLPClassifier``, persists it
   through the host's :class:`ModelStore` (``context.models`` — an MLflow
   artifact, never a raw pickle on the wire), and emits:

   - ``model``  — a one-row :class:`ModelRef` frame the core **Predict** /
     **Feature Importance** nodes consume directly, and
   - ``metrics`` — a one-row train/test metrics summary you can wire to any
     output.

   Its sidebar form is driven by the ``config_schema`` declared on the node spec
   (no frontend code needed), and it skips fitting during editor previews
   (``context.in_preview``), exactly like the core train nodes.

scikit-learn/numpy are imported lazily inside ``execute``/``to_python_code`` so
the plugin still registers and appears in the catalog where scikit-learn is not
installed; running then raises a clear "install scikit-learn" error.
"""

from __future__ import annotations

from typing import Any

from app.plugin_api import (
    ModelProvider,
    ModelTypeSpec,
    NodeContext,
    NodeProvider,
    NodeRuntime,
    NodeSpec,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)
from app.plugin_api.model_ref import ModelRef

PLUGIN_ID = "community.mlp-classifier"
NODE_ID = "sklearn.mlpClassifierTrain"
MODEL_TYPE = "mlp_classifier"

#: Hyperparameter value sets we support, validated up front so the UI (and export)
#: fail fast with a clear message instead of deep inside scikit-learn.
ACTIVATIONS = ("identity", "logistic", "tanh", "relu")
SOLVERS = ("lbfgs", "sgd", "adam")

DEFAULT_CONFIG: dict[str, Any] = {
    "target_column": "",
    "feature_columns": [],
    "hidden_layer_sizes": "100",
    "activation": "relu",
    "solver": "adam",
    "alpha": 0.0001,
    "learning_rate_init": 0.001,
    "max_iter": 200,
    "test_size": 0.2,
    "random_state": 42,
    "stratify": True,
}

#: The node's sidebar form — rendered by Ciaren from this schema, no frontend code.
CONFIG_SCHEMA: dict[str, Any] = {
    "fields": [
        {"key": "target_column", "label": "Target column", "type": "column", "required": True},
        {
            "key": "feature_columns",
            "label": "Feature columns",
            "type": "column_list",
            "help": "Empty = every numeric column except the target.",
        },
        {
            "key": "hidden_layer_sizes",
            "label": "Hidden layers",
            "type": "string",
            "default": "100",
            "placeholder": "64,32",
            "help": "Comma-separated layer sizes, e.g. 64,32.",
        },
        {"key": "activation", "label": "Activation", "type": "select", "options": list(ACTIVATIONS), "default": "relu"},
        {"key": "solver", "label": "Solver", "type": "select", "options": list(SOLVERS), "default": "adam"},
        {"key": "alpha", "label": "L2 penalty (alpha)", "type": "number", "min": 0, "default": 0.0001},
        {"key": "learning_rate_init", "label": "Learning rate", "type": "number", "default": 0.001},
        {"key": "max_iter", "label": "Max iterations", "type": "integer", "min": 1, "default": 200},
        {"key": "test_size", "label": "Test split", "type": "number", "min": 0.05, "max": 0.95, "default": 0.2},
        {"key": "random_state", "label": "Random seed", "type": "integer", "default": 42},
        {"key": "stratify", "label": "Stratify the split", "type": "boolean", "default": True},
    ]
}

#: Hyperparameters for the mlp_classifier *model type* (used inside the core
#: Train Classifier node, which supplies target/features/seed itself).
HYPERPARAMETER_SCHEMA: dict[str, Any] = {
    "fields": [
        {
            "key": "hidden_layer_sizes",
            "label": "Hidden layers",
            "type": "string",
            "default": "100",
            "placeholder": "64,32",
            "help": "Comma-separated layer sizes, e.g. 64,32.",
        },
        {"key": "activation", "label": "Activation", "type": "select", "options": list(ACTIVATIONS), "default": "relu"},
        {"key": "solver", "label": "Solver", "type": "select", "options": list(SOLVERS), "default": "adam"},
        {"key": "alpha", "label": "L2 penalty (alpha)", "type": "number", "min": 0, "default": 0.0001},
        {"key": "max_iter", "label": "Max iterations", "type": "integer", "min": 1, "default": 200},
    ]
}


def _as_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"mlpClassifierTrain: {name!r} must be a number, got {value!r}") from exc


def _as_int(value: Any, name: str) -> int:
    try:
        # Reject 1.5 rather than silently truncating it.
        f = float(value)
        if f != int(f):
            raise ValueError
        return int(f)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"mlpClassifierTrain: {name!r} must be an integer, got {value!r}") from exc


def parse_hidden_layers(value: Any) -> tuple[int, ...]:
    """Coerce ``hidden_layer_sizes`` (an int, a list, or a ``"64,32"`` string) into a
    tuple of positive ints — the shape scikit-learn's ``MLPClassifier`` expects."""
    if isinstance(value, bool):  # bool is an int subclass; reject it explicitly
        raise ValueError("mlpClassifierTrain: 'hidden_layer_sizes' must be integers, not a boolean")
    if isinstance(value, int):
        items: list[Any] = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    elif isinstance(value, str):
        items = [p.strip() for p in value.split(",") if p.strip()]
    else:
        raise ValueError(f"mlpClassifierTrain: 'hidden_layer_sizes' has an unsupported type: {type(value).__name__}")
    sizes = [_as_int(n, "hidden_layer_sizes") for n in items]
    if not sizes or any(n <= 0 for n in sizes):
        raise ValueError("mlpClassifierTrain: 'hidden_layer_sizes' must be one or more positive integers, e.g. '64,32'")
    return tuple(sizes)


def resolve_config(config: dict[str, Any]) -> dict[str, Any]:
    """Merge with defaults and validate every field, returning typed values.

    Raising here (rather than deep inside scikit-learn) is what makes the node's
    validation legible in the editor and keeps ``to_python_code`` and ``execute`` in
    agreement about what a valid config is."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    target = str(cfg["target_column"]).strip()
    if not target:
        raise ValueError("mlpClassifierTrain: 'target_column' is required")

    features = cfg["feature_columns"] or []
    if not isinstance(features, (list, tuple)) or not all(isinstance(c, str) for c in features):
        raise ValueError("mlpClassifierTrain: 'feature_columns' must be a list of column names (or empty for all)")

    activation = str(cfg["activation"])
    if activation not in ACTIVATIONS:
        raise ValueError(f"mlpClassifierTrain: 'activation' must be one of {ACTIVATIONS}, got {activation!r}")
    solver = str(cfg["solver"])
    if solver not in SOLVERS:
        raise ValueError(f"mlpClassifierTrain: 'solver' must be one of {SOLVERS}, got {solver!r}")

    alpha = _as_float(cfg["alpha"], "alpha")
    if alpha < 0:
        raise ValueError("mlpClassifierTrain: 'alpha' must be >= 0")
    learning_rate_init = _as_float(cfg["learning_rate_init"], "learning_rate_init")
    if learning_rate_init <= 0:
        raise ValueError("mlpClassifierTrain: 'learning_rate_init' must be > 0")
    max_iter = _as_int(cfg["max_iter"], "max_iter")
    if max_iter <= 0:
        raise ValueError("mlpClassifierTrain: 'max_iter' must be > 0")
    test_size = _as_float(cfg["test_size"], "test_size")
    if not 0.0 < test_size < 1.0:
        raise ValueError("mlpClassifierTrain: 'test_size' must be between 0 and 1 (exclusive)")

    return {
        "target_column": target,
        "feature_columns": list(features),
        "hidden_layer_sizes": parse_hidden_layers(cfg["hidden_layer_sizes"]),
        "activation": activation,
        "solver": solver,
        "alpha": alpha,
        "learning_rate_init": learning_rate_init,
        "max_iter": max_iter,
        "test_size": test_size,
        "random_state": _as_int(cfg["random_state"], "random_state"),
        "stratify": bool(cfg["stratify"]),
    }


def build_mlp(hyperparameters: dict[str, Any], seed: int | None) -> Any:
    """Estimator builder for the ``mlp_classifier`` model type (core train nodes).

    Receives already-sanitized, JSON-native hyperparameters; coerces the friendly
    ``"64,32"`` layer syntax and injects the run seed unless the user set one."""
    try:
        from sklearn.neural_network import MLPClassifier
    except ImportError as exc:  # pragma: no cover - exercised only without sklearn
        raise ValueError("mlp_classifier needs scikit-learn — install it with `pip install scikit-learn`") from exc

    params = dict(hyperparameters or {})
    if "hidden_layer_sizes" in params:
        params["hidden_layer_sizes"] = parse_hidden_layers(params["hidden_layer_sizes"])
    if "activation" in params and params["activation"] not in ACTIVATIONS:
        raise ValueError(f"mlp_classifier: 'activation' must be one of {ACTIVATIONS}")
    if "solver" in params and params["solver"] not in SOLVERS:
        raise ValueError(f"mlp_classifier: 'solver' must be one of {SOLVERS}")
    if "max_iter" in params:
        params["max_iter"] = _as_int(params["max_iter"], "max_iter")
    if seed is not None and "random_state" not in params:
        params["random_state"] = seed
    return MLPClassifier(**params)


class MlpClassifierTrainRuntime(NodeRuntime):
    """Trains an ``MLPClassifier`` and emits a model reference + metrics summary."""

    def validate_config(self, config: dict[str, Any]) -> None:
        resolve_config(config)  # raises ValueError on anything we don't support

    def execute_with_context(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: NodeContext,
    ) -> dict[str, Any]:
        import pandas as pd

        p = resolve_config(config)
        target = p["target_column"]

        # Editor previews run on sampled data and must not fit or persist a
        # model — hand downstream a placeholder reference, like the core nodes.
        if context.in_preview:
            placeholder = ModelRef(
                task_type="classification",
                model_type=MODEL_TYPE,
                target_column=target,
                feature_columns=tuple(p["feature_columns"]),
            )
            return {"model": placeholder.to_frame(), "metrics": pd.DataFrame()}

        try:
            from sklearn.metrics import accuracy_score
            from sklearn.model_selection import train_test_split
            from sklearn.neural_network import MLPClassifier
        except ImportError as exc:  # pragma: no cover - exercised only without sklearn
            raise ValueError(
                "mlpClassifierTrain needs scikit-learn — install it with `pip install scikit-learn`"
            ) from exc

        df = inputs["in"]
        if target not in df.columns:
            raise ValueError(f"mlpClassifierTrain: target column {target!r} is not in the input {list(df.columns)}")

        features = p["feature_columns"] or [c for c in df.columns if c != target]
        missing = [c for c in features if c not in df.columns]
        if missing:
            raise ValueError(f"mlpClassifierTrain: feature columns not found in the input: {missing}")
        if not features:
            raise ValueError("mlpClassifierTrain: there are no feature columns to train on")
        non_numeric = [c for c in features if not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            raise ValueError(f"mlpClassifierTrain: feature columns must be numeric; non-numeric: {non_numeric}")

        X, y = df[features], df[target]
        # Stratify only when it is actually valid (>1 class, every class has >= 2 rows);
        # otherwise scikit-learn would raise, so fall back to a plain split.
        stratify = y if p["stratify"] and y.nunique() > 1 and y.value_counts().min() >= 2 else None
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=p["test_size"], random_state=p["random_state"], stratify=stratify
        )
        clf = MLPClassifier(
            hidden_layer_sizes=p["hidden_layer_sizes"],
            activation=p["activation"],
            solver=p["solver"],
            alpha=p["alpha"],
            learning_rate_init=p["learning_rate_init"],
            max_iter=p["max_iter"],
            random_state=p["random_state"],
        )
        clf.fit(X_train, y_train)

        metrics = {
            "n_samples": int(len(df)),
            "n_features": int(len(features)),
            "n_classes": int(len(clf.classes_)),
            "train_accuracy": float(accuracy_score(y_train, clf.predict(X_train))),
            "test_accuracy": float(accuracy_score(y_test, clf.predict(X_test))),
            "n_iterations": int(clf.n_iter_),
            "final_loss": float(clf.loss_),
        }

        if context.models is None:
            raise ValueError(
                "mlpClassifierTrain: this server has no ML/MLflow support installed, "
                "so the trained model cannot be persisted (install ciaren[ml])."
            )
        # The sanctioned persistence path: the fitted estimator becomes an MLflow
        # artifact; only the typed reference travels through the graph.
        # params land in the reference's model_config_json as the recorded
        # hyperparameters — keep them builder-compatible (the "64,32" layer
        # syntax build_mlp accepts) so core Cross-Validate can rebuild this
        # estimator from the reference alone.
        ref = context.models.log_sklearn_model(
            clf,
            model_type=MODEL_TYPE,
            task_type="classification",
            target_column=target,
            feature_columns=tuple(features),
            params={
                "hidden_layer_sizes": ",".join(str(n) for n in p["hidden_layer_sizes"]),
                "activation": p["activation"],
                "solver": p["solver"],
                "alpha": p["alpha"],
                "learning_rate_init": p["learning_rate_init"],
                "max_iter": p["max_iter"],
            },
            metrics={"train_accuracy": metrics["train_accuracy"], "test_accuracy": metrics["test_accuracy"]},
            input_example=X_train.head(5),
            seed=p["random_state"],
        )
        return {"model": ref.to_frame(), "metrics": pd.DataFrame([metrics])}

    def imports(self, config: dict[str, Any]) -> list[str]:
        return [
            "from sklearn.metrics import accuracy_score",
            "from sklearn.model_selection import train_test_split",
            "from sklearn.neural_network import MLPClassifier",
        ]

    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        p = resolve_config(config)
        inp = input_vars["in"]
        model_var = output_vars.get("model", "mlp_model")
        metrics_var = output_vars.get("metrics", "mlp_metrics")
        # Unique helper names (derived from the model var) so two train nodes in
        # one flow can't collide in the exported script.
        feat = f"{model_var}_features"
        x_tr, x_te = f"{model_var}_X_train", f"{model_var}_X_test"
        y_tr, y_te = f"{model_var}_y_train", f"{model_var}_y_test"
        target = p["target_column"]
        feat_expr = (
            repr(list(p["feature_columns"]))
            if p["feature_columns"]
            else f"[c for c in {inp}.columns if c != {target!r}]"
        )
        stratify_expr = f"{inp}[{target!r}]" if p["stratify"] else "None"
        return "\n".join(
            [
                f"{feat} = {feat_expr}",
                f"{x_tr}, {x_te}, {y_tr}, {y_te} = train_test_split(",
                f"    {inp}[{feat}], {inp}[{target!r}],",
                f"    test_size={p['test_size']!r}, random_state={p['random_state']!r}, stratify={stratify_expr},",
                ")",
                f"{model_var} = MLPClassifier(",
                f"    hidden_layer_sizes={p['hidden_layer_sizes']!r}, activation={p['activation']!r}, "
                f"solver={p['solver']!r},",
                f"    alpha={p['alpha']!r}, learning_rate_init={p['learning_rate_init']!r}, "
                f"max_iter={p['max_iter']!r},",
                f"    random_state={p['random_state']!r},",
                ")",
                f"{model_var}.fit({x_tr}, {y_tr})",
                f"{metrics_var} = pd.DataFrame([{{",
                f"    'n_samples': len({inp}),",
                f"    'n_features': len({feat}),",
                f"    'n_classes': len({model_var}.classes_),",
                f"    'train_accuracy': accuracy_score({y_tr}, {model_var}.predict({x_tr})),",
                f"    'test_accuracy': accuracy_score({y_te}, {model_var}.predict({x_te})),",
                f"    'n_iterations': {model_var}.n_iter_,",
                f"    'final_loss': {model_var}.loss_,",
                "}])",
            ]
        )


class _MlpNodeProvider(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id=NODE_ID,
                label="MLP Classifier (train)",
                category="ml",
                description=(
                    "Trains a scikit-learn MLPClassifier, persists it to MLflow, and emits "
                    "a typed model reference (for Predict / Feature Importance) plus a "
                    "train/test metrics summary."
                ),
                provider=PLUGIN_ID,
                version="0.2.0",
                inputs=(PortSpec(id="in"),),
                outputs=(
                    PortSpec(id="model", type="model"),
                    PortSpec(id="metrics"),
                ),
                default_config=dict(DEFAULT_CONFIG),
                capabilities=("node.sklearn.mlp",),
                is_model_sink=True,
                is_flow_terminal=True,
                config_schema=CONFIG_SCHEMA,
            )
        ]

    def node_implementations(self) -> dict[str, Any]:
        return {NODE_ID: MlpClassifierTrainRuntime()}


class _MlpModelProvider(ModelProvider):
    def model_types(self) -> list[ModelTypeSpec]:
        return [
            ModelTypeSpec(
                id=MODEL_TYPE,
                label="MLP (neural network)",
                task="classification",
                supervised=True,
                provider=PLUGIN_ID,
                description="Multi-layer perceptron classifier (scikit-learn MLPClassifier).",
                requires=("sklearn",),
                install_hint="pip install scikit-learn",
                default_hyperparameters={"hidden_layer_sizes": "100", "max_iter": 200},
                hyperparameter_schema=HYPERPARAMETER_SCHEMA,
                import_lines=("from sklearn.neural_network import MLPClassifier",),
            )
        ]

    def model_builders(self) -> dict[str, Any]:
        return {MODEL_TYPE: build_mlp}


class MlpClassifierPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="MLP Classifier",
            version="0.2.0",
            publisher="community",
            description=(
                "Neural-network classification for Ciaren: adds the mlp_classifier model "
                "type to the core Train Classifier node and a standalone MLP train node "
                "that emits a typed model reference."
            ),
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_MlpNodeProvider())
        registry.register_model_provider(_MlpModelProvider())
