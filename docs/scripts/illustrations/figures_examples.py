"""Figures for docs/examples/."""

from __future__ import annotations

from build import figure
from sketch import (
    GREEN,
    GREEN_SOFT,
    INK,
    INK_SOFT,
    MARKER,
    MARKER_SOFT,
    RED,
    RED_SOFT,
    VIOLET,
    VIOLET_SOFT,
    Figure,
)

W = 980


def _dot(fig: Figure, cx: float, cy: float, *, fill: str = INK, r: float = 7) -> None:
    fig.ellipse(cx, cy, r, r, stroke=INK, fill=fill, width=1.4)


# -- sales-analysis -------------------------------------------------------------


@figure("examples/sales-group-by")
def sales_group_by() -> Figure:
    fig = Figure(
        "examples/sales-group-by",
        W,
        400,
        "Group By Aggregate on region turns the four cleaned orders into three rows. The two "
        "North orders, 120.50 and 210.00, become one North row with a sum of 330.50 and a count of 2.",
    )
    fig.heading(44, 56, "one row in, per region out")
    cols = ["order_id", "region", "amount"]
    rows = [[1001, "North", "120.50"], [1002, "South", "89.00"], [1005, "Unknown", "42.25"], [1006, "North", "210.00"]]
    tw, th, _ = fig.table_size(cols, rows)
    left, top = 44, 130
    fig.note(left, top - 14, "after cleaning: 4 orders", size=22)
    fig.table(left, top, cols, rows, row_styles={0: {"fill": MARKER_SOFT}, 3: {"fill": MARKER_SOFT}})

    out_cols = ["region", "amount (sum)", "order_id (count)"]
    out_rows = [["North", "330.50", 2], ["South", "89.00", 1], ["Unknown", "42.25", 1]]
    ow, oh, _ = fig.table_size(out_cols, out_rows)
    right = W - 44 - ow
    fig.note(right, top + 1, "3 rows, one per region", size=22)
    fig.table(right, top + 15, out_cols, out_rows, cell_styles={(0, 1): {"fill": MARKER}, (0, 2): {"fill": MARKER}})
    fig.step(left + tw + 24, right - 24, top + th / 2 + 8, "group by: region")
    fig.note(left, top + th + 44, "120.50 + 210.00 = 330.50, and 2 orders", size=23, fill=INK)
    fig.note(
        right,
        top + 15 + oh + 34,
        ["ordered_at is gone: it is neither", "grouped nor aggregated"],
        size=21,
    )
    return fig


@figure("examples/sales-case-split")
def sales_case_split() -> Figure:
    fig = Figure(
        "examples/sales-case-split",
        W,
        420,
        "Without the Replace Values nodes, North and north are different group keys, so the summary "
        "has four rows and North's revenue is split into 210.00 and 120.50. With them, North is one row of 330.50.",
    )
    fig.heading(44, 56, "group keys must match exactly")
    cols = ["region", "total_sales", "num_orders"]
    without = [["north", "210.00", 1], ["North", "120.50", 1], ["south", "89.00", 1], ["Unknown", "42.25", 1]]
    with_ = [["North", "330.50", 2], ["South", "89.00", 1], ["Unknown", "42.25", 1]]
    tw, _, _ = fig.table_size(cols, without)
    left, right, top = 70, W - 70 - tw, 140
    fig.note(left, top - 16, "without Replace Values", size=24, fill=RED)
    fig.table(left, top, cols, without, row_styles={0: {"fill": RED_SOFT}, 1: {"fill": RED_SOFT}})
    fig.note(left, top + 30 * 5 + 40, ["4 rows: North's revenue", "is split across two keys"], size=22, fill=RED)
    fig.note(right, top - 16, "with Replace Values", size=24, fill=GREEN)
    fig.table(right, top, cols, with_, row_styles={0: {"fill": GREEN_SOFT}})
    fig.note(right, top + 30 * 4 + 40, ["3 rows: north → North", "before grouping"], size=22, fill=GREEN)
    fig.check(right + tw + 10, top + 38, color=GREEN)
    fig.cross(left - 30, top + 38, color=RED)
    return fig


# -- customer-segmentation -------------------------------------------------------


