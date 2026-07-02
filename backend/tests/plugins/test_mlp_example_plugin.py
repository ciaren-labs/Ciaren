"""The advanced MLP Classifier example plugin (API 1.1): both extension paths.

Loads the committed example plugin from its directory (the same path the loader
uses), then exercises config validation, the ModelStore-backed train node (typed
``model`` output + ``metrics`` frame), the contributed ``mlp_classifier`` model
type inside the core Train Classifier picker, Python-code export, and that its
signed package is bundled into the Explore catalog.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.plugin_api import ModelRef, NodeContext

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "examples" / "plugins" / "mlp-classifier-plugin"
BUNDLED = REPO_ROOT / "backend" / "app" / "bundled_plugins"

pytest.importorskip("sklearn", reason="the MLP plugin needs scikit-learn")


class _FakeModelStore:
    """Stands in for the host MLflow store in pure runtime tests."""

    def __init__(self) -> None:
        self.logged: list[dict] = []

    def log_sklearn_model(self, model, **kwargs) -> ModelRef:
        self.logged.append({"model": model, **kwargs})
        return ModelRef(
            task_type=kwargs["task_type"],
            model_type=kwargs["model_type"],
            mlflow_run_id="fake-run",
            model_uri="runs:/fake-run/model",
            target_column=kwargs.get("target_column"),
            feature_columns=tuple(kwargs.get("feature_columns", ())),
        )

    def load_model(self, ref_or_uri):  # pragma: no cover - unused here
        raise NotImplementedError


def _context(store: _FakeModelStore | None = None, in_preview: bool = False) -> NodeContext:
    return NodeContext(plugin_id="community.mlp-classifier", models=store, in_preview=in_preview)


@pytest.fixture(scope="module")
def runtime():
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.append(str(PLUGIN_DIR))
    from ciaren_mlp.plugin import MlpClassifierTrainRuntime

    return MlpClassifierTrainRuntime()


def _dataset(n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"f1": rng.normal(size=n), "f2": rng.normal(size=n)})
    df["label"] = (df["f1"] + df["f2"] > 0).astype(int)
    return df


@pytest.mark.parametrize(
    "config",
    [
        {},  # missing target
        {"target_column": "label", "activation": "sigmoid"},  # unsupported activation
        {"target_column": "label", "solver": "rmsprop"},  # unsupported solver
        {"target_column": "label", "max_iter": 0},  # must be > 0
        {"target_column": "label", "test_size": 0},  # must be in (0, 1)
        {"target_column": "label", "test_size": 1},
        {"target_column": "label", "alpha": -0.1},  # must be >= 0
        {"target_column": "label", "hidden_layer_sizes": "16,oops"},  # not integers
        {"target_column": "label", "hidden_layer_sizes": "0"},  # not positive
        {"target_column": "label", "feature_columns": "f1"},  # must be a list
    ],
)
def test_validate_config_rejects_unsupported(runtime, config):
    with pytest.raises(ValueError):
        runtime.validate_config(config)


def test_validate_config_accepts_supported(runtime):
    runtime.validate_config(
        {
            "target_column": "label",
            "feature_columns": ["f1", "f2"],
            "hidden_layer_sizes": "32,16",
            "activation": "tanh",
            "solver": "adam",
            "alpha": 0.001,
            "max_iter": 300,
            "test_size": 0.25,
        }
    )


def test_execute_trains_persists_and_returns_metrics(runtime):
    store = _FakeModelStore()
    out = runtime.execute_with_context(
        {"in": _dataset()},
        {"target_column": "label", "hidden_layer_sizes": "16", "max_iter": 300},
        _context(store),
    )
    # The model wire carries a typed reference, not a raw estimator.
    ref = ModelRef.from_frame(out["model"])
    assert ref.model_type == "mlp_classifier"
    assert ref.task_type == "classification"
    assert ref.model_uri == "runs:/fake-run/model"
    assert ref.feature_columns == ("f1", "f2")
    # The estimator itself went to the ModelStore (MLflow in production).
    assert len(store.logged) == 1
    assert store.logged[0]["metrics"]["test_accuracy"] >= 0.0

    row = out["metrics"].iloc[0]
    assert row["n_samples"] == 80
    assert row["n_features"] == 2
    assert row["n_classes"] == 2
    assert 0.0 <= row["test_accuracy"] <= 1.0
    # A separable dataset should train well past chance.
    assert row["train_accuracy"] > 0.7


def test_preview_skips_fitting_and_persistence(runtime):
    store = _FakeModelStore()
    out = runtime.execute_with_context(
        {"in": _dataset()},
        {"target_column": "label"},
        _context(store, in_preview=True),
    )
    assert store.logged == []  # nothing fitted, nothing persisted
    ref = ModelRef.from_frame(out["model"])
    assert ref.model_uri is None  # placeholder reference only


def test_execute_without_ml_support_gives_clear_error(runtime):
    with pytest.raises(ValueError, match="MLflow"):
        runtime.execute_with_context({"in": _dataset()}, {"target_column": "label"}, _context(store=None))


def test_execute_rejects_non_numeric_features(runtime):
    df = _dataset()
    df["f2"] = "not-a-number"
    with pytest.raises(ValueError, match="numeric"):
        runtime.execute_with_context({"in": df}, {"target_column": "label"}, _context(_FakeModelStore()))


def test_execute_rejects_missing_target(runtime):
    with pytest.raises(ValueError, match="target column"):
        runtime.execute_with_context(
            {"in": _dataset()}, {"target_column": "does_not_exist"}, _context(_FakeModelStore())
        )


def test_exported_code_is_valid_python(runtime):
    code = runtime.to_python_code(
        {"in": "df_1"},
        {"model": "df_2", "metrics": "df_3"},
        {"target_column": "label", "feature_columns": ["f1", "f2"], "hidden_layer_sizes": "16"},
    )
    assert "MLPClassifier(" in code
    assert "train_test_split(" in code
    compile(code, "<generated>", "exec")  # must be syntactically valid


# -- the contributed model type in the core train node ---------------------------


def test_build_mlp_injects_seed_and_parses_layers():
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.append(str(PLUGIN_DIR))
    from ciaren_mlp.plugin import build_mlp

    est = build_mlp({"hidden_layer_sizes": "8,4", "max_iter": 50}, seed=7)
    assert est.hidden_layer_sizes == (8, 4)
    assert est.random_state == 7
    with pytest.raises(ValueError, match="activation"):
        build_mlp({"activation": "sigmoid"}, seed=1)


# -- end-to-end through the loader/bridge ----------------------------------------


@pytest.fixture
def _loaded_plugin(monkeypatch, tmp_path):
    """Discover + bridge the MLP plugin into the engine registry (approved), with
    MLflow pointed at a per-test temp dir so the ModelStore has somewhere to log."""
    from app.plugins import get_registry, reset_registry
    from app.plugins.state import PluginStateStore

    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(PLUGIN_DIR.parent))
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    state = PluginStateStore()
    state.set_approved("community.mlp-classifier", True)
    state.save()
    reset_registry()
    get_registry()
    yield
    reset_registry()
    get_settings.cache_clear()


def _train_graph() -> dict:
    """csvInput -> MLP train; metrics -> csvOutput, model -> mlPredict -> csvOutput."""
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "mlp",
                "type": "sklearn.mlpClassifierTrain",
                "data": {"config": {"target_column": "label", "hidden_layer_sizes": "16", "max_iter": 300}},
            },
            {"id": "pred", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {"id": "metrics_out", "type": "csvOutput", "data": {"config": {}}},
            {"id": "pred_out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "mlp"},
            {"id": "e2", "source": "mlp", "sourceHandle": "metrics", "target": "metrics_out"},
            {"id": "e3", "source": "in1", "target": "pred", "targetHandle": "in"},
            {"id": "e4", "source": "mlp", "sourceHandle": "model", "target": "pred", "targetHandle": "model"},
            {"id": "e5", "source": "pred", "target": "pred_out"},
        ],
    }


def test_contributed_model_type_joins_core_catalog(_loaded_plugin):
    from app.ml.models import get_model_spec, model_catalog_status

    spec = get_model_spec("mlp_classifier")
    assert spec.task == "classification"
    row = next(r for r in model_catalog_status() if r["model_type"] == "mlp_classifier")
    assert row["provider"] == "community.mlp-classifier"
    assert row["hyperparameter_schema"]["fields"]


def test_core_train_classifier_trains_the_plugin_model(_loaded_plugin):
    from app.engine.backends import get_engine
    from app.engine.transformations.ml.train import TrainClassifierTransformation

    engine = get_engine("pandas")
    out, meta = TrainClassifierTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(_dataset(90))},
        {
            "model_type": "mlp_classifier",
            "target_column": "label",
            "seed": 7,
            "hyperparameters": {"hidden_layer_sizes": "8", "max_iter": 200},
        },
    )
    ref = ModelRef.from_frame(engine.to_pandas(out["model"]))
    assert ref.model_type == "mlp_classifier"
    assert meta is not None and meta.ml_metrics


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_runs_end_to_end_on_both_engines(_loaded_plugin, tmp_path, engine_name):
    from app.engine.executor import FlowExecutor, dataset_ref_key
    from app.engine.graph import validate_graph

    validate_graph(_train_graph())  # model wire + flow-terminal checks pass

    in_csv = tmp_path / "in.csv"
    _dataset(90).to_csv(in_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    outputs = FlowExecutor().execute(
        _train_graph(),
        dataset_paths={dataset_ref_key("ds1", None): in_csv},
        output_dir=out_dir,
        engine_name=engine_name,
    )
    metrics = pd.read_csv(outputs["metrics_out"])
    assert 0.0 <= metrics["test_accuracy"].iloc[0] <= 1.0
    assert metrics["n_features"].iloc[0] == 2

    predictions = pd.read_csv(outputs["pred_out"])
    assert "prediction" in predictions.columns
    assert set(predictions["prediction"].unique()).issubset({0, 1})


def test_exports_valid_sklearn_code_on_both_engines(_loaded_plugin):
    from app.engine.codegen import CodeGenerator
    from app.engine.polars_codegen import PolarsCodeGenerator

    graph = {
        "nodes": _train_graph()["nodes"][:2] + [{"id": "m_out", "type": "csvOutput", "data": {"config": {}}}],
        "edges": [
            {"id": "e1", "source": "in1", "target": "mlp"},
            {"id": "e2", "source": "mlp", "sourceHandle": "metrics", "target": "m_out"},
        ],
    }
    pandas_code = CodeGenerator().generate(graph, {"ds1": "in.csv"})
    polars_code = PolarsCodeGenerator().generate(graph, {"ds1": "in.csv"})
    assert "from sklearn.neural_network import MLPClassifier" in pandas_code
    assert "MLPClassifier(" in polars_code and "to_pandas()" in polars_code  # bridged into polars
    compile(pandas_code, "<pandas>", "exec")
    compile(polars_code, "<polars>", "exec")


def test_signed_package_is_bundled_in_catalog():
    """The build scripts ship signed packages + catalog entries so a fresh install
    lists the examples in Explore, ready to install."""
    import json

    from app.plugins.package import read_manifest, verify_package

    pkg = BUNDLED / "community.mlp-classifier-0.2.0.ciarenplugin"
    assert pkg.is_file(), "run examples/plugins/build_mlp_classifier_ciarenplugin.py"
    manifest = read_manifest(pkg)
    assert manifest.id == "community.mlp-classifier"
    assert "model.mlp_classifier" in manifest.capabilities

    demo_key = {"ciaren-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}
    assert verify_package(pkg, trusted_keys=demo_key).outcome == "trusted"

    catalog = json.loads((BUNDLED / "marketplace.json").read_text(encoding="utf-8"))
    ids = {e["id"] for e in catalog["plugins"]}
    assert {"community.hello", "community.mlp-classifier", "community.rest-connector"} <= ids
