"""Figures for docs/recipes/.

Every value drawn here comes from running the recipe's sample data through
Ciaren's pandas and Polars engines; keep a figure and its page in sync.
"""

from __future__ import annotations

from build import figure
from sketch import (
    GREEN,
    GREEN_SOFT,
    INK_FAINT,
    INK_SOFT,
    MARKER,
    RED,
    RED_SOFT,
    VIOLET,
    Figure,
)

ROW_H = 30
SPACE = "·"  # drawn in place of a space character, explained by a note


def _row_center(table_y: float, row: int) -> float:
    """Vertical center of data row `row` (0-based) in a table drawn at `table_y`."""
    return table_y + ROW_H * (row + 1) + ROW_H / 2


def _row_notes(fig: Figure, x: float, table_y: float, notes: dict[int, tuple[str, str]], size: float = 21) -> None:
    """Handwritten notes level with table rows: {row: (text, color)}."""
    for row, (text, color) in notes.items():
        fig.note(x, _row_center(table_y, row) + size * 0.3, text, size=size, fill=color)


@figure("recipes/remove-duplicates-keep")
def remove_duplicates_keep() -> Figure:
    fig = Figure(
        "recipes/remove-duplicates-keep",
        980,
        470,
        "Remove Duplicates keeps the first matching row in the current order. Sorting by "
        "updated_at, newest first, makes the newest row the one that survives.",
    )
    cols = ["name", "email", "updated_at"]
    loaded = [
        ["Ada", "ada@x.io", "2024-01-03"],
        ["Lin", "lin@x.io", "2024-02-11"],
        ["Ada L.", "ada@x.io", "2024-03-20"],
    ]
    newest_first = [loaded[2], loaded[1], loaded[0]]
    tw, th, _ = fig.table_size(cols, loaded)
    left, right = 44, 980 - 44 - tw

    fig.heading(44, 56, "keep: first means first in the current row order")

    lanes = [
        (126, "as loaded", INK_SOFT, loaded, "the older Ada survives", RED),
        (306, "after Sort Rows: updated_at, newest first", VIOLET, newest_first, "the newest Ada survives", GREEN),
    ]
    for y, label, color, rows, verdict, verdict_color in lanes:
        fig.note(left, y - 12, label, size=22, fill=color)
        fig.table(
            left,
            y,
            cols,
            rows,
            row_styles={0: {"fill": GREEN_SOFT}, 2: {"strike": True, "fill": RED_SOFT}},
            cell_styles={(0, 2): {"fill": MARKER}} if rows is newest_first else None,
        )
        fig.step(left + tw + 22, right - 22, y + th / 2 + 8, "subset: email · keep: first")
        fig.table(right, y + 15, cols, rows[:2], row_styles={0: {"fill": GREEN_SOFT}})
        fig.note(right + 4, y + th + 12, verdict, size=23, fill=verdict_color)
    fig.check(right - 26, 306 + 15 + 36, color=GREEN)
    return fig


@figure("recipes/remove-duplicates-subset")
def remove_duplicates_subset() -> Figure:
    fig = Figure(
        "recipes/remove-duplicates-subset",
        980,
        540,
        "With an empty subset, Remove Duplicates drops only the row that repeats every "
        "column, so Ada and Ada L. both stay. With subset email, rows that share an email "
        "are duplicates, so only the first Ada and the first Lin stay.",
    )
    cols = ["name", "email", "updated_at"]
    rows = [
        ["Ada", "ada@x.io", "2024-01-03"],
        ["Lin", "lin@x.io", "2024-02-11"],
        ["Ada L.", "ada@x.io", "2024-03-20"],
        ["Lin", "lin@x.io", "2024-02-11"],
    ]
    tw, th, _ = fig.table_size(cols, rows)
    left, right = 44, 980 - 44 - tw

    fig.heading(44, 56, "the subset decides what counts as the same row")

    dropped = {"strike": True, "fill": RED_SOFT}
    lanes = [
        (
            126,
            "Subset empty: every column must match",
            {3: dropped},
            None,
            [0, 1, 2],
            "names differ, so both Adas stay",
        ),
        (
            330,
            "Subset: email",
            {2: dropped, 3: dropped},
            {(0, 1): {"fill": MARKER}, (2, 1): {"fill": MARKER}},
            [0, 1],
            "one row per email",
        ),
    ]
    for y, label, row_styles, cell_styles, kept, verdict in lanes:
        fig.note(left, y - 12, label, size=22, fill=VIOLET)
        fig.table(left, y, cols, rows, row_styles=row_styles, cell_styles=cell_styles)
        fig.step(left + tw + 22, right - 22, y + th / 2 + 8, "keep: first")
        fig.table(right, y, cols, [rows[i] for i in kept])
        fig.note(right + 4, y + ROW_H * (len(kept) + 1) + 28, verdict, size=22, fill=GREEN)
    return fig