@figure("examples/segmentation-equal-width")
def segmentation_equal_width() -> Figure:
    fig = Figure(
        "examples/segmentation-equal-width",
        W,
        470,
        "Equal-width binning splits the range of total_spent, 15 to 500, into three bins 161.67 wide. "
        "The edges at 176.67 and 338.33 put Linus and Ada in Bronze, Margaret in Silver and Grace in Gold.",
    )
    fig.heading(44, 56, "equal width splits the range, not the customers")
    x0, x1, axis_y = 110, 870, 220
    lo, hi = 15.0, 500.0

    def at(v: float) -> float:
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    edges = [lo, lo + (hi - lo) / 3, lo + 2 * (hi - lo) / 3, hi]
    for (a, b), label in zip(zip(edges, edges[1:]), ["Bronze", "Silver", "Gold"]):
        fig.box(
            at(a) + 3,
            axis_y + 46,
            at(b) - at(a) - 6,
            40,
            r=10,
            stroke=VIOLET,
            fill=VIOLET_SOFT,
            width=1.2,
            double=False,
        )
        fig.text((at(a) + at(b)) / 2, axis_y + 72, label, size=16, weight=650, anchor="middle", fill=VIOLET)
    fig.line(x0 - 20, axis_y, x1 + 20, axis_y, width=1.8)
    for v, label in zip(edges, ["15", "176.67", "338.33", "500"]):
        fig.line(at(v), axis_y - 8, at(v), axis_y + 8, width=1.6, double=False)
        fig.text(at(v), axis_y + 28, label, role="mono", size=13, anchor="middle", fill=INK_SOFT)
    for v, name in [(15, "Linus"), (100, "Ada"), (250, "Margaret"), (500, "Grace")]:
        _dot(fig, at(v), axis_y - 24, fill=MARKER)
        fig.text(at(v), axis_y - 44, f"{name} {v:g}", size=13.5, weight=600, anchor="middle")
    fig.note(560, 360, ["Margaret has the 2nd-highest total, but", "Grace's 500 pushes Gold up to 338.33"], size=21)
    fig.arrow([(552, 352), (520, 336), (at(250) + 8, axis_y + 92)], stroke=INK_SOFT)
    fig.note(110, 430, "each bin is (500 − 15) / 3 = 161.67 wide", size=23, fill=INK)
    return fig


# -- data-quality -----------------------------------------------------------------


@figure("examples/quality-step-order")
def quality_step_order() -> Figure:
    fig = Figure(
        "examples/quality-step-order",
        W,
        500,
        "With keep first, Remove Duplicates keeps the first Grace row, whose age is null. If it runs "
        "before Drop Nulls, Drop Nulls then deletes that row and no Grace is left. Dropping nulls first "
        "removes the bad copy and keeps Grace with age 85.",
    )
    fig.heading(44, 56, "drop nulls before you remove duplicates")
    cols = ["email", "age"]
    rows = [["grace@example.com", None], ["grace@example.com", 85]]
    tw, th, _ = fig.table_size(cols, rows)
    left = 44
    right = W - 44 - tw

    # lane 1: dedupe first
    y = 140
    fig.note(left, y - 14, "Remove Duplicates, then Drop Nulls", size=22, fill=RED)
    fig.table(
        left, y, cols, rows, row_styles={1: {"strike": True, "fill": RED_SOFT}}, cell_styles={(0, 1): {"fill": MARKER}}
    )
    fig.step(left + tw + 24, right - 24, y + th / 2 + 8, "keep: first, then drop nulls")
    fig.box(right, y + 8, tw, 60, r=10, stroke=RED, dash="6 6", double=False)
    fig.text(right + tw / 2, y + 44, "no Grace row left", size=16, weight=650, anchor="middle", fill=RED)
    fig.note(left, y + th + 30, "the null-age copy wins the duplicate check, then gets dropped", size=21, fill=RED)

    # lane 2: drop nulls first
    y = 330
    fig.note(left, y - 14, "Drop Nulls, then Remove Duplicates", size=22, fill=GREEN)
    fig.table(left, y, cols, rows, row_styles={0: {"strike": True, "fill": RED_SOFT}})
    fig.step(left + tw + 24, right - 24, y + th / 2 + 8, "drop nulls, then keep: first")
    fig.table(right, y + 15, cols, rows[1:], row_styles={0: {"fill": GREEN_SOFT}})
    fig.check(right + tw - 30, y + 15 + 30 * 2 + 12, color=GREEN)
    fig.note(left, y + th + 30, "only the age-85 copy reaches the duplicate check", size=21, fill=GREEN)
    return fig


# -- duckdb-analytics -------------------------------------------------------------


