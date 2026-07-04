# SPDX-License-Identifier: AGPL-3.0-only
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

from app.engine.node_metadata import NODE_META_BY_TYPE

# (name, description, graph) tuples are what the seeder persists.
DemoFlow = tuple[str, str, dict[str, Any]]


def _label_for(node_type: str) -> str:
    """Human-readable label for a node type, matching what the editor's own
    node-creation path (`createFlowNode` / `nodeCatalog.ts`) sets by default —
    reused from the backend's node catalog (`app.engine.node_metadata`) so the
    demo seed never regresses to showing the raw camelCase type as its label."""
    meta = NODE_META_BY_TYPE.get(node_type)
    return meta.label if meta is not None else node_type


def _input(node_id: str, dataset_id: str, x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "fileInput",
        "position": {"x": x, "y": y},
        "data": {
            "label": _label_for("fileInput"),
            "config": {"dataset_id": dataset_id, "dataset_version": 1, "format": "csv"},
        },
    }


def _node(node_id: str, node_type: str, config: dict[str, Any], x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": x, "y": y},
        "data": {"label": _label_for(node_type), "config": config},
    }


def _output(node_id: str, dataset_name: str, x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "fileOutput",
        "position": {"x": x, "y": y},
        "data": {"label": _label_for("fileOutput"), "config": {"format": "csv", "dataset_name": dataset_name}},
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
        _lead_intake_cleanup(dataset_ids),
        _web_event_engagement(dataset_ids),
        _survey_quality_contracts(dataset_ids),
        _regional_target_variance(dataset_ids),
        _product_catalog_scoring(dataset_ids),
    ]
    if include_ml:
        flows += [
            _iris_quick_classifier(dataset_ids),
            _iris_train_validate_evaluate(dataset_ids),
            _house_prices_regression(dataset_ids),
            _iris_pca_explore(dataset_ids),
            _iris_cross_validation_report(dataset_ids),
            _iris_knn_with_encoded_species(dataset_ids),
            _house_price_feature_selection(dataset_ids),
            _house_price_customer_segments(dataset_ids),
            _house_price_pca_model(dataset_ids),
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
# 5. Lead Intake Cleanup — column prep, coalescing, mapping, and type cleanup.
# ---------------------------------------------------------------------------


def _lead_intake_cleanup(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_leads", ds["leads.csv"], 0, 0),
            _node(
                "contact_email",
                "coalesceColumns",
                {"columns": ["email", "backup_email"], "new_column": "contact_email", "keep_original": True},
                240,
                0,
            ),
            _node("has_contact", "dropNulls", {"subset": ["contact_email"], "how": "any"}, 480, 0),
            _node(
                "split_name",
                "splitColumn",
                {"column": "full_name", "mode": "delimiter", "delimiter": " ", "into": ["first_name", "last_name"]},
                720,
                0,
            ),
            _node(
                "display_name",
                "combineColumns",
                {"columns": ["last_name", "first_name"], "new_column": "display_name", "separator": ", "},
                960,
                0,
            ),
            _node("cast_age", "castDtypes", {"casts": {"age_text": "integer"}, "errors": "coerce"}, 1200, 0),
            _node("source_case", "replaceValues", {"column": "source", "to_replace": "WEB", "value": "web"}, 1440, 0),
            _node(
                "country_region",
                "mapValues",
                {
                    "column": "country",
                    "new_column": "region",
                    "mapping": {"US": "North America", "CA": "North America", "MX": "North America", "UK": "Europe"},
                    "default": "Other",
                    "use_default": True,
                },
                1680,
                0,
            ),
            _node("drop_raw", "dropColumns", {"columns": ["email", "backup_email", "utm_campaign"]}, 1920, 0),
            _node(
                "select_final",
                "selectColumns",
                {
                    "columns": [
                        "lead_id",
                        "display_name",
                        "contact_email",
                        "country",
                        "region",
                        "source",
                        "age_text",
                        "score",
                    ]
                },
                2160,
                0,
            ),
            _node("rename_age", "renameColumns", {"mapping": {"age_text": "age"}}, 2400, 0),
            _output("out_leads", "lead_intake_clean", 2640, 0),
        ],
        "edges": [
            _edge("in_leads", "contact_email"),
            _edge("contact_email", "has_contact"),
            _edge("has_contact", "split_name"),
            _edge("split_name", "display_name"),
            _edge("display_name", "cast_age"),
            _edge("cast_age", "source_case"),
            _edge("source_case", "country_region"),
            _edge("country_region", "drop_raw"),
            _edge("drop_raw", "select_final"),
            _edge("select_final", "rename_age"),
            _edge("rename_age", "out_leads"),
        ],
    }
    return (
        "Lead Intake Cleanup",
        "Turn messy inbound leads into a clean contact list: coalesce emails, split and recombine names, "
        "cast age text, map countries to regions, and publish only the final columns.",
        graph,
    )


