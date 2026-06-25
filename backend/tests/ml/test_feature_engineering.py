"""Feature-engineering ML nodes: scale, encode, select, reduce.

Each node converts at the engine boundary (to_pandas/from_pandas), so the core
behaviour is exercised on both engines; sklearn-specific assertions use pandas.
"""

import numpy as np
import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.transformations.ml.feature_engineering import (
    EncodeCategoriesTransformation,
    ReduceDimensionsTransformation,
    ScaleFeaturesTransformation,
    SelectFeaturesTransformation,
)

ENGINES = ["pandas", "polars"]


def _frame(engine_name, df):
    engine = get_engine(engine_name)
    return engine, engine.from_pandas(df)


def _run(node, engine, frame, config):
    return engine.to_pandas(node.execute(engine, {"in": frame}, config)["out"])


# -- scaleFeatures ----------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_standard_scaler_zero_mean_unit_std(engine_name):
    engine, frame = _frame(engine_name, pd.DataFrame({"x": [1.0, 2, 3, 4, 5], "y": [10, 20, 30, 40, 50]}))
    out = _run(ScaleFeaturesTransformation(), engine, frame, {"method": "standard", "columns": ["x", "y"]})
    assert out["x"].mean() == pytest.approx(0.0, abs=1e-9)
    assert out["x"].std(ddof=0) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("engine_name", ENGINES)
def test_minmax_scaler_bounds(engine_name):
    engine, frame = _frame(engine_name, pd.DataFrame({"x": [1.0, 5, 9]}))
    out = _run(ScaleFeaturesTransformation(), engine, frame, {"method": "minmax", "columns": ["x"]})
    assert out["x"].min() == pytest.approx(0.0)
    assert out["x"].max() == pytest.approx(1.0)


def test_scale_validate_rejects_bad_method_and_empty_columns():
    node = ScaleFeaturesTransformation()
    with pytest.raises(ValueError, match="method"):
        node.validate_config({"method": "zscore", "columns": ["x"]})
    with pytest.raises(ValueError, match="columns"):
        node.validate_config({"method": "standard", "columns": []})


def test_scale_missing_column_raises():
    engine, frame = _frame("pandas", pd.DataFrame({"x": [1.0, 2]}))
    with pytest.raises(ValueError, match="not found"):
        ScaleFeaturesTransformation().execute(engine, {"in": frame}, {"method": "standard", "columns": ["z"]})


# -- encodeCategories -------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_onehot_expands_columns(engine_name):
    engine, frame = _frame(engine_name, pd.DataFrame({"color": ["r", "g", "b", "r"], "v": [1, 2, 3, 4]}))
    out = _run(EncodeCategoriesTransformation(), engine, frame, {"method": "onehot", "columns": ["color"]})
    assert "color" not in out.columns
    assert {"color_r", "color_g", "color_b"}.issubset(out.columns)


def test_onehot_drop_first():
    engine, frame = _frame("pandas", pd.DataFrame({"color": ["r", "g", "b"]}))
    out = _run(
        EncodeCategoriesTransformation(), engine, frame, {"method": "onehot", "columns": ["color"], "drop_first": True}
    )
    # one category dropped -> 2 dummy columns, not 3
    assert sum(c.startswith("color_") for c in out.columns) == 2


@pytest.mark.parametrize("engine_name", ENGINES)
def test_ordinal_encoding_is_numeric(engine_name):
    engine, frame = _frame(engine_name, pd.DataFrame({"size": ["s", "m", "l", "m"]}))
    out = _run(EncodeCategoriesTransformation(), engine, frame, {"method": "ordinal", "columns": ["size"]})
    assert pd.api.types.is_numeric_dtype(out["size"])
    assert out["size"].nunique() == 3


# -- selectFeatures ---------------------------------------------------------


def test_variance_threshold_drops_constant_column():
    engine, frame = _frame("pandas", pd.DataFrame({"const": [1, 1, 1, 1], "vary": [1, 2, 3, 4]}))
    out = _run(SelectFeaturesTransformation(), engine, frame, {"method": "variance", "threshold": 0.0})
    assert "const" not in out.columns
    assert "vary" in out.columns


def test_correlation_filter_drops_collinear():
    base = np.arange(50, dtype=float)
    df = pd.DataFrame({"a": base, "b": base * 2.0 + 1.0, "c": np.random.RandomState(0).rand(50)})
    engine, frame = _frame("pandas", df)
    out = _run(SelectFeaturesTransformation(), engine, frame, {"method": "correlation", "threshold": 0.95})
    # a and b are perfectly correlated -> exactly one of them is dropped.
    assert ("a" in out.columns) ^ ("b" in out.columns)
    assert "c" in out.columns


def test_kbest_keeps_k_plus_target():
    rng = np.random.RandomState(0)
    y = rng.randint(0, 2, size=100)
    df = pd.DataFrame(
        {
            "good": y + rng.normal(0, 0.01, 100),  # strongly predictive
            "noise1": rng.normal(0, 1, 100),
            "noise2": rng.normal(0, 1, 100),
            "target": y,
        }
    )
    engine, frame = _frame("pandas", df)
    out = _run(SelectFeaturesTransformation(), engine, frame, {"method": "kbest", "k": 1, "target_column": "target"})
    assert "good" in out.columns
    assert "target" in out.columns
    assert out.shape[1] == 2  # 1 best feature + target


def _exec_exported(node, config, df):
    """Run a node's exported code in a namespace and return the result frame."""
    from sklearn.feature_selection import (  # noqa: F401 - used by exec'd code
        SelectKBest,
        f_classif,
        f_regression,
    )

    code = node.to_python_code({"in": "df"}, {"out": "res"}, config)
    ns = {
        "pd": pd,
        "np": np,
        "df": df,
        "SelectKBest": SelectKBest,
        "f_classif": f_classif,
        "f_regression": f_regression,
    }
    exec(code, ns)  # noqa: S102 - exercising generated code on purpose
    return ns["res"]


