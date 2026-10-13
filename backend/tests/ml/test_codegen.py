"""ML code export: the CodeGenerator wires multi-output handle variables and
collects per-node sklearn imports; the exported script compiles."""

import numpy as np
import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.codegen import CodeGenerator
from app.engine.codegen_params import parameter_block_lines, substitute_for_codegen
from app.engine.polars_codegen import PolarsCodeGenerator
from app.engine.registry import get_transformation
from tests.ml.conftest import classification_df


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
    assert "train.csv" in code and "test.csv" in code
    compile(code, "<gen>", "exec")


def test_full_ml_pipeline_export_compiles():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 1}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {"config": {"model_type": "random_forest_classifier", "target_column": "target", "seed": 1}},
            },
            {"id": "pr", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {
                "id": "ev",
                "type": "mlEvaluate",
                "data": {
                    "config": {
                        "task_type": "classification",
                        "target_column": "target",
                        "prediction_column": "prediction",
                    }
                },
            },
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


def test_exported_ml_pipeline_runs_on_categorical_and_null_data(tmp_path):
    """The exported script must *run*, not just compile: mlTrain bundles the same
    preprocessing as the run (impute + scale + one-hot), and mlPredict scores only
    the model's features. A flow with a categorical column and nulls would crash
    if either of those were dropped from the export."""
    data = tmp_path / "data.csv"
    rng = np.random.default_rng(0)
    n = 120
    df = pd.DataFrame(
        {
            "num1": rng.normal(size=n),
            "num2": rng.normal(size=n),
            "color": rng.choice(["r", "g", "b"], size=n),
            "target": rng.integers(0, 2, size=n),
        }
    )
    df.loc[0:5, "num1"] = np.nan  # nulls force the imputer to be present
    df.to_csv(data, index=False)
    pred_out = tmp_path / "pred.csv"

    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 42, "test_size": 0.25}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {
                    "config": {
                        "model_type": "random_forest_classifier",
                        "target_column": "target",
                        "feature_columns": ["num1", "num2", "color"],
                        "seed": 42,
                    }
                },
            },
            {"id": "pr", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": pred_out.as_posix()}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "tr", "sourceHandle": "train"},
            {"id": "e3", "source": "sp", "target": "pr", "sourceHandle": "test"},
            {"id": "e4", "source": "tr", "target": "pr", "sourceHandle": "model", "targetHandle": "model"},
            {"id": "e5", "source": "pr", "target": "out"},
        ],
    }
    code = CodeGenerator().generate(graph, {"ds1": data.as_posix()})
    exec(compile(code, "<gen>", "exec"), {})  # noqa: S102 - exercising generated code
    result = pd.read_csv(pred_out)
    assert "prediction" in result.columns
    assert result["prediction"].notna().all()


