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


def build_demo_frames(include_ml: bool = False) -> dict[str, pd.DataFrame]:
    """Return the demo datasets keyed by their CSV file name.

    The four ETL datasets are always included. When ``include_ml`` is set, two
    clean, model-ready datasets are added for the machine-learning demo flows:
    a 3-class classification set (``iris.csv``) and a regression set
    (``house_prices.csv``)."""
    rng = np.random.default_rng(_SEED)
    frames = {
        "customers.csv": _build_customers(rng),
        "orders.csv": _build_orders(rng),
        "products.csv": _build_products(rng),
        "order_items.csv": _build_order_items(rng),
    }
    if include_ml:
        frames["iris.csv"] = _build_iris(rng)
        frames["house_prices.csv"] = _build_house_prices(rng)
    return frames


# ---------------------------------------------------------------------------
# Individual dataset builders
# ---------------------------------------------------------------------------

_N_CUSTOMERS = 60
_N_PRODUCTS = 12
_N_ORDERS = 120

# Countries written with inconsistent casing on purpose (a cleaning target).
_COUNTRIES = ["usa", "USA", "Usa", "canada", "CANADA", "Canada", "uk", "UK", "mexico"]
_FIRST_NAMES = [
    "Ana",
    "Liam",
    "Noah",
    "Mia",
    "Ethan",
    "Olivia",
    "Lucas",
    "Emma",
    "Mateo",
    "Sofia",
    "Leo",
    "Aria",
    "Hugo",
    "Ivy",
    "Owen",
    "Zoe",
]
_LAST_NAMES = [
    "Smith",
    "Garcia",
    "Brown",
    "Lee",
    "Patel",
    "Khan",
    "Nguyen",
    "Lopez",
    "Davis",
    "Martin",
    "Clark",
    "Reed",
]
_STATUSES = ["completed", "completed", "completed", "pending", "cancelled", "refunded"]
_CATEGORIES = ["Electronics", "Home", "Toys", "Books", "Sports"]


def _build_customers(rng: np.random.Generator) -> pd.DataFrame:
    ids = list(range(1, _N_CUSTOMERS + 1))
    names = [
        f"{_FIRST_NAMES[rng.integers(len(_FIRST_NAMES))]} {_LAST_NAMES[rng.integers(len(_LAST_NAMES))]}" for _ in ids
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
    prices: list[float | None] = np.round(rng.uniform(5, 250, size=_N_PRODUCTS), 2).tolist()
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


# ---------------------------------------------------------------------------
# Machine-learning datasets (clean and model-ready, unlike the ETL data above)
# ---------------------------------------------------------------------------

_IRIS_SPECIES = ["setosa", "versicolor", "virginica"]
# Per-class (mean, std) for each of the four measurements — chosen so the classes
# are well but not perfectly separable, so trained models score high yet non-trivially.
_IRIS_PARAMS = {
    "setosa": [(5.0, 0.35), (3.4, 0.38), (1.5, 0.17), (0.25, 0.11)],
    "versicolor": [(5.9, 0.51), (2.8, 0.31), (4.3, 0.47), (1.3, 0.20)],
    "virginica": [(6.6, 0.63), (3.0, 0.32), (5.6, 0.55), (2.0, 0.27)],
}


def _build_iris(rng: np.random.Generator) -> pd.DataFrame:
    """A clean, deterministic 3-class flower dataset for classification demos."""
    rows: list[dict[str, float | str]] = []
    for species in _IRIS_SPECIES:
        params = _IRIS_PARAMS[species]
        for _ in range(50):
            rows.append(
                {
                    "sepal_length": round(float(rng.normal(*params[0])), 2),
                    "sepal_width": round(float(rng.normal(*params[1])), 2),
                    "petal_length": round(float(rng.normal(*params[2])), 2),
                    "petal_width": round(float(rng.normal(*params[3])), 2),
                    "species": species,
                }
            )
    df = pd.DataFrame(rows)
    # Shuffle so the classes aren't blocked together (deterministic permutation).
    return df.sample(frac=1.0, random_state=_SEED).reset_index(drop=True)


def _build_house_prices(rng: np.random.Generator) -> pd.DataFrame:
    """A clean regression dataset: price is a noisy linear function of features."""
    n = 200
    area = rng.uniform(50, 250, size=n)           # m²
    bedrooms = rng.integers(1, 6, size=n)
    age = rng.uniform(0, 40, size=n)              # years
    distance_to_city = rng.uniform(1, 30, size=n)  # km
    noise = rng.normal(0, 15_000, size=n)
    price = (
        30_000
        + area * 3_000
        + bedrooms * 12_000
        - age * 1_500
        - distance_to_city * 2_000
        + noise
    )
    return pd.DataFrame(
        {
            "area": np.round(area, 1),
            "bedrooms": bedrooms,
            "age": np.round(age, 1),
            "distance_to_city": np.round(distance_to_city, 1),
            "price": np.round(price, 0),
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
