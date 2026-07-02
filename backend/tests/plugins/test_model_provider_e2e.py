"""End-to-end: plugin-provided ML capabilities.

Two extension paths are covered:

1. **ModelProvider** — a plugin contributes a model *type* that appears in the
   core model catalog and trains through the existing task-scoped train nodes
   (mlTrainClassifier), including MLflow logging and code export.
2. **Plugin train node** — a plugin node with a typed ``model`` output persists
   through the host ModelStore (``context.models``) and its ModelRef frame feeds
   the core ``mlPredict``, with graph validation enforcing the model wire.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine import node_kinds
from app.engine.backends import get_engine
from app.engine.graph import GraphValidationError, validate_graph
from app.engine.registry import list_transformation_types
from app.ml.availability import ml_core_available
from app.plugin_api import ModelProvider, ModelRef, ModelTypeSpec
from app.plugins import get_registry, reset_registry

pytestmark = pytest.mark.skipif(not ml_core_available(), reason="ML core libraries not installed")

PLUGIN_ID = "community.stub-ml"
NODE_ID = "stub.treeTrain"


@pytest.fixture
def ml_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def classification_df(n=80, seed=0):
    rng = np.random.RandomState(seed)
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    return pd.DataFrame({"x1": x1, "x2": x2, "target": (x1 + x2 > 0).astype(int)})


# -- 1. ModelProvider: a plugin model type in the core train node ----------------


class _StubModels(ModelProvider):
    def model_types(self) -> list[ModelTypeSpec]:
        return [
            ModelTypeSpec(
                id="stub_tree",
                label="Stub Decision Tree",
                task="classification",
                provider=PLUGIN_ID,
                requires=("sklearn",),
                default_hyperparameters={"max_depth": 3},
            ),
            # Same estimator, but with explicitly declared export imports.
            ModelTypeSpec(
                id="stub_tree_imports",
                label="Stub Tree (declared imports)",
                task="classification",
                provider=PLUGIN_ID,
                requires=("sklearn",),
                import_lines=("from acme_ml.compat import DecisionTreeClassifier",),
            ),
        ]

    def model_builders(self) -> dict[str, Any]:
        def build(params: dict[str, Any], seed: int | None) -> Any:
            from sklearn.tree import DecisionTreeClassifier

            merged = dict(params)
            if seed is not None and "random_state" not in merged:
                merged["random_state"] = seed
            return DecisionTreeClassifier(**merged)

        return {"stub_tree": build, "stub_tree_imports": build}


@pytest.fixture
def stub_model_registered():
    get_registry().register_model_provider(_StubModels())
    yield
    reset_registry()


def test_plugin_model_type_joins_the_catalog(stub_model_registered):
    from app.ml.models import get_model_spec, model_catalog_status, models_for_tasks

    spec = get_model_spec("stub_tree")
    assert spec.task == "classification"
    assert spec.supervised is True
    assert "stub_tree" in models_for_tasks(("classification",))

    row = next(r for r in model_catalog_status() if r["model_type"] == "stub_tree")
    assert row["provider"] == PLUGIN_ID
    assert row["label"] == "Stub Decision Tree"
    assert row["available"] is True
    assert row["default_hyperparameters"] == {"max_depth": 3}


def test_unknown_model_type_lists_plugin_types_in_error(stub_model_registered):
    from app.ml.models import get_model_spec

    with pytest.raises(ValueError, match="stub_tree"):
        get_model_spec("no_such_model")


def test_plugin_model_type_disappears_after_registry_reset(stub_model_registered):
    from app.ml.models import get_model_spec

    assert get_model_spec("stub_tree") is not None
    reset_registry()
    with pytest.raises(ValueError, match="Unknown model_type"):
        get_model_spec("stub_tree")


def test_core_train_node_trains_a_plugin_model_type(ml_env, stub_model_registered):
    from app.engine.transformations.ml.train import TrainClassifierTransformation

    engine = get_engine("pandas")
    df = classification_df()
    out, meta = TrainClassifierTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(df)},
        {"model_type": "stub_tree", "target_column": "target", "seed": 7},
    )
    ref = ModelRef.from_frame(engine.to_pandas(out["model"]))
    assert ref.model_type == "stub_tree"
    assert ref.task_type == "classification"
    assert ref.model_uri, "the trained model must be persisted to MLflow"
    assert meta is not None and meta.ml_metrics

    # The reference loads back and predicts through the core loader path.
    from app.ml.loader import load_model

    pipeline = load_model(ref.model_uri)
    preds = pipeline.predict(df[["x1", "x2"]])
    assert len(preds) == len(df)


def test_core_train_node_exports_code_for_plugin_model_type(stub_model_registered):
    from app.engine.transformations.ml.train import TrainClassifierTransformation

    node = TrainClassifierTransformation()
    config = {"model_type": "stub_tree", "target_column": "target", "seed": 7}
    code = node.to_python_code({"in": "df"}, {"model": "model"}, config)
    assert "DecisionTreeClassifier" in code
    imports = node.imports(config)
    assert "from sklearn.tree import DecisionTreeClassifier" in imports


def test_declared_default_hyperparameters_apply_when_form_untouched(stub_model_registered):
    """The catalog advertises default_hyperparameters — an untouched form ({})
    must train with them, and explicit values must win over them."""
    from app.ml.models import build_estimator

    est = build_estimator("stub_tree", {}, 7)
    assert est.max_depth == 3
    assert est.random_state == 7
    assert build_estimator("stub_tree", {"max_depth": 5}, 7).max_depth == 5

    # The defaults surface in exported code too (repr of the built estimator).
    from app.engine.transformations.ml.train import TrainClassifierTransformation

    code = TrainClassifierTransformation().to_python_code(
        {"in": "df"}, {"model": "model"}, {"model_type": "stub_tree", "target_column": "target", "seed": 7}
    )
    assert "max_depth=3" in code


def test_declared_import_lines_replace_the_derived_estimator_import(stub_model_registered):
    from app.engine.transformations.ml.train import TrainClassifierTransformation

    config = {"model_type": "stub_tree_imports", "target_column": "target", "seed": 7}
    imports = TrainClassifierTransformation().imports(config)
    assert "from acme_ml.compat import DecisionTreeClassifier" in imports
    assert "from sklearn.tree import DecisionTreeClassifier" not in imports


def test_plugin_builder_missing_module_gives_install_hint():
    class _NeedsMissing(ModelProvider):
        def model_types(self) -> list[ModelTypeSpec]:
            return [
                ModelTypeSpec(
                    id="ghost_model",
                    label="Ghost",
                    task="classification",
                    provider=PLUGIN_ID,
                    requires=("nonexistent_module_xyz",),
                    install_hint="pip install ghost-ml",
                )
            ]

        def model_builders(self) -> dict[str, Any]:
            return {"ghost_model": lambda params, seed: None}

    get_registry().register_model_provider(_NeedsMissing())
    try:
        from app.ml.models import build_estimator, model_catalog_status

        row = next(r for r in model_catalog_status() if r["model_type"] == "ghost_model")
        assert row["available"] is False
        assert "ghost-ml" in row["warning"]
        with pytest.raises(RuntimeError, match="ghost-ml"):
            build_estimator("ghost_model", {}, 1)
    finally:
        reset_registry()


# -- 2. A plugin train node: ModelStore + model wire ------------------------------

PLUGIN_MODULE = """
from typing import Any