# ---------------------------------------------------------------------------
# 6. Web Event Engagement — time deltas, windows, rolling metrics, sampling.
# ---------------------------------------------------------------------------


def _web_event_engagement(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_events", ds["web_events.csv"], 0, 0),
            _node("parse_dates", "parseDates", {"columns": ["signup_date", "event_time"], "errors": "coerce"}, 240, 0),
            _node(
                "days_since_signup",
                "dateDifference",
                {
                    "start_column": "signup_date",
                    "end_column": "event_time",
                    "unit": "days",
                    "new_column": "days_active",
                },
                480,
                0,
            ),
            _node(
                "session_number",
                "windowFunction",
                {
                    "function": "row_number",
                    "partition_by": ["user_id"],
                    "order_by": ["event_time"],
                    "new_column": "session_number",
                },
                720,
                0,
            ),
            _node(
                "rolling_revenue",
                "rollingAggregate",
                {
                    "target": "revenue",
                    "function": "mean",
                    "window": 3,
                    "min_periods": 1,
                    "partition_by": ["user_id"],
                    "order_by": ["event_time"],
                    "new_column": "rolling_revenue_3",
                },
                960,
                0,
            ),
            _node(
                "revenue_delta",
                "rowDifference",
                {
                    "target": "revenue",
                    "method": "diff",
                    "periods": 1,
                    "partition_by": ["user_id"],
                    "order_by": ["event_time"],
                    "new_column": "revenue_delta",
                },
                1200,
                0,
            ),
            _node(
                "engaged_paid",
                "filterExpression",
                {"expression": "duration_sec >= 60 and revenue >= 0"},
                1440,
                0,
            ),
            _node("explode_tags", "explodeRows", {"column": "tags", "delimiter": ","}, 1680, 0),
            _node(
                "round_metrics",
                "roundNumbers",
                {"columns": ["revenue", "rolling_revenue_3"], "decimals": 2},
                1920,
                0,
            ),
            _node("sample_review", "sampleRows", {"frac": 0.5, "seed": 7}, 2160, 0),
            _node("top_review", "limitRows", {"n": 40, "offset": 0}, 2400, 0),
            _output("out_events", "web_event_engagement", 2640, 0),
        ],
        "edges": [
            _edge("in_events", "parse_dates"),
            _edge("parse_dates", "days_since_signup"),
            _edge("days_since_signup", "session_number"),
            _edge("session_number", "rolling_revenue"),
            _edge("rolling_revenue", "revenue_delta"),
            _edge("revenue_delta", "engaged_paid"),
            _edge("engaged_paid", "explode_tags"),
            _edge("explode_tags", "round_metrics"),
            _edge("round_metrics", "sample_review"),
            _edge("sample_review", "top_review"),
            _edge("top_review", "out_events"),
        ],
    }
    return (
        "Web Event Engagement",
        "Parse event timestamps, calculate days since signup, add per-user session numbers, rolling revenue, "
        "row-over-row revenue deltas, explode tags, and sample rows for review.",
        graph,
    )


# ---------------------------------------------------------------------------
# 7. Survey Quality Contracts — assertions plus binning and reshape.
# ---------------------------------------------------------------------------