@figure("recipes/fill-nulls-mean-median")
def fill_nulls_mean_median() -> Figure:
    fig = Figure(
        "recipes/fill-nulls-mean-median",
        980,
        420,
        "The age column has one null and one outlier, 95. Filling with the mean writes "
        "47.75 because the outlier pulls the average up; filling with the median writes 35.5.",
    )
    fig.heading(44, 56, "one outlier moves the mean, not the median")
    cols = ["respondent_id", "age"]
    rows = [[1, 25], [2, None], [3, 40], [4, 31], [5, 95]]
    ty = 110
    tw, th = fig.table(
        44,
        ty,
        cols,
        rows,
        cell_styles={(1, 1): {"fill": MARKER}, (4, 1): {"fill": RED_SOFT}},
    )
    fig.note(44, ty + th + 40, "95 is an outlier", size=22, fill=RED)
    fig.arrow([(166, ty + th + 28), (182, ty + th + 6)], stroke=RED, head=9)

    nx = 44 + tw + 130
    fig.arrow([(44 + tw + 18, _row_center(ty, 1)), (nx - 18, 141)], stroke=INK_SOFT)
    fig.arrow([(44 + tw + 18, _row_center(ty, 1) + 8), (nx - 18, 271)], stroke=INK_SOFT)
    results = [
        (110, "strategy: mean", "47.75", "(25 + 40 + 31 + 95) / 4", RED),
        (240, "strategy: median", "35.5", "middle of 25, 31, 40, 95", GREEN),
    ]
    for y, detail, value, how, color in results:
        _, _, w, h = fig.node(nx, y, "Fill Nulls", detail, kind="clean", w=210)
        fig.arrow([(nx + w + 16, y + h / 2), (nx + w + 70, y + h / 2)], stroke=INK_SOFT)
        fig.text(nx + w + 86, y + h / 2 + 9, value, role="mono", size=26, weight=600, fill=color)
        fig.note(nx + w + 86, y + h / 2 + 40, how, size=20, fill=INK_SOFT)
    fig.check(nx + 210 + 190, 240 + 18, color=GREEN)
    return fig


@figure("recipes/clean-text-strip-lower")
def clean_text_strip_lower() -> Figure:
    fig = Figure(
        "recipes/clean-text-strip-lower",
        980,
        290,
        "Two emails for the same customer differ by surrounding spaces and by letter case. "
        "Strip spaces removes the spaces, Lowercase removes the case difference, and only "
        "after both steps are the two values equal.",
    )
    fig.heading(44, 56, "the two emails match only after both steps")
    ty = 120
    raw = [[1, f"{SPACE * 2}ADA@EXAMPLE.COM{SPACE}"], [4, "ada@example.com"]]
    stripped = [["ADA@EXAMPLE.COM"], ["ada@example.com"]]
    lowered = [["ada@example.com"], ["ada@example.com"]]

    x = 44
    w1, th = fig.table(x, ty, ["customer_id", "email"], raw, cell_styles={(0, 1): {"fill": MARKER}})
    fig.note(x, ty + th + 34, f"{SPACE} marks a space", size=21, fill=INK_SOFT)
    x2 = x + w1 + 140
    fig.step(x + w1 + 16, x2 - 16, ty + th / 2 + 8, "Strip spaces", role="sans")
    w2, _ = fig.table(x2, ty, ["email"], stripped, cell_styles={(0, 0): {"fill": RED_SOFT}})
    fig.note(x2, ty + th + 34, "still different: case", size=21, fill=RED)
    x3 = x2 + w2 + 140
    fig.step(x2 + w2 + 16, x3 - 16, ty + th / 2 + 8, "Lowercase", role="sans")
    fig.table(x3, ty, ["email"], lowered, row_styles={0: {"fill": GREEN_SOFT}, 1: {"fill": GREEN_SOFT}})
    fig.note(x3, ty + th + 34, "equal: a join can match them", size=21, fill=GREEN)
    return fig


