"""The MLP Classifier plugin: train and evaluate a scikit-learn ``MLPClassifier``.

It contributes one node, ``sklearn.mlpClassifierTrain``, that trains a multi-layer
perceptron classifier on the input frame and outputs a one-row **metrics summary**
(train/test accuracy, iterations, final loss, …). It is the "advanced" companion to
the Hello plugin: it shows a realistic plugin node with several **hyperparameters**,
thorough **config validation**, an executable pandas runtime, and Python-code export
that reproduces the training with scikit-learn.

Design notes:

- The node stays within the plugin runtime contract (**pandas in → pandas out**), so
  Ciaren runs it end-to-end and exports it on both the pandas and polars engines. It
  therefore emits a *metrics report*, not a raw model object (the plugin contract
  carries dataframes, not estimators).
- ``scikit-learn``/``numpy`` are imported **lazily** inside ``execute``/``to_python_code``
  so the plugin still registers and appears in the catalog where scikit-learn is not
  installed; running the node then raises a clear "install scikit-learn" error.
"""

from __future__ import annotations

from typing import Any

from app.plugin_api import (
    NodeProvider,
    NodeRuntime,
    NodeSpec,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)

PLUGIN_ID = "community.mlp-classifier"
NODE_ID = "sklearn.mlpClassifierTrain"

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


class MlpClassifierTrainRuntime(NodeRuntime):
    """Trains an ``MLPClassifier`` and returns a metrics summary frame."""

    def validate_config(self, config: dict[str, Any]) -> None:
        resolve_config(config)  # raises ValueError on anything we don't support

    def execute(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        import pandas as pd

        try:
            from sklearn.metrics import accuracy_score
            from sklearn.model_selection import train_test_split
            from sklearn.neural_network import MLPClassifier
        except ImportError as exc:  # pragma: no cover - exercised only without sklearn
            raise ValueError(
                "mlpClassifierTrain needs scikit-learn — install it with `pip install scikit-learn`"
            ) from exc

        df = inputs["in"]
        p = resolve_config(config)
        target = p["target_column"]
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
        metrics = pd.DataFrame(
            [
                {
                    "n_samples": int(len(df)),
                    "n_features": int(len(features)),
                    "n_classes": int(len(clf.classes_)),
                    "train_accuracy": float(accuracy_score(y_train, clf.predict(X_train))),
                    "test_accuracy": float(accuracy_score(y_test, clf.predict(X_test))),
                    "n_iterations": int(clf.n_iter_),
                    "final_loss": float(clf.loss_),
                    # Stored as text so the cell survives the pandas→polars bridge tidily.
                    "hidden_layer_sizes": "x".join(str(n) for n in p["hidden_layer_sizes"]),
                    "activation": p["activation"],
                    "solver": p["solver"],
                }
            ]
        )
        return {"out": metrics}

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
        inp, out = input_vars["in"], output_vars["out"]
        # Unique helper names (derived from the output var) so two train nodes in one
        # flow can't collide in the exported script.
        feat, mlp = f"{out}_features", f"{out}_mlp"
        x_tr, x_te = f"{out}_X_train", f"{out}_X_test"
        y_tr, y_te = f"{out}_y_train", f"{out}_y_test"
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
                f"{mlp} = MLPClassifier(",
                f"    hidden_layer_sizes={p['hidden_layer_sizes']!r}, activation={p['activation']!r}, "
                f"solver={p['solver']!r},",
                f"    alpha={p['alpha']!r}, learning_rate_init={p['learning_rate_init']!r}, "
                f"max_iter={p['max_iter']!r},",
                f"    random_state={p['random_state']!r},",
                ")",
                f"{mlp}.fit({x_tr}, {y_tr})",
                f"{out} = pd.DataFrame([{{",
                f"    'n_samples': len({inp}),",
                f"    'n_features': len({feat}),",
                f"    'n_classes': len({mlp}.classes_),",
                f"    'train_accuracy': accuracy_score({y_tr}, {mlp}.predict({x_tr})),",
                f"    'test_accuracy': accuracy_score({y_te}, {mlp}.predict({x_te})),",
                f"    'n_iterations': {mlp}.n_iter_,",
                f"    'final_loss': {mlp}.loss_,",
                "}])",
            ]
        )


class _MlpNodeProvider(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id=NODE_ID,
                label="MLP Classifier (train + evaluate)",
                category="ml",
                description=(
                    "Trains a scikit-learn MLPClassifier on the input and outputs a "
                    "metrics summary (train/test accuracy, iterations, final loss)."
                ),
                provider=PLUGIN_ID,
                version="0.1.0",
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="out"),),
                default_config=dict(DEFAULT_CONFIG),
                capabilities=("node.sklearn.mlp",),
            )
        ]

    def node_implementations(self) -> dict[str, Any]:
        return {NODE_ID: MlpClassifierTrainRuntime()}


class MlpClassifierPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="MLP Classifier",
            version="0.1.0",
            publisher="community",
            description="Train and evaluate a scikit-learn MLPClassifier from a node on the canvas.",
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_MlpNodeProvider())