from app.plugin_api import (
    NodeContext,
    NodeProvider,
    NodeRuntime,
    NodeSpec,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)

PLUGIN_ID = "community.stub-ml"
NODE_ID = "stub.treeTrain"


class StubTrainRuntime(NodeRuntime):
    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("target_column"):
            raise ValueError("stub.treeTrain requires a target_column")

    def execute_with_context(self, inputs, config, context: NodeContext):
        from sklearn.tree import DecisionTreeClassifier

        df = inputs["in"]
        target = config["target_column"]
        features = [c for c in df.columns if c != target]
        est = DecisionTreeClassifier(max_depth=3, random_state=0)
        est.fit(df[features], df[target])
        if context.models is None:
            raise ValueError("stub.treeTrain: this server has no ML/MLflow support")
        ref = context.models.log_sklearn_model(
            est,
            model_type="stub_tree",
            task_type="classification",
            target_column=target,
            feature_columns=tuple(features),
            metrics={"train_accuracy": float(est.score(df[features], df[target]))},
        )
        return {"model": ref.to_frame()}


class _Nodes(NodeProvider):
    def nodes(self):
        return [
            NodeSpec(
                id=NODE_ID,
                label="Stub Tree Train",
                category="ml",
                provider=PLUGIN_ID,
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="model", type="model"),),
                default_config={"target_column": ""},
                is_model_sink=True,
                is_flow_terminal=True,
                config_schema={"fields": [{"key": "target_column", "type": "column", "required": True}]},
            )
        ]

    def node_implementations(self):
        return {NODE_ID: StubTrainRuntime()}


class StubMlPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(id=PLUGIN_ID, name="Stub ML")

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_Nodes())
"""

MANIFEST = {
    "id": PLUGIN_ID,
    "name": "Stub ML",
    "version": "0.1.0",
    "ciaren": ">=0.1",
    "entrypoint": "stub_ml.plugin:StubMlPlugin",
    "ui": {"nodes": [NODE_ID]},
}


@pytest.fixture
def stub_plugin_loaded(tmp_path, monkeypatch, ml_env):
    """Write the stub plugin to disk and load it through the real discovery path
    (manifest validation -> approval gate -> import -> bridge)."""
    from app.plugins.state import PluginStateStore

    plugin_dir = tmp_path / "plugins" / "stub-ml-plugin"
    pkg = plugin_dir / "stub_ml"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "plugin.py").write_text(textwrap.dedent(PLUGIN_MODULE), encoding="utf-8")
    (plugin_dir / "ciaren-plugin.json").write_text(json.dumps(MANIFEST), encoding="utf-8")

    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(tmp_path / "plugins"))
    state = PluginStateStore()
    state.set_approved(PLUGIN_ID, True)
    state.save()
    reset_registry()
    get_registry()
    yield
    reset_registry()


def _train_predict_graph():
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "train", "type": NODE_ID, "data": {"config": {"target_column": "target"}}},
            {"id": "pred", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "train"},
            {"id": "e2", "source": "in1", "target": "pred", "targetHandle": "in"},
            {"id": "e3", "source": "train", "target": "pred", "targetHandle": "model"},
            {"id": "e4", "source": "pred", "target": "out1"},
        ],
    }


def test_plugin_train_node_bridges_with_model_ports(stub_plugin_loaded):
    assert NODE_ID in list_transformation_types()
    assert node_kinds.model_output_handles(NODE_ID) == frozenset({"model"})
    assert node_kinds.output_handles(NODE_ID) == ("model",)
    assert node_kinds.is_flow_terminal(NODE_ID)
    assert node_kinds.is_model_sink(NODE_ID)
    assert node_kinds.edge_carries_model(NODE_ID, None)


def test_plugin_node_kinds_unregister_on_reset(stub_plugin_loaded):
    reset_registry()
    assert not node_kinds.is_flow_terminal(NODE_ID)
    assert node_kinds.model_output_handles(NODE_ID) == frozenset()
    assert node_kinds.output_handles(NODE_ID) == ("out",)


def test_graph_validation_enforces_plugin_model_wire(stub_plugin_loaded):
    validate_graph(_train_predict_graph())  # model -> mlPredict.model is fine

    # A plugin model output cannot feed a data input.
    bad = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "train", "type": NODE_ID, "data": {"config": {"target_column": "target"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "train"},
            {"id": "e2", "source": "train", "target": "out1"},
        ],
    }
    with pytest.raises(GraphValidationError, match="model"):
        validate_graph(bad)


def test_plugin_train_node_is_a_valid_flow_terminal(stub_plugin_loaded):
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "train", "type": NODE_ID, "data": {"config": {"target_column": "target"}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "train"}],
    }
    validate_graph(graph)  # no output node needed — the train node persists a model


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_plugin_train_to_core_predict_end_to_end(stub_plugin_loaded, tmp_path, engine_name):
    from app.engine.executor import FlowExecutor, dataset_ref_key

    in_csv = tmp_path / "in.csv"
    classification_df().to_csv(in_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    outputs = FlowExecutor().execute(
        _train_predict_graph(),
        dataset_paths={dataset_ref_key("ds1", None): in_csv},
        output_dir=out_dir,
        engine_name=engine_name,
    )
    result = pd.read_csv(outputs["out1"])
    assert "prediction" in result.columns
    assert set(result["prediction"].unique()).issubset({0, 1})