def _survey_quality_contracts(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_survey", ds["survey_responses.csv"], 0, 0),
            _node("required_ids", "assertNotNull", {"columns": ["response_id", "account_id"], "mode": "error"}, 240, 0),
            _node("unique_response", "assertUnique", {"columns": ["response_id"], "mode": "error"}, 480, 0),
            _node("score_range", "assertValueRange", {"column": "satisfaction", "min": 1, "max": 5}, 720, 0),
            _node(
                "plan_domain",
                "assertValuesInSet",
                {"column": "plan", "allowed": ["free", "team", "enterprise"], "allow_null": False},
                960,
                0,
            ),
            _node(
                "valid_average",
                "assertExpression",
                {"expression": "satisfaction >= 1 and satisfaction <= 5"},
                1200,
                0,
            ),
            _node("row_bounds", "assertRowCount", {"min_rows": 20, "max_rows": 100}, 1440, 0),
            _node(
                "satisfaction_band",
                "binColumn",
                {
                    "column": "satisfaction",
                    "new_column": "satisfaction_band",
                    "method": "equalwidth",
                    "bins": 3,
                    "labels": ["low", "medium", "high"],
                },
                1680,
                0,
            ),
            _node(
                "wide_to_long",
                "unpivot",
                {
                    "id_vars": ["response_id", "account_id", "plan"],
                    "value_vars": ["q1", "q2", "q3"],
                    "var_name": "question",
                    "value_name": "score",
                },
                1920,
                0,
            ),
            _node(
                "question_scores",
                "groupByAggregate",
                {"group_by": ["plan", "question"], "aggregations": {"score": "mean"}},
                2160,
                0,
            ),
            _output("out_survey", "survey_question_scores", 2400, 0),
        ],
        "edges": [
            _edge("in_survey", "required_ids"),
            _edge("required_ids", "unique_response"),
            _edge("unique_response", "score_range"),
            _edge("score_range", "plan_domain"),
            _edge("plan_domain", "valid_average"),
            _edge("valid_average", "row_bounds"),
            _edge("row_bounds", "satisfaction_band"),
            _edge("satisfaction_band", "wide_to_long"),
            _edge("wide_to_long", "question_scores"),
            _edge("question_scores", "out_survey"),
        ],
    }
    return (
        "Survey Quality Contracts",
        "Validate survey data with not-null, uniqueness, range, domain, expression, and row-count checks, "
        "then reshape question scores into a tidy summary.",
        graph,
    )


# ---------------------------------------------------------------------------
# 8. Regional Target Variance — multi-input concat, unpivot, pivot, variance.
# ---------------------------------------------------------------------------


def _regional_target_variance(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_targets", ds["regional_targets.csv"], 0, 0),
            _node(
                "targets_long",
                "unpivot",
                {
                    "id_vars": ["region", "metric"],
                    "value_vars": ["q1", "q2", "q3", "q4"],
                    "var_name": "quarter",
                    "value_name": "amount",
                },
                240,
                0,
            ),
            _input("in_actuals", ds["regional_actuals.csv"], 0, 260),
            _node(
                "actuals_long",
                "unpivot",
                {
                    "id_vars": ["region", "metric"],
                    "value_vars": ["q1", "q2", "q3", "q4"],
                    "var_name": "quarter",
                    "value_name": "amount",
                },
                240,
                260,
            ),
            _node("stack_metrics", "concatRows", {}, 520, 130),
            _node(
                "metrics_wide",
                "pivot",
                {"index": ["region", "quarter"], "columns": "metric", "values": "amount", "aggfunc": "sum"},
                760,
                130,
            ),
            _node(
                "variance",
                "calculatedColumn",
                {"column_name": "variance", "expression": "actual - target"},
                1000,
                130,
            ),
            _node(
                "attainment",
                "calculatedColumn",
                {"column_name": "attainment", "expression": "actual / target"},
                1240,
                130,
            ),
            _node("round_attainment", "roundNumbers", {"columns": ["attainment"], "decimals": 3}, 1480, 130),
            _output("out_variance", "regional_target_variance", 1720, 130),
        ],
        "edges": [
            _edge("in_targets", "targets_long"),
            _edge("in_actuals", "actuals_long"),
            _edge("targets_long", "stack_metrics"),
            _edge("actuals_long", "stack_metrics"),
            _edge("stack_metrics", "metrics_wide"),
            _edge("metrics_wide", "variance"),
            _edge("variance", "attainment"),
            _edge("attainment", "round_attainment"),
            _edge("round_attainment", "out_variance"),
        ],
    }
    return (
        "Regional Target Variance",
        "Convert quarterly targets and actuals from wide to long, stack both sources, pivot them back side by side, "
        "then calculate variance and attainment.",
        graph,
    )


# ---------------------------------------------------------------------------
# 9. Product Catalog Scoring — expression filter, binning, and Python escape hatch.
# ---------------------------------------------------------------------------


