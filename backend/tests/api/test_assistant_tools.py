"""Assistant policy, node models and read-only catalog tools."""

import json

import pytest

from app.core.config import get_settings
from app.engine.node_metadata import BUILTIN_NODE_META
from app.engine.registry import get_transformation
from app.engine.transformations.ml.cross_validation import CV_STRATEGIES
from app.ml.models import MODEL_CATALOG
from app.plugins.builtin import CORE_PROVIDER
from app.services import assistant_policy as policy
from app.services.assistant_nodes import MODELS, column_fields
from app.services.assistant_tools import catalog
from app.services.assistant_tools.context import ToolContext, ToolError

DEFAULTS = {m.type: m.default_config for m in BUILTIN_NODE_META}
IO = policy.INPUTS | {"fileOutput"}
# Values for the fields each node requires beyond its catalog defaults.
FIXTURES = {
    "fileInput": {"dataset_id": "d"},
    **{t: {"dataset_id": "d"} for t in ("csvInput", "excelInput", "parquetInput", "jsonInput", "textInput")},
    "fileOutput": {"dataset_name": "result"},
    "filterRows": {"column": "a", "value2": 2},
    "filterExpression": {"expression": "a > 1"},
    "sortRows": {"columns": ["a"]},
    "castDtypes": {"casts": {"a": "integer"}},
    "dropColumns": {"columns": ["a"]},
    "renameColumns": {"mapping": {"a": "b"}},
    "selectColumns": {"columns": ["a"]},
    "combineColumns": {"columns": ["a", "b"], "new_column": "ab"},
    "coalesceColumns": {"columns": ["a", "b"], "new_column": "ab"},
    "replaceValues": {"column": "a"},
    "stringTransform": {"column": "a", "find": "x", "width": 4},
    "calculatedColumn": {"column_name": "c", "expression": "a * 2"},
    "splitColumn": {"column": "a", "into": ["x", "y"]},
    "mapValues": {"column": "a", "mapping": {"x": 1}},
    "groupByAggregate": {"group_by": ["a"], "aggregations": {"b": "sum"}},
    "join": {"on": "a"},
    "unpivot": {"id_vars": ["a"]},
    "pivot": {"index": ["a"], "columns": "b", "values": "c"},
    "explodeRows": {"column": "a"},
    "removeOutliers": {"columns": ["a"]},
    "roundNumbers": {"columns": ["a"]},
    "binColumn": {"column": "a", "new_column": "bin"},
    "extractDateParts": {"column": "a", "parts": ["year"]},
    "parseDates": {"columns": ["a"]},
    "windowFunction": {"new_column": "w", "target": "a", "order_by": ["a"]},
    "conditionalColumn": {"new_column": "f", "rules": [{"column": "a", "operator": "==", "value": 1, "result": True}]},
    "rollingAggregate": {"target": "a", "new_column": "r"},
    "rowDifference": {"target": "a", "new_column": "r"},
    "dateDifference": {"start_column": "a", "end_column": "b", "new_column": "d"},
    "assertValueRange": {"column": "a", "min": 0},
    "assertExpression": {"expression": "a > 0"},
    "assertRowCount": {"min_rows": 1},
    "assertValuesInSet": {"column": "a", "allowed": [1]},
    "chartBar": {"x": "a", "y": "b"},
    "chartLine": {"x": "a", "y_columns": ["b"]},
    "chartArea": {"x": "a", "y_columns": ["b"]},
    "chartScatter": {"x": "a", "y": "b"},
    "chartPie": {"category": "a"},
    "chartHistogram": {"column": "a"},
    "chartBoxPlot": {"column": "a"},
    "scaleFeatures": {"columns": ["a"]},
    "encodeCategories": {"columns": ["a"]},
    "selectFeatures": {"target_column": "t"},
    "mlClassifierModel": {"target_column": "t"},
    "mlRegressorModel": {"target_column": "t"},
    "mlTrainClassifier": {"target_column": "t"},
    "mlTrainRegressor": {"target_column": "t"},
    "mlEvaluate": {"target_column": "t"},
    "mlCrossValidate": {"group_column": "g"},
}


@pytest.fixture
def ml(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "ML_ENABLED", True)


def filled(node_type):
    return {**DEFAULTS[node_type], **FIXTURES.get(node_type, {})}