@figure("recipes/coalesce-first-non-null")
def coalesce_first_non_null() -> Figure:
    fig = Figure(
        "recipes/coalesce-first-non-null",
        980,
        330,
        "Coalesce Columns reads primary_email, then backup_email, and copies the first value "
        "that is not null into email. A value that is only a space is not null, so it wins "
        "over the backup in row 4.",
    )
    fig.heading(44, 56, "the first value that is not null wins, left to right")
    cols = ["customer_id", "primary_email", "backup_email", "email"]
    rows = [
        [1, "ada@example.com", "ada.backup@example.com", "ada@example.com"],
        [2, None, "grace@example.com", "grace@example.com"],
        [3, None, None, None],
        [4, SPACE, "lin@example.com", SPACE],
    ]
    ty = 110
    picked = {"fill": GREEN_SOFT}
    tw, _ = fig.table(
        44,
        ty,
        cols,
        rows,
        cell_styles={(0, 1): picked, (1, 2): picked, (3, 1): {"fill": MARKER}, (3, 3): {"fill": MARKER}},
    )
    _row_notes(
        fig,
        44 + tw + 22,
        ty,
        {
            0: ("primary is set: use it", GREEN),
            1: ("primary is null: use backup", GREEN),
            2: ("both null: email is null", INK_SOFT),
            3: ("a space is not null: it wins", RED),
        },
    )
    fig.note(44, ty + ROW_H * 5 + 34, f"{SPACE} marks a space", size=21, fill=INK_SOFT)
    return fig


@figure("recipes/excel-one-sheet")
def excel_one_sheet() -> Figure:
    fig = Figure(
        "recipes/excel-one-sheet",
        980,
        430,
        "A workbook has a Summary sheet and an Orders sheet. Ciaren imports one sheet: the "
        "first unless you name another under Import options. The Parquet file stores one type "
        "per column. The zip that Excel displays as 02134 is the number 2134, so Parquet stores 2134.",
    )
    fig.heading(44, 56, "one sheet becomes the dataset: the first, unless you name it")
    x = 44
    fig.note(x, 108, "sheet 0: Summary", size=21, fill=INK_SOFT)
    fig.table(x, 120, ["note"], [["Q1 totals are on the Orders sheet"]], row_styles={0: {"color": INK_FAINT}})
    fig.note(x + 312, 158, "imported when no sheet is named", size=21, fill=INK_SOFT)
    fig.note(x, 228, "sheet 1: Orders", size=21, fill=INK_SOFT)
    orders = [
        ["ORD-1", "2024-01-05", "250.0", "02134"],
        ["ORD-2", "2024-01-06", "99.99", "10001"],
        ["ORD-3", "2024-01-09", "100.0", "94105"],
    ]
    w1, th = fig.table(
        x, 240, ["order_id", "order_date", "amount", "zip"], orders, cell_styles={(0, 3): {"fill": MARKER}}
    )

    px = 980 - 44 - 360
    fig.step(x + w1 + 18, px - 18, 240 + th / 2 + 8, "sheet: Orders")
    parquet = [["str", "datetime", "float", "int"]] + [[o[0], o[1], o[2], o[3].lstrip("0")] for o in orders]
    fig.note(px, 213, "orders.parquet", size=21, fill=GREEN)
    fig.table(
        px,
        225,
        ["order_id", "order_date", "amount", "zip"],
        parquet,
        widths=[90, 110, 80, 80],
        row_styles={0: {"color": VIOLET}},
        cell_styles={(1, 3): {"fill": MARKER}},
    )
    fig.note(px, 225 + ROW_H * 5 + 32, "Excel only displayed 02134: the value is 2134", size=21, fill=RED)
    return fig