def _product_catalog_scoring(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_products", ds["products.csv"], 0, 0),
            _node("fill_price", "fillNulls", {"columns": ["price"], "strategy": "mean"}, 240, 0),
            _node("good_catalog", "filterExpression", {"expression": "price >= 10 and rating >= 2"}, 480, 0),
            _node(
                "price_band",
                "binColumn",
                {"column": "price", "new_column": "price_band", "method": "quantile", "bins": 3},
                720,
                0,
            ),
            _node("round_catalog", "roundNumbers", {"columns": ["price", "rating"], "decimals": 1}, 960, 0),
            _node(
                "python_margin",
                "pythonTransform",
                {
                    "script": (
                        "if hasattr(df, 'with_columns'):\n"
                        "    return df.with_columns((pl.col('price') * 0.35).alias('margin_estimate'))\n"
                        "df = df.copy()\n"
                        "df['margin_estimate'] = df['price'] * 0.35\n"
                        "return df"
                    )
                },
                1200,
                0,
            ),
            _output("out_catalog", "product_catalog_scored", 1440, 0),
        ],
        "edges": [
            _edge("in_products", "fill_price"),
            _edge("fill_price", "good_catalog"),
            _edge("good_catalog", "price_band"),
            _edge("price_band", "round_catalog"),
            _edge("round_catalog", "python_margin"),
            _edge("python_margin", "out_catalog"),
        ],
    }
    return (
        "Product Catalog Scoring",
        "Prepare a product catalog with an expression filter, quantile price bands, rounded numeric fields, "
        "and a small Python Transform for a margin estimate.",
        graph,
    )


# ---------------------------------------------------------------------------
# Machine-learning demo flows (only seeded when core ML dependencies are available)
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


# 9. Iris — Cross-Validation Report: dedicated CV node with logistic regression.
def _iris_cross_validation_report(ds: dict[str, str]) -> DemoFlow:
    model_columns = [*_IRIS_FEATURES, "species"]
    graph = {
        "nodes": [
            _input("in_iris", ds["iris.csv"], 0, 0),
            _node("model_columns", "selectColumns", {"columns": model_columns}, 240, 0),
            _node(
                "model",
                "mlClassifierModel",
                {
                    "model_type": "logistic_regression",
                    "target_column": "species",
                    "feature_columns": _IRIS_FEATURES,
                    "hyperparameters": {"max_iter": 1000},
                    "preprocessing": {
                        "numeric_columns": _IRIS_FEATURES,
                        "categorical_columns": [],
                        "numeric_strategy": "standard_scaler",
                    },
                    "seed": 11,
                },
                500,
                -80,
            ),
            _node(
                "cross_validate",
                "mlCrossValidate",
                {
                    "cv_strategy": "stratified_kfold",
                    "n_splits": 5,
                    "shuffle": True,
                    "scoring": ["accuracy", "f1_weighted"],
                    "seed": 11,
                },
                500,
                120,
            ),
            _output("out_cv", "iris_logistic_cv_scores", 760, 120),
        ],
        "edges": [
            _edge("in_iris", "model_columns"),
            _edge("model_columns", "model"),
            _edge("model_columns", "cross_validate"),
            _edge("model", "cross_validate", source_handle="model", target_handle="model"),
            _edge("cross_validate", "out_cv"),
        ],
        "engine": "pandas",
    }
    return (
        "Iris — Logistic CV Report",
        "Select the modeling columns, configure a logistic-regression classifier, then cross-validate that model "
        "model with fold-safe preprocessing and export fold-level scores.",
        graph,
    )


# 10. Iris — KNN with Encoded Species: category encoding + KNN classifier.
def _iris_knn_with_encoded_species(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_iris", ds["iris.csv"], 0, 0),
            _node("encode_species", "encodeCategories", {"columns": ["species"], "method": "ordinal"}, 240, 0),
            _node(
                "split",
                "trainTestSplit",
                {"test_size": 0.25, "stratify_column": "species", "seed": 13},
                480,
                0,
            ),
            _node(
                "train",
                "mlTrainClassifier",
                {
                    "model_type": "knn_classifier",
                    "target_column": "species",
                    "feature_columns": _IRIS_FEATURES,
                    "hyperparameters": {"n_neighbors": 5},
                    "seed": 13,
                },
                720,
                -80,
            ),
            _node("predict", "mlPredict", {"output_column": "prediction"}, 960, 0),
            _node(
                "evaluate",
                "mlEvaluate",
                {"task_type": "classification", "target_column": "species", "prediction_column": "prediction"},
                1200,
                0,
            ),
            _output("out_eval", "iris_knn_encoded_metrics", 1440, 0),
        ],
        "edges": [
            _edge("in_iris", "encode_species"),
            _edge("encode_species", "split"),
            _edge("split", "train", target_handle="in", source_handle="train"),
            _edge("split", "predict", target_handle="in", source_handle="test"),
            _edge("train", "predict", target_handle="model"),
            _edge("predict", "evaluate"),
            _edge("evaluate", "out_eval"),
        ],
        "engine": "pandas",
    }
    return (
        "Iris — KNN with Encoded Species",
        "Encode the target labels, split the dataset, train a KNN classifier, and evaluate predictions.",
        graph,
    )


