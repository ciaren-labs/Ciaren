"""trainTestSplit node: seed enforcement, split correctness on both engines,
stratification edge cases, and the min-train-rows guardrail."""
import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.transformations.ml.base import MLSchema
from app.engine.transformations.ml.split import (
    MIN_TRAIN_ROWS,
    TrainTestSplitTransformation,
)

NODE = TrainTestSplitTransformation()


def _frame(engine_name, n=100, with_classes=False):
    engine = get_engine(engine_name)
    data = {"v": list(range(n))}
    if with_classes:
        # 70/30 split across two classes.
        data["label"] = ["a"] * (n * 7 // 10) + ["b"] * (n - n * 7 // 10)
    return engine, engine.from_pandas(pd.DataFrame(data))


# -- validate_config --------------------------------------------------------


@pytest.mark.parametrize("seed", [None, "42", 3.5, True, False])
def test_seed_is_required_and_integer(seed):
    with pytest.raises(ValueError, match="seed"):
        NODE.validate_config({"seed": seed} if seed is not None else {})


def test_valid_seed_passes():
    NODE.validate_config({"seed": 42})


@pytest.mark.parametrize("test_size", [0, 1, 1.5, -0.1, "0.2", True])
def test_test_size_must_be_fraction(test_size):
    with pytest.raises(ValueError, match="test_size"):
        NODE.validate_config({"seed": 42, "test_size": test_size})


def test_stratify_column_must_be_str_or_null():
    with pytest.raises(ValueError, match="stratify_column"):
        NODE.validate_config({"seed": 42, "stratify_column": 5})
    NODE.validate_config({"seed": 42, "stratify_column": None})
    NODE.validate_config({"seed": 42, "stratify_column": "label"})


# -- execute: split correctness ---------------------------------------------


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_split_sizes(engine_name):
    engine, frame = _frame(engine_name, n=100)
    out = NODE.execute(engine, {"in": frame}, {"seed": 42, "test_size": 0.25})
    assert set(out) == {"train", "test"}
    assert engine.row_count(out["train"]) == 75
    assert engine.row_count(out["test"]) == 25


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_split_is_reproducible_with_same_seed(engine_name):
    engine, frame = _frame(engine_name, n=100)
    a = NODE.execute(engine, {"in": frame}, {"seed": 7, "test_size": 0.2})
    b = NODE.execute(engine, {"in": frame}, {"seed": 7, "test_size": 0.2})
    assert engine.to_pandas(a["train"])["v"].tolist() == engine.to_pandas(b["train"])["v"].tolist()
    assert engine.to_pandas(a["test"])["v"].tolist() == engine.to_pandas(b["test"])["v"].tolist()


def test_different_seeds_differ():
    engine, frame = _frame("pandas", n=100)
    a = NODE.execute(engine, {"in": frame}, {"seed": 1, "test_size": 0.2})
    b = NODE.execute(engine, {"in": frame}, {"seed": 2, "test_size": 0.2})
    assert engine.to_pandas(a["test"])["v"].tolist() != engine.to_pandas(b["test"])["v"].tolist()


def test_train_and_test_are_disjoint_and_cover_all_rows():
    engine, frame = _frame("pandas", n=50)
    out = NODE.execute(engine, {"in": frame}, {"seed": 0, "test_size": 0.3})
    train = set(engine.to_pandas(out["train"])["v"])
    test = set(engine.to_pandas(out["test"])["v"])
    assert train.isdisjoint(test)
    assert train | test == set(range(50))


# -- min train rows guardrail -----------------------------------------------


def test_too_few_training_rows_rejected():
    engine, frame = _frame("pandas", n=12)
    with pytest.raises(ValueError, match=f"at least {MIN_TRAIN_ROWS}"):
        NODE.execute(engine, {"in": frame}, {"seed": 42, "test_size": 0.9})


# -- stratification ---------------------------------------------------------


def test_stratify_preserves_class_balance():
    engine, frame = _frame("pandas", n=100, with_classes=True)
    out = NODE.execute(engine, {"in": frame}, {"seed": 42, "test_size": 0.2, "stratify_column": "label"})
    test = engine.to_pandas(out["test"])
    # 20% of 100 = 20 rows; 70/30 class balance -> 14 'a', 6 'b'.
    counts = test["label"].value_counts().to_dict()
    assert counts == {"a": 14, "b": 6}


def test_stratify_on_rare_class_raises():
    engine = get_engine("pandas")
    # class 'rare' has a single sample — cannot appear in both splits.
    df = pd.DataFrame({"v": range(40), "label": ["a"] * 39 + ["rare"]})
    with pytest.raises(ValueError, match="rare"):
        NODE.execute(engine, {"in": engine.from_pandas(df)}, {"seed": 1, "stratify_column": "label"})


def test_stratify_on_missing_column_raises():
    engine, frame = _frame("pandas", n=40)
    with pytest.raises(ValueError, match="not in the input columns"):
        NODE.execute(engine, {"in": frame}, {"seed": 1, "stratify_column": "ghost"})


# -- validate_with_schema (early, data-free) --------------------------------


def test_schema_validation_rejects_missing_stratify_column():
    schema = MLSchema(columns=["v", "label"], row_count=100)
    NODE.validate_with_schema({"seed": 1, "stratify_column": "label"}, schema)
    with pytest.raises(ValueError, match="ghost"):
        NODE.validate_with_schema({"seed": 1, "stratify_column": "ghost"}, schema)


def test_schema_validation_rejects_tiny_dataset():
    schema = MLSchema(columns=["v"], row_count=12)
    with pytest.raises(ValueError, match=f"at least {MIN_TRAIN_ROWS}"):
        NODE.validate_with_schema({"seed": 1, "test_size": 0.9}, schema)


# -- through the executor (multi-output routing) ----------------------------


def test_executor_routes_train_and_test(tmp_path):
    csv = tmp_path / "in.csv"
    pd.DataFrame({"v": range(100)}).to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 42, "test_size": 0.2}}},
            {"id": "out_tr", "type": "csvOutput", "data": {"config": {}}},
            {"id": "out_te", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "out_tr", "sourceHandle": "train"},
            {"id": "e3", "source": "sp", "target": "out_te", "sourceHandle": "test"},
        ],
    }
    paths = {dataset_ref_key("ds1", None): csv}
    result = FlowExecutor().run_with_results(graph, paths, out_dir)
    assert result.error is None
    assert len(pd.read_csv(result.output_paths["out_tr"])) == 80
    assert len(pd.read_csv(result.output_paths["out_te"])) == 20
    by_id = {r.node_id: r for r in result.node_results}
    # primary handle "train" is the one sampled in the run DAG.
    assert by_id["sp"].rows == 80


# -- generated code ---------------------------------------------------------


def test_to_python_code_compiles():
    code = NODE.to_python_code(
        {"in": "df_0"}, {"train": "df_tr", "test": "df_te"}, {"seed": 42, "test_size": 0.2}
    )
    assert "train_test_split(df_0" in code
    assert "random_state=42" in code
    # with the import prepended, the snippet is valid Python
    compile("\n".join(NODE.imports({}) + [code]), "<gen>", "exec")