def test_kbest_export_matches_execute_classification():
    rng = np.random.RandomState(0)
    y = rng.randint(0, 2, size=60)
    df = pd.DataFrame(
        {
            "id": [f"r{i}" for i in range(60)],  # non-numeric passthrough
            "good": y + rng.normal(0, 0.01, 60),
            "noise": rng.normal(0, 1, 60),
            "target": y,
        }
    )
    node, config = SelectFeaturesTransformation(), {"method": "kbest", "k": 1, "target_column": "target"}
    engine, frame = _frame("pandas", df)
    executed = _run(node, engine, frame, config)
    exported = _exec_exported(node, config, df)
    # The non-numeric 'id' column must survive in both (a regression earlier dropped it).
    assert "id" in executed.columns
    assert list(executed.columns) == list(exported.columns)


def test_kbest_export_matches_execute_regression():
    rng = np.random.RandomState(1)
    df = pd.DataFrame(
        {
            "id": [f"r{i}" for i in range(60)],
            "a": rng.rand(60),
            "b": rng.rand(60),
            "c": rng.rand(60),
            "target": rng.rand(60) * 100,  # continuous -> f_regression
        }
    )
    node, config = SelectFeaturesTransformation(), {"method": "kbest", "k": 2, "target_column": "target"}
    engine, frame = _frame("pandas", df)
    executed = _run(node, engine, frame, config)
    exported = _exec_exported(node, config, df)
    assert list(executed.columns) == list(exported.columns)


def test_select_validate_kbest_requires_target_and_k():
    node = SelectFeaturesTransformation()
    with pytest.raises(ValueError, match="target_column"):
        node.validate_config({"method": "kbest", "k": 2})
    with pytest.raises(ValueError, match="'k'"):
        node.validate_config({"method": "kbest", "target_column": "y", "k": 0})


# -- reduceDimensions -------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_pca_produces_components(engine_name):
    rng = np.random.RandomState(0)
    df = pd.DataFrame({f"f{i}": rng.rand(40) for i in range(5)})
    df["keep"] = ["x"] * 40  # non-numeric passthrough
    engine, frame = _frame(engine_name, df)
    out = _run(ReduceDimensionsTransformation(), engine, frame, {"n_components": 2, "seed": 0})
    assert {"pc_1", "pc_2"}.issubset(out.columns)
    assert "keep" in out.columns  # non-feature column preserved
    assert not any(c.startswith("f") for c in out.columns)  # original features replaced


def test_pca_caps_components_to_feature_count():
    df = pd.DataFrame({"a": [1.0, 2, 3, 4], "b": [4.0, 3, 2, 1]})
    engine, frame = _frame("pandas", df)
    # ask for more components than features (2) -> capped, no error
    out = _run(ReduceDimensionsTransformation(), engine, frame, {"n_components": 5, "columns": ["a", "b"]})
    assert sum(c.startswith("pc_") for c in out.columns) == 2


def test_reduce_export_caps_n_components_like_execute():
    # n_components (5) exceeds the feature count (2): execute caps it, and the
    # exported code must cap it too instead of crashing inside PCA.
    from sklearn.decomposition import PCA  # noqa: F401 - used by exec'd code

    df = pd.DataFrame({"a": np.random.RandomState(0).rand(8), "b": np.random.RandomState(1).rand(8)})
    node, config = ReduceDimensionsTransformation(), {"n_components": 5, "columns": ["a", "b"], "seed": 0}
    engine, frame = _frame("pandas", df)
    executed = _run(node, engine, frame, config)
    ns = {"pd": pd, "np": np, "df": df.copy(), "PCA": PCA}
    exec(node.to_python_code({"in": "df"}, {"out": "res"}, config), ns)  # noqa: S102
    exported = ns["res"]
    exec_pc = sorted(c for c in executed.columns if c.startswith("pc_"))
    export_pc = sorted(c for c in exported.columns if c.startswith("pc_"))
    assert exec_pc == export_pc == ["pc_1", "pc_2"]


def test_reduce_validate_rejects_bad_n_components():
    node = ReduceDimensionsTransformation()
    with pytest.raises(ValueError, match="n_components"):
        node.validate_config({"n_components": 0})
    with pytest.raises(ValueError, match="n_components"):
        node.validate_config({"n_components": 1.5})
    node.validate_config({"n_components": 3})
    node.validate_config({"n_components": 0.95})


# -- generated code compiles ------------------------------------------------


@pytest.mark.parametrize(
    "node,config",
    [
        (ScaleFeaturesTransformation(), {"method": "robust", "columns": ["a"]}),
        (EncodeCategoriesTransformation(), {"method": "onehot", "columns": ["a"]}),
        (EncodeCategoriesTransformation(), {"method": "ordinal", "columns": ["a"]}),
        (SelectFeaturesTransformation(), {"method": "variance", "threshold": 0.0}),
        (SelectFeaturesTransformation(), {"method": "correlation", "threshold": 0.9}),
        (SelectFeaturesTransformation(), {"method": "kbest", "k": 1, "target_column": "t"}),
        (ReduceDimensionsTransformation(), {"n_components": 2}),
    ],
)
def test_generated_code_compiles(node, config):
    code = node.to_python_code({"in": "df_0"}, {"out": "df_1"}, config)
    snippet = "\n".join(["import pandas as pd", *node.imports(config), code])
    compile(snippet, "<gen>", "exec")
