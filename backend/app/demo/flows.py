"""React-Flow-compatible graph builders for the demo flows.

Each builder takes the demo dataset ids (keyed by CSV file name) and returns a
``(name, description, graph_json)`` tuple. Graphs only use node types that exist
in the engine registry (``app/engine/registry.py``) plus the csv input/output
nodes from ``app/engine/node_kinds.py`` — no chart/visualize nodes.

Node layout (``position``) is purely cosmetic for the editor; the executor
ignores it. Input nodes carry ``dataset_id`` (and pin the latest version via
``dataset_version``) so a run resolves the exact demo data.
"""

from __future__ import annotations

from typing import Any

# (name, description, graph) tuples are what the seeder persists.
DemoFlow = tuple[str, str, dict[str, Any]]


def _input(node_id: str, dataset_id: str, x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "csvInput",
        "position": {"x": x, "y": y},
        "data": {"config": {"dataset_id": dataset_id, "dataset_version": 1}},
    }


def _node(node_id: str, node_type: str, config: dict[str, Any], x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": x, "y": y},
        "data": {"config": config},
    }


def _output(node_id: str, dataset_name: str, x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "fileOutput",
        "position": {"x": x, "y": y},
        "data": {"config": {"format": "csv", "dataset_name": dataset_name}},
    }


def _edge(
    source: str,
    target: str,
    target_handle: str | None = None,
    source_handle: str | None = None,
) -> dict[str, Any]:
    suffix = "".join(f"-{h}" for h in (source_handle, target_handle) if h)
    edge: dict[str, Any] = {
        "id": f"e-{source}-{target}{suffix}",
        "source": source,
        "target": target,
    }
    if source_handle is not None:
        edge["sourceHandle"] = source_handle
    if target_handle is not None:
        edge["targetHandle"] = target_handle
    return edge


def build_demo_flows(dataset_ids: dict[str, str], include_ml: bool = False) -> list[DemoFlow]:
    """Return every demo flow wired to the given dataset ids (by CSV file name).

    When ``include_ml`` is set (the ML extension is installed), the machine-learning
    example flows are appended — they reference the ``iris.csv`` / ``house_prices.csv``
    datasets that :func:`build_demo_frames` adds in the same mode."""
    flows = [
        _clean_customers(dataset_ids),
        _order_revenue_by_month(dataset_ids),
        _customer_orders_join(dataset_ids),
        _full_sales_mart(dataset_ids),
    ]
    if include_ml:
        flows += [
            _iris_quick_classifier(dataset_ids),
            _iris_train_validate_evaluate(dataset_ids),
            _house_prices_regression(dataset_ids),
            _iris_pca_explore(dataset_ids),
        ]
    return flows


# ---------------------------------------------------------------------------
# 1. Clean Customers — linear cleaning pipeline.
# ---------------------------------------------------------------------------


def _clean_customers(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_customers", ds["customers.csv"], 0, 0),
            _node(
                "fill_age",
                "fillNulls",
                {"columns": ["age"], "strategy": "median"},
                250,
                0,
            ),
            _node(
                "norm_country",
                "stringTransform",
                {"column": "country", "operation": "upper"},
                500,
                0,
            ),
            _node(
                "parse_signup",
                "parseDates",
                {"columns": ["signup_date"], "errors": "coerce"},
                750,
                0,
            ),
            _output("out_customers", "customers_clean", 1000, 0),
        ],
        "edges": [
            _edge("in_customers", "fill_age"),
            _edge("fill_age", "norm_country"),
            _edge("norm_country", "parse_signup"),
            _edge("parse_signup", "out_customers"),
        ],
    }
    return (
        "Clean Customers",
        "Fill missing ages, normalize country casing, and parse the signup date from text into a real date.",
        graph,
    )


# ---------------------------------------------------------------------------
# 2. Order Revenue by Month — date handling + aggregation.
# ---------------------------------------------------------------------------