def enum_fields(schema):
    """(field, values, is_list) for every enumerated property, including list items."""
    for name, prop in schema["properties"].items():
        for option in [prop, *prop.get("anyOf", [])]:
            if "enum" in option:
                yield name, option["enum"], False
            elif "enum" in option.get("items", {}):
                yield name, option["items"]["enum"], True


@pytest.mark.parametrize("node_type", sorted(policy.POLICY))
def test_every_allowed_node_matches_engine_validation_and_catalog(ml, node_type):
    from pydantic import ValidationError

    assert node_type in catalog.allowed_specs()
    model = MODELS[node_type]
    config = filled(node_type)
    model.model_validate(config, strict=True)
    if node_type in IO:
        return
    engine = get_transformation(node_type)
    engine.validate_config(config)
    # Every enumerated value the model accepts must also pass the engine's own validation.
    for field, values, is_list in enum_fields(model.model_json_schema()):
        for value in values:
            candidate = {**config, field: [value] if is_list else value}
            try:
                model.model_validate(candidate, strict=True)
            except ValidationError:
                continue
            engine.validate_config(candidate)


def test_registry_enums_and_denied_nodes(ml):
    schema = MODELS["mlCrossValidate"].model_json_schema()
    assert schema["properties"]["cv_strategy"]["enum"] == sorted(CV_STRATEGIES)
    for node_type, task in [
        ("mlClassifierModel", "classification"),
        ("mlTrainRegressor", "regression"),
        ("mlTrainClustering", "clustering"),
        ("mlTrainDimReduction", "dimensionality_reduction"),
    ]:
        enum = MODELS[node_type].model_json_schema()["properties"]["model_type"]["enum"]
        assert enum == sorted(n for n, s in MODEL_CATALOG.items() if s.task == task)
    assert not set(policy.DENIED) & set(policy.POLICY)
    assert set(policy.POLICY) <= set(MODELS)
    # A plugin cannot claim an allowed type under another provider.
    assert policy.tier("filterRows", "acme.plugin") is None
    assert policy.tier("filterRows", CORE_PROVIDER) == "allow"
    assert policy.tier("filterExpression", CORE_PROVIDER) == "review"
    assert column_fields("chartBar") == {"x": "column", "y": "column", "group_by": "column"}
    assert column_fields("renameColumns") == {"mapping": "column_keys"}


async def test_list_and_schema_tools_hide_denied_nodes(ml, db_session):
    ctx = ToolContext(db_session, "project", {})
    listed = {n["type"]: n for n in (await catalog.list_node_types(ctx, catalog.ListNodeTypes()))["nodes"]}
    assert set(listed) == set(policy.POLICY)
    assert listed["join"]["inputs"] == [
        {"id": "left", "kind": "dataframe", "required": True, "multi": False},
        {"id": "right", "kind": "dataframe", "required": True, "multi": False},
    ]
    assert listed["trainTestSplit"]["outputs"] == ["train", "test"]
    assert listed["chartBar"]["terminal"] and listed["fileOutput"]["terminal"]
    assert listed["calculatedColumn"]["tier"] == "review"
    charts = await catalog.list_node_types(ctx, catalog.ListNodeTypes(category="chart"))
    assert {n["category"] for n in charts["nodes"]} == {"chart"}
    args = catalog.GetNodeSchema(types=["pythonTransform", "sqlOutput", "sortRows"])
    schemas = await catalog.get_node_schema(ctx, args)
    assert schemas["pythonTransform"] == schemas["sqlOutput"] == {"error": "policy"}
    assert schemas["sortRows"]["schema"]["additionalProperties"] is False
    assert schemas["sortRows"]["defaults"] == DEFAULTS["sortRows"]


@pytest.mark.parametrize(
    ("expression", "accepted"),
    [
        ("amount > 2 and abs(price) <= 10", True),
        ("`unit price` * 2 + 1e3", True),
        ("city == 'Lyon'", True),
        # Forbidden constructs are rejected inside quoted literals too.
        ("city == 'x; import os'", False),
        ("@limit < amount", False),
        ("amount.__class__", False),
        ("amount.str.len() > 2", False),
        ("unknown > 1", False),
        ("`missing` > 1", False),
        ("amount > 1; price", False),
        ("amount\n> 1", False),
        ("(lambda: 1)()", False),
        ("amount > " + "1" * 300, False),
    ],
)
def test_expression_guard(expression, accepted):
    columns = ["amount", "price", "unit price", "city"]
    if accepted:
        policy.guard_expression(expression, columns)
    else:
        with pytest.raises(policy.PolicyError):
            policy.guard_expression(expression, columns)