@figure("recipes/filter-two-conditions")
def filter_two_conditions() -> Figure:
    fig = Figure(
        "recipes/filter-two-conditions",
        980,
        300,
        "Filter by Expression checks amount >= 100 and status == 'paid' on every row. Only "
        "ORD-1003 and ORD-1004 pass both, and 100.00 passes because >= includes the boundary.",
    )
    fig.heading(44, 56, "a row stays only when both conditions are true")
    cols = ["order_id", "amount", "status", "amount >= 100", "status == 'paid'"]
    data = [
        ["ORD-1001", "250.00", "pending"],
        ["ORD-1002", "99.99", "paid"],
        ["ORD-1003", "100.00", "paid"],
        ["ORD-1004", "180.50", "paid"],
    ]
    verdicts = [(True, False), (False, True), (True, True), (True, True)]
    rows = [d + ["", ""] for d in data]
    widths = [100, 84, 90, 132, 142]
    ty = 110
    dropped = {"strike": True, "fill": RED_SOFT}
    kept = {"fill": GREEN_SOFT}
    tw, _ = fig.table(
        44,
        ty,
        cols,
        rows,
        widths=widths,
        row_styles={0: dropped, 1: dropped, 2: kept, 3: kept},
        cell_styles={(2, 1): {"fill": MARKER}},
    )
    for r, flags in enumerate(verdicts):
        for c, ok in enumerate(flags):
            cx = 44 + sum(widths[: 3 + c]) + widths[3 + c] / 2 - 8
            cy = _row_center(ty, r) - 8
            if ok:
                fig.check(cx, cy, size=16, color=GREEN)
            else:
                fig.cross(cx + 1, cy + 1, size=14, color=RED)
    _row_notes(
        fig,
        44 + tw + 22,
        ty,
        {
            0: ("not paid: dropped", RED),
            1: ("below 100: dropped", RED),
            2: (">= includes 100: kept", GREEN),
            3: ("both true: kept", GREEN),
        },
    )
    return fig


@figure("recipes/split-to-rows-fanout")
def split_to_rows_fanout() -> Figure:
    fig = Figure(
        "recipes/split-to-rows-fanout",
        980,
        430,
        "Split to Rows with delimiter ; turns five records into eight rows. Each tag gets its "
        "own row with the record_id repeated, a null stays one null row, a trailing ; adds an "
        "empty tag, and a space after ; stays in the tag.",
    )
    fig.heading(44, 56, "one row per tag, and the record_id comes along")
    src = [["r1", "news;sports"], ["r2", "news"], ["r3", None], ["r4", "a;"], ["r5", f"news;{SPACE}sports"]]
    out = [
        ["r1", "news"],
        ["r1", "sports"],
        ["r2", "news"],
        ["r3", None],
        ["r4", "a"],
        ["r4", '""'],
        ["r5", "news"],
        ["r5", f"{SPACE}sports"],
    ]
    cols = ["record_id", "tags"]
    sy, oy = 130, 100
    w1, th = fig.table(44, sy, cols, src, row_styles={0: {"fill": GREEN_SOFT}})
    fig.note(44, sy + th + 34, f"{SPACE} marks a space", size=21, fill=INK_SOFT)
    ox = 44 + w1 + 150
    fig.step(44 + w1 + 18, ox - 18, sy + th / 2 + 8, "delimiter: ;")
    w2, _ = fig.table(
        ox,
        oy,
        cols,
        out,
        row_styles={0: {"fill": GREEN_SOFT}, 1: {"fill": GREEN_SOFT}},
        cell_styles={(5, 1): {"fill": MARKER}, (7, 1): {"fill": MARKER}},
    )
    nx = ox + w2 + 22
    fig.note(nx, _row_center(oy, 0) + 21, "r1 becomes two rows", size=21, fill=GREEN)
    _row_notes(
        fig,
        nx,
        oy,
        {
            3: ("a null stays one null row", INK_SOFT),
            5: ("trailing ; adds an empty tag", RED),
            7: ("the space after ; stays", RED),
        },
    )
    return fig


