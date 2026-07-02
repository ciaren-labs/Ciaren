"""The advanced MLP Classifier example plugin: validation, execution, and export.

Loads the committed example plugin from its directory (the same path the loader
uses), then exercises config validation, the executable runtime, Python-code
export, and that its signed package is bundled into the Explore catalog.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "examples" / "plugins" / "mlp-classifier-plugin"
BUNDLED = REPO_ROOT / "backend" / "app" / "bundled_plugins"

pytest.importorskip("sklearn", reason="the MLP plugin needs scikit-learn")


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


def test_execute_trains_and_returns_metrics(runtime):
    out = runtime.execute({"in": _dataset()}, {"target_column": "label", "hidden_layer_sizes": "16", "max_iter": 300})[
        "out"
    ]
    assert list(out.columns) == [
        "n_samples",
        "n_features",
        "n_classes",
        "train_accuracy",
        "test_accuracy",
        "n_iterations",
        "final_loss",
        "hidden_layer_sizes",
        "activation",
        "solver",
    ]
    row = out.iloc[0]
    assert row["n_samples"] == 80
    assert row["n_features"] == 2
    assert row["n_classes"] == 2
    assert 0.0 <= row["test_accuracy"] <= 1.0
    # A separable dataset should train well past chance.
    assert row["train_accuracy"] > 0.7


def test_execute_rejects_non_numeric_features(runtime):
    df = _dataset()
    df["f2"] = "not-a-number"
    with pytest.raises(ValueError, match="numeric"):
        runtime.execute({"in": df}, {"target_column": "label"})


def test_execute_rejects_missing_target(runtime):
    with pytest.raises(ValueError, match="target column"):
        runtime.execute({"in": _dataset()}, {"target_column": "does_not_exist"})


def test_exported_code_is_valid_python(runtime):
    code = runtime.to_python_code(
        {"in": "df_1"},
        {"out": "df_2"},
        {"target_column": "label", "feature_columns": ["f1", "f2"], "hidden_layer_sizes": "16"},
    )
    assert "MLPClassifier(" in code
    assert "train_test_split(" in code
    compile(code, "<generated>", "exec")  # must be syntactically valid


def test_signed_package_is_bundled_in_catalog():
    """The build script ships a signed package + catalog entry so a fresh install
    lists the plugin in Explore, ready to install."""
    import json

    from app.plugins.package import read_manifest, verify_package

    pkg = BUNDLED / "community.mlp-classifier-0.1.0.ciarenplugin"
    assert pkg.is_file(), "run examples/plugins/build_mlp_classifier_ciarenplugin.py"
    assert read_manifest(pkg).id == "community.mlp-classifier"

    demo_key = {"ciaren-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}
    assert verify_package(pkg, trusted_keys=demo_key).outcome == "trusted"

    catalog = json.loads((BUNDLED / "marketplace.json").read_text(encoding="utf-8"))
    ids = {e["id"] for e in catalog["plugins"]}
    assert {"community.hello", "community.mlp-classifier"} <= ids
