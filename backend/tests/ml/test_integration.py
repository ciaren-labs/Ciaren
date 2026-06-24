"""End-to-end ML pipeline through the executor:

csvInput -> trainTestSplit -> mlTrain (train branch)
                           -> mlPredict (test branch + model) -> mlEvaluate -> csvOutput

Exercises multi-output routing (split, train), the optional model input on
mlPredict, the metadata channel, and reproducibility across two runs.
"""
import pandas as pd
import pytest

from app.engine.executor import FlowExecutor, dataset_ref_key
from tests.ml.conftest import classification_df


def _graph():
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "split", "type": "trainTestSplit",
             "data": {"config": {"seed": 42, "test_size": 0.25, "stratify_column": "target"}}},
            {"id": "train", "type": "mlTrain", "data": {"config": {
                "model_type": "random_forest_classifier", "target_column": "target", "seed": 42}}},
            {"id": "pred", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {"id": "eval", "type": "mlEvaluate", "data": {"config": {
                "task_type": "classification", "target_column": "target", "prediction_column": "prediction"}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "split"},
            {"id": "e2", "source": "split", "target": "train", "sourceHandle": "train"},
            {"id": "e3", "source": "split", "target": "pred", "sourceHandle": "test"},
            {"id": "e4", "source": "train", "target": "pred", "sourceHandle": "model", "targetHandle": "model"},
            {"id": "e5", "source": "pred", "target": "eval"},
            {"id": "e6", "source": "eval", "target": "out"},
        ],
    }


@pytest.fixture
def dataset(tmp_path):
    csv = tmp_path / "in.csv"
    classification_df(n=200).to_csv(csv, index=False)
    return csv


def test_full_ml_pipeline(ml_env, dataset, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    paths = {dataset_ref_key("ds1", None): dataset}
    result = FlowExecutor().run_with_results(_graph(), paths, out_dir)

    assert result.error is None, result.error
    by_id = {r.node_id: r for r in result.node_results}
    # every node succeeded
    assert all(r.status == "success" for r in result.node_results)
    # train node surfaced ML metadata
    assert by_id["train"].task_type == "classification"
    assert by_id["train"].model_uri
    assert "train_accuracy" in by_id["train"].ml_metrics
    # eval node surfaced metrics
    assert "accuracy" in by_id["eval"].ml_metrics
    # the written metrics file is the long-format evaluation frame
    metrics_df = pd.read_csv(result.output_paths["out"])
    assert "metric" in metrics_df.columns and "value" in metrics_df.columns
    assert "accuracy" in set(metrics_df["metric"])


def test_pipeline_is_reproducible(ml_env, dataset, tmp_path):
    paths = {dataset_ref_key("ds1", None): dataset}
    out1 = tmp_path / "o1"
    out1.mkdir()
    out2 = tmp_path / "o2"
    out2.mkdir()
    r1 = FlowExecutor().run_with_results(_graph(), paths, out1)
    r2 = FlowExecutor().run_with_results(_graph(), paths, out2)
    acc1 = {x.node_id: x for x in r1.node_results}["eval"].ml_metrics["accuracy"]
    acc2 = {x.node_id: x for x in r2.node_results}["eval"].ml_metrics["accuracy"]
    assert acc1 == acc2