def test_exported_evaluate_and_proba_run_with_all_metrics(tmp_path):
    """The export must emit *all* configured evaluate metrics (not just one) and
    the requested class-probability columns, and the script must run."""
    data = tmp_path / "data.csv"
    rng = np.random.default_rng(1)
    n = 120
    pd.DataFrame(
        {
            "num1": rng.normal(size=n),
            "num2": rng.normal(size=n),
            "target": rng.integers(0, 2, size=n),
        }
    ).to_csv(data, index=False)
    out = tmp_path / "metrics.csv"

    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 7, "test_size": 0.25}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {
                    "config": {
                        "model_type": "random_forest_classifier",
                        "target_column": "target",
                        "feature_columns": ["num1", "num2"],
                        "seed": 7,
                    }
                },
            },
            {
                "id": "pr",
                "type": "mlPredict",
                "data": {"config": {"output_column": "prediction", "output_proba_columns": ["p0", "p1"]}},
            },
            {
                "id": "ev",
                "type": "mlEvaluate",
                "data": {
                    "config": {
                        "task_type": "classification",
                        "target_column": "target",
                        "prediction_column": "prediction",
                        "metrics": ["accuracy", "precision", "recall", "f1"],
                    }
                },
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": out.as_posix()}}},
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
    code = CodeGenerator().generate(graph, {"ds1": data.as_posix()})
    exec(compile(code, "<gen>", "exec"), {})  # noqa: S102 - exercising generated code
    metrics = pd.read_csv(out)
    assert set(metrics["metric"]) == {"accuracy", "precision", "recall", "f1"}


@pytest.mark.parametrize("lazy", [False, True])
def test_polars_ml_export_runs_end_to_end(tmp_path, lazy):
    """A polars (eager + lazy) export of an ML flow must *run*, not just compile:
    ML nodes emit pandas/sklearn code, so the polars generator has to import pandas,
    bridge frames to/from pandas, and keep the model reference as a plain object.
    Regression: the polars script used to omit those imports and call pandas APIs on
    polars frames, so every ML flow's polars export was broken."""
    data = tmp_path / "data.csv"
    rng = np.random.default_rng(0)
    n = 140
    df = pd.DataFrame(
        {
            "num1": rng.normal(size=n),
            "num2": rng.normal(size=n),
            "color": rng.choice(["r", "g", "b"], size=n),
            "target": rng.integers(0, 2, size=n),
        }
    )
    df.loc[0:5, "num1"] = np.nan
    df.to_csv(data, index=False)
    metrics_out = tmp_path / "metrics.csv"
    fi_out = tmp_path / "fi.csv"

    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 42, "test_size": 0.25}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {
                    "config": {
                        "model_type": "random_forest_classifier",
                        "target_column": "target",
                        "feature_columns": ["num1", "num2", "color"],
                        "seed": 42,
                    }
                },
            },
            {"id": "pr", "type": "mlPredict", "data": {"config": {"output_column": "prediction"}}},
            {"id": "fi", "type": "featureImportance", "data": {"config": {}}},
            {
                "id": "ev",
                "type": "mlEvaluate",
                "data": {
                    "config": {
                        "task_type": "classification",
                        "target_column": "target",
                        "prediction_column": "prediction",
                        "metrics": ["accuracy", "f1"],
                    }
                },
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": metrics_out.as_posix()}}},
            {"id": "out2", "type": "csvOutput", "data": {"config": {"path": fi_out.as_posix()}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "tr", "sourceHandle": "train"},
            {"id": "e3", "source": "sp", "target": "pr", "sourceHandle": "test"},
            {"id": "e4", "source": "tr", "target": "pr", "sourceHandle": "model", "targetHandle": "model"},
            {"id": "e5", "source": "pr", "target": "ev"},
            {"id": "e6", "source": "ev", "target": "out"},
            {"id": "e7", "source": "tr", "target": "fi", "targetHandle": "model"},
            {"id": "e8", "source": "fi", "target": "out2"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"ds1": data.as_posix()}, lazy=lazy)
    exec(compile(code, "<gen>", "exec"), {})  # noqa: S102 - exercising generated code

    metrics = pd.read_csv(metrics_out)
    assert set(metrics["metric"]) == {"accuracy", "f1"}
    fi = pd.read_csv(fi_out)
    assert list(fi.columns) == ["feature_name", "importance", "rank"]
    # categorical one-hot names survived the polars<->pandas bridge (not integers)
    assert "color_r" in set(fi["feature_name"])


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


@pytest.fixture
def definition_input(tmp_path):
    frame = classification_df(n=24)
    path = tmp_path / "definition.csv"
    frame.to_csv(path, index=False)
    return frame, path


@pytest.fixture(
    params=[
        None,
        {"numeric_strategy": "robust_scaler"},
        {"numeric_columns": [], "categorical_columns": []},
        {"numeric_columns": ["x1", "x2"], "numeric_strategy": "robust_scaler"},
    ]
)
def preprocessing(request):
    return request.param


def _definition_graph(kind, config, scores_path=None, *, data_path=None):
    graph = {
        "nodes": [
            {"id": "input", "type": "fileInput", "data": {"config": {"dataset_id": "data", "format": "csv"}}},
            {"id": "definition", "type": kind, "data": {"config": config}},
        ],
        "edges": [{"id": "input-model", "source": "input", "target": "definition"}],
    }
    if scores_path is not None:
        graph["nodes"].extend(
            [
                {
                    "id": "cv",
                    "type": "mlCrossValidate",
                    "data": {"config": {"cv_strategy": "kfold", "n_splits": 3, "seed": 42}},
                },
                {"id": "output", "type": "fileOutput", "data": {"config": {"format": "csv", "path": scores_path}}},
            ]
        )
        graph["edges"].extend(
            [
                {"id": "input-cv", "source": "input", "target": "cv", "targetHandle": "in"},
                {
                    "id": "model-cv",
                    "source": "definition",
                    "target": "cv",
                    "sourceHandle": "model",
                    "targetHandle": "model",
                },
                {"id": "cv-output", "source": "cv", "target": "output"},
            ]
        )
    else:
        assert data_path is not None
        graph["nodes"].append(
            {"id": "output", "type": "fileOutput", "data": {"config": {"format": "csv", "path": data_path}}}
        )
        graph["edges"].append({"id": "input-output", "source": "input", "target": "output"})
    return graph


def _execute_definition_export(graph, input_path, engine_name, lazy, parameter_lines=None):
    generator = CodeGenerator() if engine_name == "pandas" else PolarsCodeGenerator()
    options = {} if engine_name == "pandas" else {"lazy": lazy}
    code = generator.generate(
        substitute_for_codegen(graph),
        {"data": input_path.as_posix()},
        parameter_lines=parameter_block_lines(graph) if parameter_lines is None else parameter_lines,
        **options,
    )
    namespace = {}
    exec(compile(code, "<model definition export>", "exec"), namespace)  # noqa: S102
    return namespace


@pytest.mark.parametrize("engine_name,lazy", [("pandas", False), ("polars", False), ("polars", True)])
@pytest.mark.parametrize(
    "kind,model_type,parameter",
    [("mlClassifierModel", "logistic_regression", "C"), ("mlRegressorModel", "ridge", "alpha")],
)
@pytest.mark.parametrize("features", [None, [], ["x1"]])
@pytest.mark.parametrize("parameterized", [False, True])
@pytest.mark.parametrize("rows", [0, 24])
def test_model_definition_export_preserves_unfitted_reference(
    definition_input, ml_env, monkeypatch, engine_name, lazy, kind, model_type, parameter, features, parameterized, rows
):
    from sklearn.pipeline import Pipeline

    frame, path = definition_input
    frame = frame.head(rows)
    frame.to_csv(path, index=False)
    original = path.read_bytes()
    config = {
        "model_type": model_type,
        "target_column": "target",
        "feature_columns": features,
        "hyperparameters": {parameter: 0.75},
        "preprocessing": {"numeric_strategy": "robust_scaler"},
        "seed": 42,
        "experiment_name": "not-part-of-definition",
    }
    if parameterized:
        config.update(seed=7, hyperparameters={parameter: 1.25})
    engine = get_engine(engine_name)
    expected = engine.to_pandas(
        get_transformation(kind).execute(engine, {"in": engine.from_pandas(frame)}, config)["model"]
    )
    exported_config = {**config}
    graph = _definition_graph(kind, exported_config, data_path=path.with_name("passthrough.csv").as_posix())
    parameter_lines = None
    if parameterized:
        exported_config.update(
            target_column="{{ label }}", seed="{{ random_seed }}", hyperparameters={parameter: "{{ strength }}"}
        )
        graph["parameters"] = [
            {"name": "label", "type": "string", "default": "not_a_column"},
            {"name": "random_seed", "type": "integer", "default": 42},
            {"name": "strength", "type": "number", "default": 0.75},
        ]
        # Model definitions must use the assignments in the exported script,
        # rather than freezing the graph's original parameter defaults.
        parameter_lines = ["label = 'target'", "random_seed = 7", "strength = 1.25"]

    def reject_fit(*args, **kwargs):
        pytest.fail("A definition export must not fit a pipeline")

    monkeypatch.setattr(Pipeline, "fit", reject_fit)
    namespace = _execute_definition_export(graph, path, engine_name, lazy, parameter_lines)
    references = [
        value
        for value in namespace.values()
        if isinstance(value, pd.DataFrame) and list(value.columns) == list(expected.columns)
    ]
    assert len(references) == 1
    pd.testing.assert_frame_equal(references[0], expected)
    assert references[0][["mlflow_run_id", "model_uri"]].isna().all().all()
    pd.testing.assert_frame_equal(pd.read_csv(path.with_name("passthrough.csv")), frame, check_dtype=False)
    assert path.read_bytes() == original


@pytest.mark.parametrize("engine_name,lazy", [("pandas", False), ("polars", False), ("polars", True)])
@pytest.mark.parametrize("parameterized", [False, True])
@pytest.mark.parametrize(
    "kind,model_type,metrics",
    [
        ("mlClassifierModel", "logistic_regression", ["accuracy", "f1_weighted"]),
        ("mlRegressorModel", "ridge", ["r2", "root_mean_squared_error"]),
    ],
)
def test_model_definition_cross_validation_export_matches_runtime(
    definition_input, ml_env, monkeypatch, engine_name, lazy, kind, model_type, metrics, preprocessing, parameterized
):
    from sklearn import model_selection
    from sklearn.pipeline import Pipeline

    frame, path = definition_input
    frame["x1"] *= 100
    frame.to_csv(path, index=False)
    original = path.read_bytes()
    parameter = "C" if model_type == "logistic_regression" else "alpha"
    strength = 0.02 if parameter == "C" else 30.0
    config = {
        "model_type": model_type,
        "target_column": "target",
        "feature_columns": [],
        "seed": 7,
        "hyperparameters": {parameter: strength},
        "preprocessing": preprocessing,
    }
    engine = get_engine(engine_name)
    native = engine.from_pandas(frame)
    reference = get_transformation(kind).execute(engine, {"in": native}, config)["model"]
    expected = get_transformation("mlCrossValidate").execute(
        engine, {"in": native, "model": reference}, {"cv_strategy": "kfold", "n_splits": 3, "seed": 42}
    )["out"]
    output_path = path.with_name("scores.csv")
    cross_validate = model_selection.cross_validate
    pipeline_fit = Pipeline.fit
    measured = {}
    fit_lengths = []

    def capture_fold_times(*args, **kwargs):
        result = cross_validate(*args, **kwargs)
        measured.update(result)
        return result

    def capture_fits(self, x, y=None, **kwargs):
        if y is not None:
            fit_lengths.append(len(x))
        return pipeline_fit(self, x, y, **kwargs)

    exported_config = config.copy()
    graph = _definition_graph(kind, exported_config, output_path.as_posix())
    parameter_lines = None
    if parameterized:
        exported_config.update(
            target_column="{{ label }}", seed="{{ random_seed }}", hyperparameters={parameter: "{{ strength }}"}
        )
        graph["parameters"] = [
            {"name": "label", "type": "string", "default": "wrong"},
            {"name": "random_seed", "type": "integer", "default": 99},
            {"name": "strength", "type": "number", "default": 1.0},
        ]
        parameter_lines = ["label = 'target'", "random_seed = 7", f"strength = {strength!r}"]
    monkeypatch.setattr(model_selection, "cross_validate", capture_fold_times)
    monkeypatch.setattr(Pipeline, "fit", capture_fits)
    _execute_definition_export(graph, path, engine_name, lazy, parameter_lines)
    actual = pd.read_csv(output_path)
    assert list(actual.columns) == ["fold", *metrics, "fit_time_s"]
    assert actual["fold"].tolist() == [1, 2, 3]
    pd.testing.assert_frame_equal(
        actual.drop(columns=["fit_time_s"]),
        engine.to_pandas(expected).drop(columns=["fit_time_s"]),
        check_dtype=False,
        rtol=1e-9,
        atol=1e-9,
    )
    np.testing.assert_allclose(actual["fit_time_s"], measured["fit_time"], rtol=1e-9, atol=1e-9)
    assert fit_lengths == [16, 16, 16]
    assert path.read_bytes() == original


@pytest.mark.parametrize("engine_name,lazy", [("pandas", False), ("polars", False), ("polars", True)])
def test_train_export_preprocessing_matches_runtime(definition_input, ml_env, engine_name, lazy, preprocessing):
    from sklearn.metrics import r2_score

    frame, path = definition_input
    frame["x1"] *= 100
    frame.to_csv(path, index=False)
    original = path.read_bytes()
    config = {
        "model_type": "ridge",
        "target_column": "target",
        "seed": 7,
        "hyperparameters": {"alpha": 30.0},
        "preprocessing": preprocessing,
    }
    engine = get_engine(engine_name)
    _, metadata = get_transformation("mlTrainRegressor").execute_with_metadata(
        engine, {"in": engine.from_pandas(frame)}, config
    )
    output_path = path.with_name("predictions.csv")
    graph = _train_prediction_graph(config, output_path, {"output_column": "prediction"})
    _execute_definition_export(graph, path, engine_name, lazy)
    actual = pd.read_csv(output_path)
    assert metadata is not None
    assert r2_score(frame["target"], actual["prediction"]) == pytest.approx(metadata.ml_metrics["train_r2"])
    pd.testing.assert_frame_equal(actual.drop(columns=["prediction"]), frame, check_dtype=False)
    assert path.read_bytes() == original


def _train_prediction_graph(config, output_path, prediction_config):
    graph = _definition_graph("mlTrainRegressor", config, data_path=output_path.as_posix())
    graph["nodes"].append({"id": "predict", "type": "mlPredict", "data": {"config": prediction_config}})
    graph["edges"] = [
        graph["edges"][0],
        {"id": "input-predict", "source": "input", "target": "predict", "targetHandle": "in"},
        {
            "id": "model-predict",
            "source": "definition",
            "target": "predict",
            "sourceHandle": "model",
            "targetHandle": "model",
        },
        {"id": "predict-output", "source": "predict", "target": "output"},
    ]
    return graph


@pytest.mark.parametrize("engine_name,lazy", [("pandas", False), ("polars", False), ("polars", True)])
@pytest.mark.parametrize(
    "batch_size,parameterized",
    [(None, False), (1, False), (7, False), (24, False), (30, False), (7, True), (None, True)],
)
def test_predict_export_honors_batch_size(definition_input, monkeypatch, engine_name, lazy, batch_size, parameterized):
    from sklearn.pipeline import Pipeline

    frame, path = definition_input
    original = path.read_bytes()
    output_path = path.with_name("batched.csv")
    graph = _train_prediction_graph(
        {"model_type": "ridge", "target_column": "target", "seed": 42},
        output_path,
        {"output_column": "prediction", "batch_size": "{{ batch }}" if parameterized else batch_size},
    )
    parameter_lines = None
    if parameterized:
        graph["parameters"] = [{"name": "batch", "type": "integer", "default": 2}]
        parameter_lines = [f"batch = {batch_size!r}"]
    predict = Pipeline.predict
    calls = []

    def capture_predictions(self, x, **kwargs):
        calls.append((len(x), list(x.columns), x.index.tolist()))
        return predict(self, x, **kwargs)

    monkeypatch.setattr(Pipeline, "predict", capture_predictions)
    namespace = _execute_definition_export(graph, path, engine_name, lazy, parameter_lines)
    chunks = (
        [list(range(i, min(i + batch_size, len(frame)))) for i in range(0, len(frame), batch_size)]
        if batch_size
        else [list(range(len(frame)))]
    )
    assert calls == [(len(chunk), ["x1", "x2"], chunk) for chunk in chunks]
    models = [value for value in namespace.values() if isinstance(value, Pipeline)]
    assert len(models) == 1
    actual = pd.read_csv(output_path)
    np.testing.assert_allclose(actual["prediction"], predict(models[0], frame[["x1", "x2"]]), rtol=1e-9, atol=1e-9)
    pd.testing.assert_frame_equal(actual.drop(columns=["prediction"]), frame, check_dtype=False)
    assert path.read_bytes() == original