@figure("examples/duckdb-pushdown")
def duckdb_pushdown() -> Figure:
    fig = Figure(
        "examples/duckdb-pushdown",
        W,
        520,
        "The WHERE amount > 0 clause runs inside DuckDB, so only 4 of the 6 order rows reach the Ciaren "
        "canvas. Ciaren title-cases and fills the region, groups the rows into 3, and SQL Output writes "
        "them back to the revenue_by_region table in the same DuckDB file.",
    )
    fig.heading(44, 56, "the query filters before rows leave DuckDB")
    cols = ["order_id", "region", "amount"]
    rows = [
        [1001, "North", "120.50"],
        [1002, "south", "89.00"],
        [1003, "North", None],
        [1004, "South", "-5.00"],
        [1005, None, "42.25"],
        [1006, "north", "210.00"],
    ]
    tw, th, _ = fig.table_size(cols, rows, row_h=28, size=13)
    left, top = 60, 150
    fig.box(36, 100, tw + 48, 380, r=14, stroke=INK_SOFT, dash="7 6", double=False)
    fig.text(60, 128, "analytics.duckdb · orders", size=15, weight=650, fill=INK_SOFT)
    fig.table(
        left,
        top,
        cols,
        rows,
        row_h=28,
        size=13,
        row_styles={2: {"strike": True, "fill": RED_SOFT}, 3: {"strike": True, "fill": RED_SOFT}},
    )
    fig.pill(left, top + th + 18, "WHERE amount > 0", role="mono", size=13)
    fig.note(left, top + th + 80, "4 of 6 rows leave DuckDB", size=22, fill=INK)

    # Ciaren canvas
    cx = 420
    fig.box(cx - 24, 100, 270, 380, r=14, stroke=VIOLET, dash="7 6", double=False)
    fig.text(cx, 128, "Ciaren canvas", size=15, weight=650, fill=VIOLET)
    y = 160
    for label, detail, kind in [
        ("String Transform", "region: title case", "clean"),
        ("Fill Nulls", "region → Unknown", "clean"),
        ("Group By Aggregate", "region · sum(amount)", "transform"),
    ]:
        fig.node(cx, y, label, detail, kind=kind, w=222)
        if y < 330:
            fig.arrow([(cx + 111, y + 66), (cx + 111, y + 96)], stroke=INK_SOFT)
        y += 100
    fig.arrow([(left + tw + 10, top + th / 2), (cx - 34, 190)], stroke=INK_SOFT)

    # Result written back
    out_cols = ["region", "amount"]
    out_rows = [["North", "330.50"], ["South", "89.00"], ["Unknown", "42.25"]]
    ow, oh, _ = fig.table_size(out_cols, out_rows)
    rx = W - 50 - ow
    fig.box(rx - 24, 100, ow + 48, 380, r=14, stroke=INK_SOFT, dash="7 6", double=False)
    fig.text(rx, 128, "revenue_by_region", size=15, weight=650, fill=INK_SOFT)
    fig.table(
        rx,
        230,
        out_cols,
        out_rows,
        row_styles={0: {"fill": GREEN_SOFT}, 1: {"fill": GREEN_SOFT}, 2: {"fill": GREEN_SOFT}},
    )
    fig.arrow([(cx + 232, 390), (rx - 34, 300)], stroke=INK_SOFT)
    fig.note(rx, 230 + oh + 40, ["SQL Output,", "if exists: replace"], size=21)
    return fig


# -- feature-engineering ----------------------------------------------------------


@figure("examples/features-one-hot")
def features_one_hot() -> Figure:
    fig = Figure(
        "examples/features-one-hot",
        W,
        420,
        "Encode Categories with one-hot replaces the region column with region_East, region_North and "
        "region_South. Each row has True in exactly one of them, the column of its own region.",
    )
    fig.heading(44, 56, "one column per category, one True per row")
    regions = ["North", "South", "North", "East", "South", "East"]
    cols = ["applicant_id", "region"]
    rows = [[i + 1, r] for i, r in enumerate(regions)]
    tw, th, _ = fig.table_size(cols, rows, row_h=32)
    left, top = 60, 120
    fig.table(left, top, cols, rows, row_h=32)
    out_cols = ["applicant_id", "region_East", "region_North", "region_South"]
    names = ["East", "North", "South"]
    out_rows = [[i + 1, *[str(r == n) for n in names]] for i, r in enumerate(regions)]
    cells = {(i, 1 + names.index(r)): {"fill": MARKER} for i, r in enumerate(regions)}
    ow, _, _ = fig.table_size(out_cols, out_rows, row_h=32)
    right = W - 44 - ow
    fig.table(right, top, out_cols, out_rows, row_h=32, cell_styles=cells)
    fig.step(left + tw + 24, right - 24, top + th / 2 + 8, "one-hot: region")
    fig.note(left, top + th + 40, "applicant 4 is East, so only region_East is True", size=22)
    return fig


