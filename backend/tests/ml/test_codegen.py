"""ML code export: the CodeGenerator wires multi-output handle variables and
collects per-node sklearn imports; the exported script compiles."""
from app.engine.codegen import CodeGenerator


def _paths():
    return {"ds1": "data.csv"}


def test_train_test_split_export_uses_two_vars():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 42, "test_size": 0.2}}},
            {"id": "o1", "type": "csvOutput", "data": {"config": {"path": "train.csv"}}},
            {"id": "o2", "type": "csvOutput", "data": {"config": {"path": "test.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "o1", "sourceHandle": "train"},
            {"id": "e3", "source": "sp", "target": "o2", "sourceHandle": "test"},
        ],
    }
    code = CodeGenerator().generate(graph, _paths())
    assert "from sklearn.model_selection import train_test_split" in code
    assert "train_test_split(" in code
    # two distinct output vars are produced and written to the two files
    assert 'train.csv' in code and 'test.csv' in code
    compile(code, "<gen>", "exec")


def test_full_ml_pipeline_export_compiles():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 1}}},
            {"id": "tr", "type": "mlTrain", "data": {"config": {
                "model_type": "random_forest_classifier", "target_column": "target", "seed": 1}}},
            {"id": "pr", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {"id": "ev", "type": "mlEvaluate", "data": {"config": {
                "task_type": "classification", "target_column": "target", "prediction_column": "prediction"}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "metrics.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "tr", "sourceHandle": "train"},
            {"id": "e3", "source": "sp", "target": "pr", "sourceHandle": "test"},
            {"id": "e4", "source": "tr", "target": "pr", "sourceHandle": "model", "targetHandle": "model"},
            {"id": "e5", "source": "pr", "target": "ev"},
            {"id": "e6", "source": "ev", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, _paths())
    # imports collected from the ML nodes
    assert "from sklearn.ensemble import RandomForestClassifier" in code
    assert "from sklearn.pipeline import Pipeline" in code
    assert "train_test_split(" in code
    # mlPredict reuses the upstream trained model variable (no redundant load)
    assert ".predict(" in code
    compile(code, "<gen>", "exec")


def test_feature_engineering_export_compiles():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sc", "type": "scaleFeatures", "data": {"config": {"method": "standard", "columns": ["a"]}}},
            {"id": "en", "type": "encodeCategories", "data": {"config": {"method": "onehot", "columns": ["b"]}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "fe.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sc"},
            {"id": "e2", "source": "sc", "target": "en"},
            {"id": "e3", "source": "en", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, _paths())
    assert "from sklearn.preprocessing import StandardScaler" in code
    assert "pd.get_dummies(" in code
    compile(code, "<gen>", "exec")


def test_imports_are_deduplicated():
    # Two scaleFeatures nodes -> StandardScaler imported once.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "s1", "type": "scaleFeatures", "data": {"config": {"method": "standard", "columns": ["a"]}}},
            {"id": "s2", "type": "scaleFeatures", "data": {"config": {"method": "standard", "columns": ["a"]}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "o.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "s1"},
            {"id": "e2", "source": "s1", "target": "s2"},
            {"id": "e3", "source": "s2", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, _paths())
    assert code.count("from sklearn.preprocessing import StandardScaler") == 1
    compile(code, "<gen>", "exec")