@pytest.mark.parametrize(
    ("node_type", "config", "rows", "code"),
    [
        ("filterRows", {"column": "{{ secret }}"}, None, "policy"),
        ("renameColumns", {"mapping": {"a": "x{{p}}"}}, None, "policy"),
        ("mlPredict", {"model_uri": "runs:/x/model"}, None, "policy"),
        (
            "mlTrainRegressor",
            {"model_type": "random_forest_regressor", "hyperparameters": {"n_jobs": -1}},
            None,
            "policy",
        ),
        ("mlTrainRegressor", {"model_type": "ridge", "hyperparameters": {"solver": "auto"}}, None, "policy"),
        (
            "mlTrainRegressor",
            {"model_type": "random_forest_regressor", "hyperparameters": {"n_estimators": 501}},
            None,
            "limit",
        ),
        (
            "mlTrainRegressor",
            {"model_type": "random_forest_regressor", "hyperparameters": {"max_depth": 65}},
            None,
            "limit",
        ),
        ("mlCrossValidate", {"n_splits": 21}, None, "limit"),
        ("mlCrossValidate", {"n_repeats": 6}, None, "limit"),
        ("mlCrossValidate", {"cv_strategy": "leave_one_out"}, 2001, "limit"),
        ("mlCrossValidate", {"cv_strategy": "leave_one_out"}, None, "limit"),
        ("mlCrossValidate", {"cv_strategy": "leave_one_out"}, 2000, None),
        (
            "mlTrainRegressor",
            {"model_type": "random_forest_regressor", "hyperparameters": {"n_estimators": 500}},
            None,
            None,
        ),
    ],
)
def test_field_rules(node_type, config, rows, code):
    if code is None:
        policy.check_fields(node_type, config, rows)
    else:
        with pytest.raises(policy.PolicyError) as error:
            policy.check_fields(node_type, config, rows)
        assert error.value.code == code


SECRET = "private-cell-value-5512"


async def test_dataset_tools_share_refs_not_values(client, db_session):
    uploaded = await client.post(
        "/api/datasets/upload", files={"file": ("hidden.csv", f"private_name,amount\n{SECRET},3\n{SECRET},5\n")}
    )
    dataset = uploaded.json()
    project = (await client.post("/api/projects", json={"name": "Elsewhere"})).json()
    ctx = ToolContext(db_session, dataset["project_id"], {}, datasets={"d0": dataset["id"]})
    shape = await catalog.get_dataset_schema(ctx, catalog.GetDatasetSchema(dataset="d0"))
    assert shape["columns"] == [{"ref": "c0", "type": "string"}, {"ref": "c1", "type": "integer"}]
    assert shape["row_count"] == 2 and shape["profiled"]
    args = catalog.ProfileColumns(source="d0", columns=["c0", "c1"])
    profiled = await catalog.profile_columns(ctx, args)
    assert profiled["columns"][0] == {
        "ref": "c0",
        "type": "string",
        "null_frac": 0.0,
        "distinct": 1,
        "unique": False,
        "numeric": False,
    }
    assert profiled["columns"][1]["numeric"] and profiled["columns"][1]["unique"]
    sent = json.dumps([shape, profiled])
    assert SECRET not in sent and "private_name" not in sent and "hidden" not in sent and dataset["id"] not in sent
    ctx.share_names = ctx.share_values = True
    named = await catalog.get_dataset_schema(ctx, catalog.GetDatasetSchema(dataset="d0"))
    assert named["columns"][0]["name"] == "private_name"
    assert (await catalog.profile_columns(ctx, args))["columns"][1]["max"] == 5
    with pytest.raises(ToolError, match="column"):
        await catalog.profile_columns(ctx, catalog.ProfileColumns(source="d0", columns=["c9"]))
    with pytest.raises(ToolError):
        await catalog.profile_columns(ctx, catalog.ProfileColumns(source="n0", columns=["c0"]))
    foreign = ToolContext(db_session, project["id"], {}, datasets={"d0": dataset["id"]})
    with pytest.raises(Exception, match="project"):
        await catalog.get_dataset_schema(foreign, catalog.GetDatasetSchema(dataset="d0"))
