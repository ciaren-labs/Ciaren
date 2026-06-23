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
        "type": "csvOutput",
        "position": {"x": x, "y": y},
        "data": {"config": {"dataset_name": dataset_name}},
    }


def _edge(source: str, target: str, target_handle: str | None = None) -> dict[str, Any]:
    edge: dict[str, Any] = {
        "id": f"e-{source}-{target}" + (f"-{target_handle}" if target_handle else ""),
        "source": source,
        "target": target,
    }
    if target_handle is not None:
        edge["targetHandle"] = target_handle
    return edge


def build_demo_flows(dataset_ids: dict[str, str]) -> list[DemoFlow]:
    """Return every demo flow wired to the given dataset ids (by CSV file name)."""
    return [
        _clean_customers(dataset_ids),
        _order_revenue_by_month(dataset_ids),
        _customer_orders_join(dataset_ids),
        _full_sales_mart(dataset_ids),
    ]


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