def _order_revenue_by_month(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_orders", ds["orders.csv"], 0, 0),
            _node(
                "parse_date",
                "parseDates",
                {"columns": ["order_date"], "errors": "coerce"},
                250,
                0,
            ),
            _node(
                "date_parts",
                "extractDateParts",
                {"column": "order_date", "parts": ["year", "month"]},
                500,
                0,
            ),
            _node(
                "completed_only",
                "filterRows",
                {"column": "status", "operator": "==", "value": "completed"},
                750,
                0,
            ),
            _node(
                "by_month",
                "groupByAggregate",
                {
                    "group_by": ["order_date_year", "order_date_month"],
                    "aggregations": {"amount": "sum"},
                },
                1000,
                0,
            ),
            _node(
                "sort_month",
                "sortRows",
                {"columns": ["order_date_year", "order_date_month"], "ascending": True},
                1250,
                0,
            ),
            _output("out_revenue", "order_revenue_by_month", 1500, 0),
        ],
        "edges": [
            _edge("in_orders", "parse_date"),
            _edge("parse_date", "date_parts"),
            _edge("date_parts", "completed_only"),
            _edge("completed_only", "by_month"),
            _edge("by_month", "sort_month"),
            _edge("sort_month", "out_revenue"),
        ],
    }
    return (
        "Order Revenue by Month",
        "Parse order dates, extract year/month, keep completed orders, then total "
        "revenue per month sorted chronologically.",
        graph,
    )


# ---------------------------------------------------------------------------
# 3. Customer Orders Join — two cleaned branches joined together.
# ---------------------------------------------------------------------------


def _customer_orders_join(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            # Customer branch.
            _input("in_customers", ds["customers.csv"], 0, 0),
            _node(
                "fill_age",
                "fillNulls",
                {"columns": ["age"], "strategy": "median"},
                250,
                0,
            ),
            _node(
                "norm_country",
                "stringTransform",
                {"column": "country", "operation": "upper"},
                500,
                0,
            ),
            # Orders branch.
            _input("in_orders", ds["orders.csv"], 0, 250),
            _node("dedupe_orders", "removeDuplicates", {"keep": "first"}, 250, 250),
            _node(
                "no_outliers",
                "removeOutliers",
                {"columns": ["amount"], "method": "iqr", "action": "drop"},
                500,
                250,
            ),
            # Join customers <- orders on the customer id.
            _node(
                "join",
                "join",
                {"left_on": ["id"], "right_on": ["customer_id"], "how": "inner"},
                800,
                125,
            ),
            _node(
                "net_amount",
                "calculatedColumn",
                {"column_name": "net_amount", "expression": "amount * 0.9"},
                1050,
                125,
            ),
            _output("out_joined", "customer_orders", 1300, 125),
        ],
        "edges": [
            _edge("in_customers", "fill_age"),
            _edge("fill_age", "norm_country"),
            _edge("in_orders", "dedupe_orders"),
            _edge("dedupe_orders", "no_outliers"),
            _edge("norm_country", "join", "left"),
            _edge("no_outliers", "join", "right"),
            _edge("join", "net_amount"),
            _edge("net_amount", "out_joined"),
        ],
    }
    return (
        "Customer Orders Join",
        "Clean customers and orders independently, join them on the customer id, then compute a discounted net amount.",
        graph,
    )


# ---------------------------------------------------------------------------
# 4. Full Sales Mart — three inputs, chained joins, conditional column.
# ---------------------------------------------------------------------------


