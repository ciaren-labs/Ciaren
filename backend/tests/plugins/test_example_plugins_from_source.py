# SPDX-License-Identifier: AGPL-3.0-only
"""Every example under ``examples/plugins/`` builds from source, installs, loads, and runs.

Each example directory (discovered, so a new example is covered automatically) is
packed, signed, and verified with the helpers the ``build_*_ciarenplugin.py``
scripts use, installed through the production installer, loaded through the plugin
runtime (``get_registry``: loader plus engine bridge), and each of its nodes runs
once on a tiny frame. A plugin_api change that breaks a documented example fails
here instead of in a user's editor.

The committed ``dist/`` packages are checked against their source manifests. Their
content digests are not compared: the archives are built from a checkout whose
line endings depend on the platform (``core.autocrlf``), so a byte-level digest is
not reproducible between CI and developer machines.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends import get_engine
from app.engine.registry import get_transformation
from app.ml.availability import ml_core_available
from app.plugin_api import signing
from app.plugins.install import install_ciarenplugin, read_manifest_from_dir
from app.plugins.package import MANIFEST_FILENAME, pack_directory, read_manifest, sign_package, verify_package
from app.plugins.state import PluginStateStore

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples" / "plugins"
EXAMPLE_DIRS = sorted(p for p in EXAMPLES_DIR.iterdir() if (p / MANIFEST_FILENAME).is_file())
DIST_PACKAGES = sorted((EXAMPLES_DIR / "dist").glob("*.ciarenplugin"))

#: Smoke-run configs for nodes whose NodeSpec ``default_config`` cannot run on
#: :func:`_smoke_frame`. Any other node runs with its defaults, so a new example
#: needs an entry here only when its defaults require user input.
SMOKE_CONFIGS: dict[str, dict[str, Any]] = {
    "validator.checkColumn": {"column": "sku", "rule": "regex", "pattern": "^[A-Z]-\\d{3}$"},
    "sklearn.mlpClassifierTrain": {
        "target_column": "label",
        "feature_columns": ["f1", "f2"],
        "hidden_layer_sizes": "4",
        "solver": "lbfgs",
        "max_iter": 200,
    },
}

each_example = pytest.mark.parametrize("example_dir", EXAMPLE_DIRS, ids=lambda p: p.name)


def _smoke_frame() -> pd.DataFrame:
    # Two balanced classes so a classifier's stratified train/test split is valid.
    return pd.DataFrame(
        {
            "f1": [i / 20 for i in range(20)],
            "f2": [(i % 5) / 5 for i in range(20)],
            "label": [i % 2 for i in range(20)],
            "sku": [f"A-{i:03d}" for i in range(20)],
        }
    )


def _drop_modules(package_name: str) -> list[str]:
    return [n for n in sys.modules if n == package_name or n.startswith(package_name + ".")]


@pytest.fixture
def loaded_example(example_dir: Path, tmp_path, monkeypatch):
    """Build ``example_dir`` into a signed package, install and approve it, and load
    it through the process-wide plugin runtime. Teardown unregisters the bridged
    nodes and drops the modules imported from the install."""
    from app.plugins import get_load_result, get_registry, reset_registry

    if not signing.signing_available():
        pytest.skip("cryptography not installed; the build scripts cannot sign")
    manifest = read_manifest_from_dir(example_dir)
    assert manifest.entrypoint, f"{example_dir.name} manifest has no entrypoint"
    private_key, public_key = signing.generate_keypair()
    trusted = {"test-key": public_key}
    package = pack_directory(example_dir, tmp_path / f"{manifest.id}-{manifest.version}.ciarenplugin")
    sign_package(package, private_key, key_id="test-key", publisher=manifest.publisher)
    assert verify_package(package, trusted_keys=trusted).outcome == "trusted"
    install_dir = tmp_path / "installed"
    installed = install_ciarenplugin(package, install_dir=install_dir, require_trusted=True, trusted_keys=trusted)

    state = PluginStateStore()
    state.set_approved(manifest.id, True)
    state.save()

    # Discover only this install (not a developer's ~/.ciaren/plugins), and keep
    # MLflow output for model-persisting examples under tmp_path.
    home = tmp_path / "home"
    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(install_dir))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    # Other tests import the examples from their source directory or another
    # install and leave that directory on sys.path, ahead of anything the loader
    # appends. The loader must import this install instead, and it must not outlive
    # this test; monkeypatch restores the earlier modules and sys.path.
    package_name = manifest.entrypoint.partition(":")[0].split(".")[0]
    for name in _drop_modules(package_name):
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if not (Path(p) / package_name).exists()])
    get_settings.cache_clear()
    reset_registry()
    try:
        yield manifest, installed.location, get_registry(), get_load_result()
    finally:
        reset_registry()
        get_settings.cache_clear()
        for name in _drop_modules(package_name):
            del sys.modules[name]


def test_examples_are_discovered():
    # An empty parametrization would silently skip every per-example check.
    assert EXAMPLE_DIRS
    assert DIST_PACKAGES


@each_example
def test_example_builds_installs_and_registers(loaded_example):
    manifest, location, registry, result = loaded_example
    assert [e.error for e in result.errors] == []
    assert manifest.id in {p.metadata.id for p in result.loaded}
    registered = {spec.id for spec in registry.node_specs() if spec.provider == manifest.id}
    assert registered == set(manifest.ui.nodes)
    for node_id in manifest.ui.nodes:
        get_transformation(node_id)  # bridged into the engine, or KeyError
    entry_module = sys.modules[manifest.entrypoint.partition(":")[0]]
    assert Path(entry_module.__file__).is_relative_to(location)


@each_example
def test_example_nodes_execute(loaded_example):
    manifest, _, registry, _ = loaded_example
    engine = get_engine("pandas")
    frame = engine.from_pandas(_smoke_frame())
    for node_id in manifest.ui.nodes:
        spec = registry.node_spec(node_id)
        assert spec is not None
        persists_model = spec.is_model_sink or any(p.type == "model" for p in spec.outputs)
        if persists_model and not ml_core_available():
            pytest.skip(f"{node_id} persists a model and needs the [ml] extra (scikit-learn + MLflow)")
        config = SMOKE_CONFIGS.get(node_id, dict(spec.default_config))
        transformation = get_transformation(node_id)
        transformation.validate_config(config)
        outputs = transformation.execute(engine, {port.id: frame for port in spec.inputs}, config)
        assert set(outputs) == {port.id for port in spec.outputs}


@pytest.mark.parametrize("package", DIST_PACKAGES, ids=lambda p: p.name)
def test_dist_package_matches_its_source_manifest(package):
    built = read_manifest(package)
    sources = {read_manifest_from_dir(d).id: d for d in EXAMPLE_DIRS}
    assert built.id in sources, f"{package.name} has no source example in {EXAMPLES_DIR}"
    assert built == read_manifest_from_dir(sources[built.id]), (
        f"{package.name} is stale: rebuild it with examples/plugins/build_*_ciarenplugin.py"
    )