@figure("recipes/pivot-cell-placement")
def pivot_cell_placement() -> Figure:
    fig = Figure(
        "recipes/pivot-cell-placement",
        980,
        320,
        "Pivot Table turns month values into columns. The two North and Jan rows, 100 and 30, "
        "sum into one cell, 130.0. pandas sorts the month columns, and South has no Feb row, "
        "so that cell is null on pandas and 0 on the Polars engine.",
    )
    fig.heading(44, 56, "each region and month pair becomes one cell")
    long_rows = [["North", "Jan", 100], ["North", "Feb", 120], ["South", "Jan", 80], ["North", "Jan", 30]]
    ty = 120
    w1, th = fig.table(
        44,
        ty,
        ["region", "month", "amount"],
        long_rows,
        cell_styles={(0, 2): {"fill": MARKER}, (3, 2): {"fill": MARKER}},
    )
    wx = 44 + w1 + 190
    fig.step(44 + w1 + 18, wx - 18, ty + th / 2 + 8, "Aggregation: sum")
    wy = 150
    ww, _ = fig.table(
        wx,
        wy,
        ["region", "Feb", "Jan"],
        [["North", "120.0", "130.0"], ["South", None, "80.0"]],
        widths=[90, 74, 74],
        cell_styles={(0, 2): {"fill": MARKER}, (1, 1): {"fill": RED_SOFT}},
    )
    nx = wx + ww + 22
    _row_notes(fig, nx, wy, {0: ("100 + 30 = 130", INK_SOFT), 1: ("no South Feb row", RED)})
    fig.note(nx, _row_center(wy, 1) + 34, ["pandas writes null,", "Polars writes 0"], size=21, fill=RED)
    fig.note(wx, wy - 14, "pandas output", size=21, fill=INK_SOFT)
    return fig


@figure("recipes/split-column-parts")
def split_column_parts() -> Figure:
    fig = Figure(
        "recipes/split-column-parts",
        980,
        330,
        "Split Column with delimiter | and new columns region, city fills the pieces in order. "
        "EU has no second piece, so city is null; US|Austin|TX has a third piece with no "
        "column, so TX is dropped.",
    )
    fig.heading(44, 56, "pieces fill the new columns in order")
    src = [["S1", "EU|Paris"], ["S2", "US|Boston"], ["S3", "EU"], ["S4", None], ["S5", "US|Austin|TX"]]
    out = [["EU", "Paris", ""], ["US", "Boston", ""], ["EU", None, ""], [None, None, ""], ["US", "Austin", "TX"]]
    ty = 110
    w1, th = fig.table(44, ty, ["store_id", "location"], src)
    ox = 44 + w1 + 170
    fig.step(44 + w1 + 18, ox - 18, ty + th / 2 + 8, "delimiter: |")
    widths = [84, 84, 100]
    w2, _ = fig.table(
        ox,
        ty,
        ["region", "city", "3rd piece"],
        out,
        widths=widths,
        col_styles={2: {"color": INK_FAINT}},
        cell_styles={(2, 1): {"fill": MARKER}, (4, 2): {"fill": RED_SOFT, "color": RED}},
    )
    tx = ox + widths[0] + widths[1]
    fig.strike(tx + 8, _row_center(ty, 4), widths[2] - 16)
    nx = ox + w2 + 22
    _row_notes(fig, nx, ty, {2: ("no 2nd piece: null", INK_SOFT), 4: ("no 3rd column: dropped", RED)})
    return fig