@figure("examples/features-scaling")
def features_scaling() -> Figure:
    fig = Figure(
        "examples/features-scaling",
        W,
        470,
        "Before scaling, age runs from 25 to 52 and income from 42000 to 120000. Standard scaling "
        "subtracts each column's mean and divides by its standard deviation, so both land on the same "
        "axis around 0: age from -1.33 to 1.51 and income from -1.46 to 1.43.",
    )
    fig.heading(44, 56, "standard scaling puts every column on one axis")
    ages = [25, 41, 33, 52, 29, 46]
    incomes = [42000, 88000, 88000, 120000, 51000, 99000]
    z_age = [-1.33, 0.35, -0.49, 1.51, -0.91, 0.88]
    z_inc = [-1.46, 0.25, 0.25, 1.43, -1.12, 0.66]
    x0, x1 = 230, 900

    def axis(y: float, label: str, lo: float, hi: float, ticks: list[tuple[float, str]]):
        fig.text(44, y + 5, label, size=15, weight=650)
        fig.line(x0, y, x1, y, width=1.6)
        for v, t in ticks:
            px = x0 + (v - lo) / (hi - lo) * (x1 - x0)
            fig.line(px, y - 6, px, y + 6, width=1.4, double=False)
            fig.text(px, y + 26, t, role="mono", size=12.5, anchor="middle", fill=INK_SOFT)
        return lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)

    pa = axis(130, "age (years)", 20, 55, [(20, "20"), (30, "30"), (40, "40"), (50, "50")])
    for v in ages:
        _dot(fig, pa(v), 130, fill=MARKER)
    pi = axis(
        220,
        "income",
        40000,
        125000,
        [(40000, "40k"), (60000, "60k"), (80000, "80k"), (100000, "100k"), (120000, "120k")],
    )
    for v in incomes:
        fig.ellipse(pi(v), 220, 7, 7, stroke=INK, width=1.6)
    fig.pill(44, 280, "Scale Features: standard", role="mono", size=12.5)
    fig.arrow([(565, 262), (565, 318)], stroke=INK_SOFT)
    pz = axis(360, "z-score", -2, 2, [(-2, "-2"), (-1, "-1"), (0, "0"), (1, "1"), (2, "2")])
    for v in z_age:
        _dot(fig, pz(v), 346, fill=MARKER)
    for v in z_inc:
        fig.ellipse(pz(v), 374, 7, 7, stroke=INK, width=1.6)
    fig.note(44, 430, "z = (value − column mean) / column std   ·   filled: age   ·   hollow: income", size=21)
    return fig


# -- ml-classification ------------------------------------------------------------


def _id_cell(fig: Figure, x: float, y: float, cid: int, churn: int, *, size: float = 44) -> None:
    fill = MARKER_SOFT if churn else None
    fig.box(x, y, size, size, r=7, stroke=INK, fill=fill, width=1.3, double=False, fill_offset=1.5)
    fig.text(x + size / 2, y + size / 2 + 5, str(cid), role="mono", size=14, anchor="middle")


