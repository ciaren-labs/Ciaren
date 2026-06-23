"""Deterministic sample data for the demo project.

Four small CSV datasets are generated from a fixed-seed RNG so every install
gets byte-identical content. The data is intentionally *messy* — nulls,
outliers, duplicate rows, inconsistent casing, and dates stored as text — so the
example flows have something realistic to clean.

No timestamps or other run-time values are baked into the data; the only source
of randomness is the seeded generator below.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# A single fixed seed drives every dataset so the output is fully reproducible.
_SEED = 42


def build_demo_frames() -> dict[str, pd.DataFrame]:
    """Return the four demo datasets keyed by their CSV file name."""
    rng = np.random.default_rng(_SEED)
    return {
        "customers.csv": _build_customers(rng),
        "orders.csv": _build_orders(rng),
        "products.csv": _build_products(rng),
        "order_items.csv": _build_order_items(rng),
    }


# ---------------------------------------------------------------------------
# Individual dataset builders
# ---------------------------------------------------------------------------

_N_CUSTOMERS = 60
_N_PRODUCTS = 12
_N_ORDERS = 120

# Countries written with inconsistent casing on purpose (a cleaning target).
_COUNTRIES = ["usa", "USA", "Usa", "canada", "CANADA", "Canada", "uk", "UK", "mexico"]
_FIRST_NAMES = [
    "Ana", "Liam", "Noah", "Mia", "Ethan", "Olivia", "Lucas", "Emma",
    "Mateo", "Sofia", "Leo", "Aria", "Hugo", "Ivy", "Owen", "Zoe",
]
_LAST_NAMES = [
    "Smith", "Garcia", "Brown", "Lee", "Patel", "Khan", "Nguyen", "Lopez",
    "Davis", "Martin", "Clark", "Reed",
]
_STATUSES = ["completed", "completed", "completed", "pending", "cancelled", "refunded"]
_CATEGORIES = ["Electronics", "Home", "Toys", "Books", "Sports"]


def _build_customers(rng: np.random.Generator) -> pd.DataFrame:
    ids = list(range(1, _N_CUSTOMERS + 1))
    names = [
        f"{_FIRST_NAMES[rng.integers(len(_FIRST_NAMES))]} "
        f"{_LAST_NAMES[rng.integers(len(_LAST_NAMES))]}"
        for _ in ids
    ]
    emails = [f"{name.lower().replace(' ', '.')}@example.com" for name in names]

    # signup_date stored as TEXT (YYYY-MM-DD) so a parseDates node is needed.
    start = np.datetime64("2022-01-01")
    offsets = rng.integers(0, 720, size=_N_CUSTOMERS)
    signup_dates = [str((start + np.timedelta64(int(o), "D"))) for o in offsets]

    countries = [_COUNTRIES[rng.integers(len(_COUNTRIES))] for _ in ids]

    # age: mostly realistic, with a few nulls and a couple of absurd outliers.
    ages: list[float | None] = [float(int(rng.normal(38, 11))) for _ in ids]
    for idx in rng.choice(_N_CUSTOMERS, size=6, replace=False):
        ages[int(idx)] = None
    ages[3] = 199.0  # outlier
    ages[17] = 0.0  # outlier

    return pd.DataFrame(
        {
            "id": ids,
            "name": names,
            "email": emails,
            "signup_date": signup_dates,
            "country": countries,
            "age": ages,
        }
    )


def _build_orders(rng: np.random.Generator) -> pd.DataFrame:
    order_ids = list(range(1001, 1001 + _N_ORDERS))
    customer_ids = [int(rng.integers(1, _N_CUSTOMERS + 1)) for _ in order_ids]

    # order_date stored as TEXT so it must be parsed before date-part extraction.
    start = np.datetime64("2023-01-01")
    offsets = rng.integers(0, 365, size=_N_ORDERS)
    order_dates = [str((start + np.timedelta64(int(o), "D"))) for o in offsets]

    # amount: log-normal-ish with a few large outliers.
    amounts = np.round(rng.gamma(2.0, 40.0, size=_N_ORDERS) + 5, 2).tolist()
    amounts[10] = 99999.99  # outlier
    amounts[55] = 88888.88  # outlier

    statuses = [_STATUSES[rng.integers(len(_STATUSES))] for _ in order_ids]

    df = pd.DataFrame(
        {
            "order_id": order_ids,
            "customer_id": customer_ids,
            "order_date": order_dates,
            "amount": amounts,
            "status": statuses,
        }
    )
    # Introduce a few exact duplicate rows (a removeDuplicates target).
    duplicates = df.iloc[[2, 7, 20]].copy()
    return pd.concat([df, duplicates], ignore_index=True)


def _build_products(rng: np.random.Generator) -> pd.DataFrame:
    product_ids = list(range(1, _N_PRODUCTS + 1))
    categories = [_CATEGORIES[rng.integers(len(_CATEGORIES))] for _ in product_ids]

    # price: a couple of nulls to exercise fill/drop-nulls.
    prices: list[float | None] = np.round(
        rng.uniform(5, 250, size=_N_PRODUCTS), 2
    ).tolist()
    prices[4] = None
    prices[9] = None

    ratings = np.round(rng.uniform(1, 5, size=_N_PRODUCTS), 1).tolist()

    return pd.DataFrame(
        {
            "product_id": product_ids,
            "category": categories,
            "price": prices,
            "rating": ratings,
        }
    )


def _build_order_items(rng: np.random.Generator) -> pd.DataFrame:
    """Line items linking orders to products (one or two lines per order)."""
    rows: list[dict[str, float | int]] = []
    for order_id in range(1001, 1001 + _N_ORDERS):
        n_lines = int(rng.integers(1, 3))
        for _ in range(n_lines):
            product_id = int(rng.integers(1, _N_PRODUCTS + 1))
            rows.append(
                {
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": int(rng.integers(1, 6)),
                    "unit_price": float(np.round(rng.uniform(5, 250), 2)),
                }
            )
    return pd.DataFrame(rows)