def _full_sales_mart(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            # order_items branch.
            _input("in_items", ds["order_items.csv"], 0, 0),
            _node(
                "line_total",
                "calculatedColumn",
                {"column_name": "line_total", "expression": "quantity * unit_price"},
                250,
                0,
            ),
            # products branch (clean missing prices).
            _input("in_products", ds["products.csv"], 0, 250),
            _node(
                "fill_price",
                "fillNulls",
                {"columns": ["price"], "strategy": "mean"},
                250,
                250,
            ),
            # items <- products on product_id.
            _node(
                "join_products",
                "join",
                {"on": "product_id", "how": "left"},
                550,
                125,
            ),
            # orders branch.
            _input("in_orders", ds["orders.csv"], 0, 500),
            _node("dedupe_orders", "removeDuplicates", {"keep": "first"}, 250, 500),
            # (items+products) <- orders on order_id.
            _node(
                "join_orders",
                "join",
                {"on": "order_id", "how": "left"},
                850,
                300,
            ),
            # Revenue per product category.
            _node(
                "by_category",
                "groupByAggregate",
                {
                    "group_by": ["category"],
                    "aggregations": {"line_total": "sum", "order_id": "count"},
                },
                1100,
                300,
            ),
            # Label categories by revenue tier.
            _node(
                "tier",
                "conditionalColumn",
                {
                    "new_column": "revenue_tier",
                    "rules": [
                        {
                            "column": "line_total",
                            "operator": ">=",
                            "value": 5000,
                            "result": "high",
                        },
                        {
                            "column": "line_total",
                            "operator": ">=",
                            "value": 1000,
                            "result": "medium",
                        },
                    ],
                    "default": "low",
                },
                1350,
                300,
            ),
            _output("out_mart", "sales_mart", 1600, 300),
        ],
        "edges": [
            _edge("in_items", "line_total"),
            _edge("in_products", "fill_price"),
            _edge("line_total", "join_products", "left"),
            _edge("fill_price", "join_products", "right"),
            _edge("in_orders", "dedupe_orders"),
            _edge("join_products", "join_orders", "left"),
            _edge("dedupe_orders", "join_orders", "right"),
            _edge("join_orders", "by_category"),
            _edge("by_category", "tier"),
            _edge("tier", "out_mart"),
        ],
    }
    return (
        "Full Sales Mart",
        "Join order items to products and orders, total revenue per category, and "
        "label each category with a revenue tier.",
        graph,
    )


# ---------------------------------------------------------------------------
# Machine-learning demo flows (only seeded when the [ml] extra is installed)
# ---------------------------------------------------------------------------

_IRIS_FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]


# 5. Iris — Quick Classifier: the smallest end-to-end modeling flow.
def _iris_quick_classifier(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_iris", ds["iris.csv"], 0, 0),
            _node(
                "split",
                "trainTestSplit",
                {"test_size": 0.25, "stratify_column": "species", "seed": 42},
                250,
                0,
            ),
            _node(
                "train",
                "mlTrainClassifier",
                {
                    "model_type": "random_forest_classifier",
                    "target_column": "species",
                    "feature_columns": _IRIS_FEATURES,
                    "hyperparameters": {},
                    "seed": 42,
                },
                500,
                0,
            ),
        ],
        "edges": [
            _edge("in_iris", "split"),
            _edge("split", "train", target_handle="in", source_handle="train"),
        ],
        "engine": "pandas",
    }
    return (
        "Iris — Quick Classifier",
        "Split the iris data, train a random-forest classifier on the training set, "
        "and log it to MLflow. The smallest end-to-end modeling flow.",
        graph,
    )