# 11. House Prices — Feature Selection: choose numeric predictors before ridge.
def _house_price_feature_selection(ds: dict[str, str]) -> DemoFlow:
    graph = {
        "nodes": [
            _input("in_houses", ds["house_prices.csv"], 0, 0),
            _node("select_features", "selectFeatures", {"method": "kbest", "target_column": "price", "k": 3}, 240, 0),
            _node("split", "trainTestSplit", {"test_size": 0.25, "seed": 17}, 480, 0),
            _node(
                "train",
                "mlTrainRegressor",
                {
                    "model_type": "ridge",
                    "target_column": "price",
                    "hyperparameters": {"alpha": 1.0},
                    "seed": 17,
                },
                720,
                -80,
            ),
            _node("predict", "mlPredict", {"output_column": "prediction"}, 960, 0),
            _node(
                "evaluate",
                "mlEvaluate",
                {"task_type": "regression", "target_column": "price", "prediction_column": "prediction"},
                1200,
                0,
            ),
            _output("out_metrics", "house_price_ridge_metrics", 1440, 0),
        ],
        "edges": [
            _edge("in_houses", "select_features"),
            _edge("select_features", "split"),
            _edge("split", "train", target_handle="in", source_handle="train"),
            _edge("split", "predict", target_handle="in", source_handle="test"),
            _edge("train", "predict", target_handle="model"),
            _edge("predict", "evaluate"),
            _edge("evaluate", "out_metrics"),
        ],
        "engine": "pandas",
    }
    return (
        "House Prices — Feature Selection",
        "Use SelectKBest to keep the strongest numeric predictors, then train and evaluate a ridge regressor.",
        graph,
    )


# 12. House Prices — Customer Segments: unsupervised clustering, no PCA.
def _house_price_customer_segments(ds: dict[str, str]) -> DemoFlow:
    features = ["area", "bedrooms", "age", "distance_to_city", "price"]
    graph = {
        "nodes": [
            _input("in_houses", ds["house_prices.csv"], 0, 0),
            _node("scale", "scaleFeatures", {"columns": features, "method": "minmax"}, 240, 0),
            _node(
                "cluster",
                "mlTrainClustering",
                {
                    "model_type": "kmeans",
                    "feature_columns": features,
                    "hyperparameters": {"n_clusters": 4},
                    "seed": 19,
                },
                480,
                0,
            ),
        ],
        "edges": [_edge("in_houses", "scale"), _edge("scale", "cluster")],
        "engine": "pandas",
    }
    return (
        "House Prices — Customer Segments",
        "Scale house features and train a K-Means clustering model to discover price/size segments.",
        graph,
    )


# 13. House Prices — PCA Model: fit PCA as a model, separate from the Iris PCA transform.
def _house_price_pca_model(ds: dict[str, str]) -> DemoFlow:
    features = ["area", "bedrooms", "age", "distance_to_city", "price"]
    graph = {
        "nodes": [
            _input("in_houses", ds["house_prices.csv"], 0, 0),
            _node("scale", "scaleFeatures", {"columns": features, "method": "standard"}, 240, 0),
            _node(
                "train_pca",
                "mlTrainDimReduction",
                {
                    "model_type": "pca_fit",
                    "feature_columns": features,
                    "hyperparameters": {"n_components": 2},
                    "seed": 23,
                },
                480,
                0,
            ),
        ],
        "edges": [_edge("in_houses", "scale"), _edge("scale", "train_pca")],
        "engine": "pandas",
    }
    return (
        "House Prices — PCA Model",
        "Fit a PCA dimensionality-reduction model on scaled house features and log explained variance to MLflow.",
        graph,
    )