@figure("examples/ml-train-test-split")
def ml_train_test_split() -> Figure:
    fig = Figure(
        "examples/ml-train-test-split",
        W,
        470,
        "Train / Test Split with test size 0.25, stratified on churn and seed 42, sends 12 of the 16 "
        "customers to training, 6 churned and 6 stayed, and holds out customers 3, 8, 13 and 14, 2 of "
        "each. The model learns only from the 12 training rows; Predict and Evaluate score the 4 test rows.",
    )
    fig.heading(44, 56, "the test rows stay out of training")
    churn = {i: i % 2 for i in range(1, 17)}
    test = [8, 3, 14, 13]
    cell, gap = 44, 8
    x = 44
    y = 108
    fig.note(x, y - 8, "16 customers · yellow = churned", size=21)
    for k, cid in enumerate(range(1, 17)):
        _id_cell(fig, x + k * (cell + gap) + 30, y + 14, cid, churn[cid])
    split_y = y + 14 + cell + 60
    fig.pill(380, split_y - 34, "test size 0.25 · stratify: churn · seed 42", role="mono", size=12.5)
    train = [c for c in range(1, 17) if c not in test]
    ty = split_y + 30
    fig.text(44, ty - 12, "train: 12 rows, 6 churned, 6 stayed", size=15, weight=650, fill=GREEN)
    for k, cid in enumerate(train):
        _id_cell(
            fig,
            44 + k * (cell + gap) - (0 if k < 6 else 6 * (cell + gap)),
            ty + (0 if k < 6 else cell + gap),
            cid,
            churn[cid],
        )
    tx = 640
    fig.text(tx, ty - 12, "test: 4 rows, 2 and 2", size=15, weight=650, fill=RED)
    fig.box(tx - 10, ty - 6, 2 * (cell + gap) + 12, 2 * (cell + gap) + 4, r=10, stroke=RED, dash="6 5", double=False)
    for k, cid in enumerate(test):
        _id_cell(fig, tx + (k % 2) * (cell + gap), ty + (k // 2) * (cell + gap), cid, churn[cid])
    ny = ty + 2 * (cell + gap) + 30
    fig.node(44, ny, "Train Classifier", "learns from these 12", kind="ml")
    fig.node(tx - 10, ny, "Predict → Evaluate", "scores these 4", kind="ml")
    fig.step(270, tx - 30, ny + 34, "model wire")
    fig.note(tx + 2 * (cell + gap) + 26, ty + 40, ["never seen", "in training"], size=23, fill=RED)
    return fig


@figure("examples/ml-id-leak")
def ml_id_leak() -> Figure:
    fig = Figure(
        "examples/ml-id-leak",
        W,
        450,
        "In the churn sample every odd customer_id churned and every even one stayed. With Feature "
        "columns left empty the model also trains on customer_id and can predict churn from the ID "
        "alone. Listing tenure, monthly_charges and support_calls keeps the ID out.",
    )
    fig.heading(44, 56, "an ID column can predict the sample, not customers")
    cols = ["customer_id", "churn"]
    rows = [[i, i % 2] for i in range(1, 9)]
    left, top = 60, 100
    styles = {r: {"fill": MARKER_SOFT} for r in range(0, 8, 2)}
    tw, th = fig.table(left, top, cols, rows, row_h=32, row_styles=styles)
    fig.note(left + tw + 24, top + 80, ["odd id → churn 1", "even id → churn 0", "in all 16 rows"], size=23, fill=INK)
    bx = 520
    fig.text(bx, 150, "Feature columns: empty", size=16, weight=650, fill=RED)
    fig.text(bx, 176, "trains on customer_id too", role="mono", size=13, fill=RED)
    fig.cross(bx - 30, 138, color=RED)
    fig.text(bx, 266, "Feature columns:", size=16, weight=650, fill=GREEN)
    fig.text(bx, 292, "tenure, monthly_charges,", role="mono", size=13, fill=GREEN)
    fig.text(bx, 312, "support_calls", role="mono", size=13, fill=GREEN)
    fig.check(bx - 32, 252, color=GREEN)
    fig.note(bx, 380, ["a perfect score from the ID", "says nothing about churn"], size=22)
    return fig


# -- time-series ------------------------------------------------------------------


@figure("examples/timeseries-rolling-window")
def timeseries_rolling_window() -> Figure:
    fig = Figure(
        "examples/timeseries-rolling-window",
        W,
        430,
        "A Rolling Aggregate mean with a window of 2 rows moves down the monthly table one row at a "
        "time. January has no earlier row, so its window is not full and the result is null. February "
        "averages 24 and 30 to 27, and March averages 30 and 30 to 30.",
    )
    fig.heading(44, 56, "the window moves down one row at a time")
    cols = ["month", "total_value"]
    rows = [["2024-01", "24.0"], ["2024-02", "30.0"], ["2024-03", "30.0"]]
    tw, th, _ = fig.table_size(cols, rows, row_h=34)
    gap = (W - 88 - 3 * tw) / 2
    results = [
        ("January: null", ["window not full,", "no earlier row"], RED),
        ("February: 27.0", ["(24 + 30) / 2"], GREEN),
        ("March: 30.0", ["(30 + 30) / 2"], GREEN),
    ]
    top = 140
    for k, (title, detail, color) in enumerate(results):
        x = 44 + k * (tw + gap)
        window = {r: {"fill": MARKER} for r in range(max(0, k - 1), k + 1)}
        fig.table(x, top, cols, rows, row_h=34, row_styles=window)
        fig.text(x, top + th + 40, title, size=17, weight=650, fill=color)
        fig.note(x, top + th + 72, detail, size=22)
        if k < 2:
            fig.arrow([(x + tw + 14, top + th / 2), (x + tw + gap - 14, top + th / 2)], stroke=INK_SOFT)
    fig.note(44, top - 18, "yellow = rows inside the window for that month", size=21)
    return fig