# 6. Iris — Train, Validate & Evaluate: scaling, stratified split, cross-validation,
#    held-out evaluation, and feature importance.
def _iris_train_validate_evaluate(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_iris", ds["iris.csv"], 0, 100),
            _node("scale", "scaleFeatures", {"columns": _IRIS_FEATURES, "method": "standard"}, 240, 100),
            _node(
                "split",
                "trainTestSplit",
                {"test_size": 0.25, "stratify_column": "species", "seed": 42},
                480,
                100,
            ),
            _node(
                "train",
                "mlTrainClassifier",
                {
                    "model_type": "random_forest_classifier",
                    "target_column": "species",
                    "feature_columns": _IRIS_FEATURES,
                    "hyperparameters": {},
                    "cross_validate": True,
                    "cv_folds": 5,
                    "seed": 42,
                },
                720,
                0,
            ),
            _node(
                "predict",
                "mlPredict",
                {"output_column": "prediction"},
                960,
                100,
            ),
            _node(
                "evaluate",
                "mlEvaluate",
                {
                    "task_type": "classification",
                    "target_column": "species",
                    "prediction_column": "prediction",
                },
                1200,
                100,
            ),
            _output("out_metrics", "iris_metrics", 1440, 100),
            _node("importance", "featureImportance", {"top_n": 4}, 960, 260),
            _output("out_importance", "iris_feature_importance", 1200, 260),
        ],
        "edges": [
            _edge("in_iris", "scale"),
            _edge("scale", "split"),
            _edge("split", "train", target_handle="in", source_handle="train"),
            _edge("split", "predict", target_handle="in", source_handle="test"),
            _edge("train", "predict", target_handle="model"),
            _edge("predict", "evaluate"),
            _edge("evaluate", "out_metrics"),
            _edge("train", "importance", target_handle="model"),
            _edge("importance", "out_importance"),
        ],
        "engine": "pandas",
    }
    return (
        "Iris — Train, Validate & Evaluate",
        "Scale features, stratify a train/test split, cross-validate a classifier, "
        "evaluate it on the held-out set, and rank feature importance.",
        graph,
    )


# 7. House Prices — Regression: a full regression train/test/evaluate flow.
def _house_prices_regression(ds: dict[str, str]) -> DemoFlow:
    features = ["area", "bedrooms", "age", "distance_to_city"]
    graph = {
        "nodes": [
            _input("in_houses", ds["house_prices.csv"], 0, 0),
            _node("split", "trainTestSplit", {"test_size": 0.25, "seed": 42}, 250, 0),
            _node(
                "train",
                "mlTrainRegressor",
                {
                    "model_type": "random_forest_regressor",
                    "target_column": "price",
                    "feature_columns": features,
                    "hyperparameters": {},
                    "seed": 42,
                },
                500,
                -60,
            ),
            _node("predict", "mlPredict", {"output_column": "prediction"}, 750, 0),
            _node(
                "evaluate",
                "mlEvaluate",
                {
                    "task_type": "regression",
                    "target_column": "price",
                    "prediction_column": "prediction",
                },
                1000,
                0,
            ),
            _output("out_metrics", "house_price_metrics", 1250, 0),
        ],
        "edges": [
            _edge("in_houses", "split"),
            _edge("split", "train", target_handle="in", source_handle="train"),
            _edge("split", "predict", target_handle="in", source_handle="test"),
            _edge("train", "predict", target_handle="model"),
            _edge("predict", "evaluate"),
            _edge("evaluate", "out_metrics"),
        ],
        "engine": "pandas",
    }
    return (
        "House Prices — Regression",
        "Predict house prices with a random-forest regressor: split, train, predict on "
        "the held-out set, and evaluate with regression metrics (R², RMSE, MAE).",
        graph,
    )


# 8. Iris — PCA Explore: scale then compress to 2 components for visualization.
def _iris_pca_explore(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_iris", ds["iris.csv"], 0, 0),
            _node("scale", "scaleFeatures", {"columns": _IRIS_FEATURES, "method": "standard"}, 250, 0),
            _node(
                "pca",
                "reduceDimensions",
                {"method": "pca", "n_components": 2, "columns": _IRIS_FEATURES},
                500,
                0,
            ),
            _output("out_pca", "iris_pca_components", 750, 0),
        ],
        "edges": [
            _edge("in_iris", "scale"),
            _edge("scale", "pca"),
            _edge("pca", "out_pca"),
        ],
        "engine": "pandas",
    }
    return (
        "Iris — PCA Explore",
        "Standardize the four measurements and compress them to two principal "
        "components with PCA — ready to chart or cluster.",
        graph,
    )
