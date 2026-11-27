"""Figures for the ciaren.com blog posts (written to website/public/illustrations/blog/)."""

from __future__ import annotations

from build import figure
from sketch import (
    GREEN,
    GREEN_SOFT,
    INK,
    INK_FAINT,
    INK_SOFT,
    MARKER,
    RED,
    RED_SOFT,
    VIOLET,
    VIOLET_SOFT,
    Figure,
)

W = 980
LEFT = 44
RIGHT = W - 44
CODE_FILL = "#F4EFE6"


def code_panel(
    fig: Figure,
    x: float,
    y: float,
    lines: list[str],
    *,
    w: float,
    line_h: float = 24,
    size: float = 12.5,
    marks: dict[int, str] | None = None,
) -> float:
    """A box of monospace source lines; `marks` highlights lines by index. Returns its height."""
    marks = marks or {}
    pad = 14
    h = len(lines) * line_h + 2 * pad - 6
    longest = max(fig.measure(line, role="mono", size=size) for line in lines)
    if longest + 2 * pad > w:
        raise ValueError(f"code panel at {x:.0f},{y:.0f}: {longest + 2 * pad:.0f}px of text in a {w:.0f}px panel")
    fig._open(f"code@{x:.0f},{y:.0f}", x, y, x + w, y + h)
    fig.box(x, y, w, h, r=10, fill=CODE_FILL, stroke=INK, width=1.4, double=False, fill_offset=2)
    for i, line in enumerate(lines):
        baseline = y + pad + 11 + i * line_h
        code = line.lstrip()
        # SVG collapses leading spaces in <text>, so indentation is an x offset.
        indent = fig.measure(line[: len(line) - len(code)], role="mono", size=size)
        if i in marks:
            lw = fig.measure(code, role="mono", size=size)
            fig.marker(x + pad + indent - 4, baseline - 13, lw + 8, 18, color=marks[i], opacity=0.6)
        if code:
            fig.text(x + pad + indent, baseline, code, role="mono", size=size)
    fig._owner = None
    return h


def code_line_y(y: float, i: int, *, line_h: float = 24) -> float:
    """Vertical center of line `i` in a code_panel drawn at `y`."""
    return y + 14 + 11 + i * line_h - 4


def value_card(
    fig: Figure, x: float, y: float, value: str, caption: str, *, color: str, soft: str
) -> tuple[float, float]:
    """A big monospace value with a small caption under it, in a tinted box. Returns (w, h)."""
    vw = fig.measure(value, role="mono", size=22)
    cw = fig.measure(caption, role="sans", size=12.5)
    w, h = max(vw, cw) + 32, 70
    fig._open(f"value {value}@{x:.0f}", x, y, x + w, y + h)
    fig.box(x, y, w, h, r=10, fill=soft, stroke=color, width=1.6)
    fig.text(x + 16, y + 32, value, role="mono", size=22, fill=INK)
    fig.text(x + 16, y + 55, caption, role="sans", size=12.5, fill=INK_SOFT)
    fig._owner = None
    return w, h


def region(
    fig: Figure, x: float, y: float, w: float, h: float, label: str, *, color: str = INK_SOFT, dash: str | None = None
) -> None:
    """A large dashed area with a label tab; contents are drawn separately."""
    fig.box(x, y, w, h, r=16, stroke=color, width=1.5, double=False, dash=dash or "7 6")
    fig.text(x + 18, y + 26, label, role="sans", size=14, weight=650, fill=color)


# --------------------------------------------------------------------------
# Deduplicate revisions
# --------------------------------------------------------------------------


@figure("blog/dedupe-tie-breaker")
def dedupe_tie_breaker() -> Figure:
    fig = Figure(
        "blog/dedupe-tie-breaker",
        W,
        610,
        "Two revisions of supplier S04's LAMP-1 share the timestamp 09:00. Sorted by updated_at alone, "
        "Remove Duplicates keeps revision 9 from the file as delivered and revision 10 from the same rows "
        "reversed. Adding revision as the second sort key keeps revision 10 in both cases.",
    )
    cols = ["updated_at", "revision", "status"]
    r9 = ["2026-11-10 09:00", 9, "available"]
    r10 = ["2026-11-10 09:00", 10, "discontinued"]
    r8 = ["2026-11-09 15:00", 8, "backordered"]
    tw, th, widths = fig.table_size(cols, [r9, r10, r8])
    out_cols = ["revision", "status"]
    ow, oh, out_widths = fig.table_size(out_cols, [[10, "discontinued"]])
    right = RIGHT - ow

    fig.heading(LEFT, 56, "A tied timestamp leaves the winner to file order")

    lanes = [
        (
            130,
            "file as delivered · Sort Rows: updated_at",
            INK_SOFT,
            [r9, r10, r8],
            RED_SOFT,
            "revision 9 wins",
            RED,
            False,
        ),
        (
            292,
            "same rows reversed · Sort Rows: updated_at",
            INK_SOFT,
            [r10, r9, r8],
            GREEN_SOFT,
            "revision 10 wins, by luck",
            RED,
            False,
        ),
        (
            454,
            "either order · Sort Rows: updated_at, then revision",
            VIOLET,
            [r10, r9, r8],
            GREEN_SOFT,
            "revision 10 wins every time",
            GREEN,
            True,
        ),
    ]
    for y, label, color, rows, kept_fill, verdict, verdict_color, tie_broken in lanes:
        fig.note(LEFT, y - 12, label, size=22, fill=color)
        cells = {(0, 0): {"fill": MARKER}, (1, 0): {"fill": MARKER}}
        if tie_broken:
            cells = {(0, 1): {"fill": MARKER}, (1, 1): {"fill": MARKER}}
        fig.table(
            LEFT,
            y,
            cols,
            rows,
            widths=widths,
            row_styles={0: {"fill": kept_fill}, 1: {"strike": True}, 2: {"strike": True}},
            cell_styles=cells,
        )
        fig.step(LEFT + tw + 22, right - 22, y + th / 2 + 8, "keep: first")
        fig.table(right, y + 30, out_cols, [rows[0][1:]], widths=out_widths, row_styles={0: {"fill": kept_fill}})
        fig.note(right + 4, y + 30 + oh + 24, verdict, size=22, fill=verdict_color)
    fig.check(right - 30, 454 + 30 + 36, color=GREEN)
    fig.cross(right - 30, 130 + 30 + 38, color=RED)
    return fig


@figure("blog/dedupe-equal-rank")
def dedupe_equal_rank() -> Figure:
    fig = Figure(
        "blog/dedupe-equal-rank",
        W,
        330,
        "Two rows with the same supplier, SKU, timestamp and revision but different statuses have equal rank. "
        "Assert Unique on those four columns in error mode stops the run instead of letting either status win.",
    )
    cols = ["supplier_id", "sku", "updated_at", "revision", "status"]
    rows = [
        ["S04", "LAMP-1", "2026-11-10 09:00", 10, "available"],
        ["S04", "LAMP-1", "2026-11-10 09:00", 10, "discontinued"],
    ]
    tw, th, _ = fig.table_size(cols, rows)
    fig.heading(LEFT, 56, "Equal rank on every sort key: stop, do not pick")
    y = 116
    fig.table(LEFT, y, cols, rows, cell_styles={(0, 4): {"fill": RED_SOFT}, (1, 4): {"fill": RED_SOFT}})
    fig.note(LEFT, y + th + 34, ["same four sort keys,", "different status"], size=22, fill=INK_SOFT)
    nx = LEFT + tw + 70
    fig.arrow([(LEFT + tw + 14, y + th / 2), (nx - 12, y + th / 2)], stroke=INK_SOFT)
    _, _, nw, nh = fig.node(nx, y + th / 2 - 31, "Assert Unique", "On violation: Error", kind="check")
    fig.cross(nx + 4, y + th / 2 + 52, color=RED)
    fig.note(nx + 28, y + th / 2 + 66, ["run stops:", "2 duplicate rows"], size=22, fill=RED)
    fig.note(LEFT + 300, y + th + 34, ["columns: supplier_id, sku,", "updated_at, revision"], size=22, fill=VIOLET)
    return fig


# --------------------------------------------------------------------------
# Left join fan-out
# --------------------------------------------------------------------------


ORDERS_COLS = ["order_id", "customer_id", "amount"]
ORDERS = [[1001, "C12", 120], [1002, "C18", 80], [1003, "C99", 50], [1004, "C12", 80]]
DIRECTORY_COLS = ["assignment_id", "customer_id", "region", "state"]
DIRECTORY = [["A1", "C12", "West", "archived"], ["A2", "C12", "North", "current"], ["A3", "C18", "South", "current"]]


@figure("blog/left-join-fanout")
def left_join_fanout() -> Figure:
    fig = Figure(
        "blog/left-join-fanout",
        W,
        640,
        "Customer C12 has two rows in the region directory, so a left join on customer_id returns orders 1001 "
        "and 1004 twice each. The four orders total 330 before the join and 530 after it; order 1003 has no "
        "match and keeps one row with a null region.",
    )
    fig.heading(LEFT, 56, "Two directory rows for C12 means two copies of each C12 order")
    ow, oh, _ = fig.table_size(ORDERS_COLS, ORDERS)
    dw, dh, _ = fig.table_size(DIRECTORY_COLS, DIRECTORY)
    top = 116
    fig.note(LEFT, top - 12, "orders · total 330", size=22, fill=INK_SOFT)
    fig.table(LEFT, top, ORDERS_COLS, ORDERS, cell_styles={(0, 1): {"fill": MARKER}, (3, 1): {"fill": MARKER}})
    dx = RIGHT - dw
    fig.note(dx, top - 12, "region directory", size=22, fill=INK_SOFT)
    fig.table(dx, top, DIRECTORY_COLS, DIRECTORY, cell_styles={(0, 1): {"fill": MARKER}, (1, 1): {"fill": MARKER}})

    nx, ny = 372, 296
    _, _, nw, nh = fig.node(nx, ny, "Join / Merge", "Join on: customer_id · Left", kind="transform")
    fig.arrow([(LEFT + ow / 2, top + oh + 10), (LEFT + ow / 2 + 30, ny + 20), (nx - 12, ny + nh / 2)], stroke=INK_SOFT)
    fig.arrow([(dx + dw / 2, top + dh + 10), (dx + dw / 2 - 30, ny + 20), (nx + nw + 12, ny + nh / 2)], stroke=INK_SOFT)

    result_cols = ["order_id", "customer_id", "amount", "region"]
    result = [
        [1001, "C12", 120, "West"],
        [1001, "C12", 120, "North"],
        [1002, "C18", 80, "South"],
        [1003, "C99", 50, None],
        [1004, "C12", 80, "West"],
        [1004, "C12", 80, "North"],
    ]
    rw, rh, _ = fig.table_size(result_cols, result)
    rx, ry = nx + nw / 2 - rw / 2, 410
    fig.arrow([(nx + nw / 2, ny + nh + 8), (nx + nw / 2, ry - 10)], stroke=INK_SOFT)
    fig.table(
        rx,
        ry,
        result_cols,
        result,
        row_styles={0: {"fill": RED_SOFT}, 4: {"fill": RED_SOFT}},
        cell_styles={(3, 3): {"fill": MARKER}},
    )
    fig.note(rx + rw + 30, ry + 40, ["C12 matched twice:", "+120 and +80"], size=22, fill=RED)
    fig.note(rx + rw + 30, ry + 130, "total 530, not 330", size=24, fill=RED)
    fig.note(LEFT, ry + 100, ["1003 has no match:", "one row, region null"], size=22, fill=INK_SOFT)
    return fig


@figure("blog/left-join-fix")
def left_join_fix() -> Figure:
    fig = Figure(
        "blog/left-join-fix",
        W,
        560,
        "Filter Rows keeps only the current assignment for each customer, and Assert Unique on customer_id "
        "confirms one directory row per key. After the left join each order appears once, the amounts sum to "
        "330 again, and the unmatched order 1003 is labeled Unassigned.",
    )
    fig.heading(LEFT, 56, "One lookup row per key before the join, one row per order after it")
    dw, dh, _ = fig.table_size(DIRECTORY_COLS, DIRECTORY)
    y1 = 116
    fig.note(LEFT, y1 - 12, "region directory", size=22, fill=INK_SOFT)
    fig.table(LEFT, y1, DIRECTORY_COLS, DIRECTORY, row_styles={0: {"strike": True, "fill": RED_SOFT}})
    kept_cols = ["customer_id", "region"]
    kept = [["C12", "North"], ["C18", "South"]]
    kw, kh, _ = fig.table_size(kept_cols, kept)
    kx = RIGHT - kw
    fig.step(LEFT + dw + 22, kx - 22, y1 + dh / 2 + 8, "state == 'current'")
    fig.table(kx, y1 + 15, kept_cols, kept, row_styles={0: {"fill": GREEN_SOFT}, 1: {"fill": GREEN_SOFT}})
    fig.check(kx - 32, y1 + 15 + 38, color=GREEN)
    fig.note(LEFT + dw + 22, y1 + dh / 2 + 44, "then Assert Unique: customer_id", size=22, fill=VIOLET)

    result_cols = ["order_id", "customer_id", "amount", "region"]
    result = [
        [1001, "C12", 120, "North"],
        [1002, "C18", 80, "South"],
        [1003, "C99", 50, "Unassigned"],
        [1004, "C12", 80, "North"],
    ]
    rw, rh, _ = fig.table_size(result_cols, result)
    y2 = 330
    fig.note(LEFT, y2 - 12, "after Join / Merge and Fill Nulls", size=22, fill=INK_SOFT)
    fig.table(LEFT, y2, result_cols, result, cell_styles={(2, 3): {"fill": MARKER}})
    fig.note(LEFT, y2 + rh + 30, "Assert Unique: order_id passes", size=22, fill=VIOLET)
    totals_cols = ["region", "amount"]
    totals = [["North", 200], ["South", 80], ["Unassigned", 50]]
    tw, th, _ = fig.table_size(totals_cols, totals)
    tx = RIGHT - tw
    fig.step(LEFT + rw + 22, tx - 22, y2 + rh / 2 + 8, "group by region · sum")
    fig.table(tx, y2 + 15, totals_cols, totals)
    fig.note(tx, y2 + 15 + th + 26, "200 + 80 + 50 = 330", size=24, fill=GREEN)
    return fig


# --------------------------------------------------------------------------
# Pivot monthly return rates
# --------------------------------------------------------------------------


@figure("blog/pivot-mean-vs-ratio")
def pivot_mean_vs_ratio() -> Figure:
    fig = Figure(
        "blog/pivot-mean-vs-ratio",
        W,
        420,
        "In April, Harbor returned 5 of 10 units (50%) and Hill returned 9 of 90 (10%). The mean of the two "
        "store rates is 30%, but 14 of the 100 units sold came back, a return rate of 14%.",
    )
    fig.heading(LEFT, 56, "Averaging store rates gives each store one vote")
    cols = ["store", "sold", "returned", "store rate"]
    rows = [["Harbor", 10, 5, "50%"], ["Hill", 90, 9, "10%"]]
    tw, th, _ = fig.table_size(cols, rows)
    ty = 170
    fig.note(LEFT, ty - 12, "April, two stores", size=22, fill=INK_SOFT)
    fig.table(LEFT, ty, cols, rows, col_styles={3: {"fill": MARKER}})

    x0 = LEFT + tw + 20
    vx = 640
    # upper path: mean of the rate column
    fig.pill(x0 + 40, 108, "mean(store rate)", role="mono", size=12, weight=500, color=INK_SOFT, soft="#F1EBDF")
    fig.arrow([(x0, ty + 20), (x0 + 120, 150), (vx - 14, 142)], stroke=INK_SOFT)
    fig.text(vx, 156, "30%", role="hand", size=46, weight=700, fill=RED)
    fig.cross(vx + 92, 128, color=RED)
    fig.note(vx + 130, 146, ["each store", "counts once"], size=21, fill=RED)
    # lower path: sum the counts, then divide
    fig.pill(x0 + 40, 300, "sum, then 100 * returned / sold", role="mono", size=12, weight=500)
    fig.arrow([(x0, ty + th - 20), (x0 + 120, 280), (vx - 14, 286)], stroke=INK_SOFT)
    fig.text(vx, 300, "14%", role="hand", size=46, weight=700, fill=GREEN)
    fig.check(vx + 92, 272, color=GREEN)
    fig.note(vx + 130, 290, ["14 returned of", "100 sold"], size=21, fill=GREEN)
    fig.note(LEFT, 384, "May shows the same gap: mean 2.5%, actual 4 of 100 = 4%", size=22, fill=INK_SOFT)
    return fig


@figure("blog/pivot-layout")
def pivot_layout() -> Figure:
    fig = Figure(
        "blog/pivot-layout",
        W,
        380,
        "Pivot Table with metric as the index, month as the columns and return_pct as the values turns the two "
        "monthly rows into one row with a column per month. The April rate of 14.0 moves into the 2026-04 column.",
    )
    fig.heading(LEFT, 56, "Pivot moves each monthly rate under its month")
    cols = ["month", "metric", "sold", "returned", "return_pct"]
    rows = [["2026-04", "return_pct", 100, 14, "14.0"], ["2026-05", "return_pct", 100, 4, "4.0"]]
    tw, th, widths = fig.table_size(cols, rows)
    y = 120
    fig.note(LEFT, y - 12, "after Group By and Calculated Column", size=22, fill=INK_SOFT)
    fig.table(LEFT, y, cols, rows, cell_styles={(0, 0): {"fill": VIOLET_SOFT}, (0, 4): {"fill": MARKER}})
    wide_cols = ["metric", "2026-04", "2026-05"]
    wide = [["return_pct", "14.0", "4.0"]]
    ww, wh, wwidths = fig.table_size(wide_cols, wide)
    wx = RIGHT - ww
    fig.step(LEFT + tw + 22, wx - 22, y + th / 2 + 8, "Pivot Table · first")
    fig.table(wx, y + 15, wide_cols, wide, cell_styles={(0, 1): {"fill": MARKER}})
    src_x = LEFT + sum(widths[:4]) + widths[4] / 2
    dst_x = wx + wwidths[0] + wwidths[1] / 2
    fig.arrow(
        [(src_x, y + th + 8), (src_x + 120, y + th + 52), (dst_x - 60, y + th + 40), (dst_x, y + 15 + wh + 8)],
        stroke=VIOLET,
        dash="5 5",
    )
    notes = [
        "index: metric  →  one row per metric",
        "columns: month  →  one column per month",
        "values: return_pct  →  the cells",
    ]
    for i, line in enumerate(notes):
        fig.note(LEFT, 290 + i * 26, line, size=21, fill=VIOLET)
    return fig


# --------------------------------------------------------------------------
# Fallback columns: null vs blank
# --------------------------------------------------------------------------


@figure("blog/fallback-null-vs-blank")
def fallback_null_vs_blank() -> Figure:
    fig = Figure(
        "blog/fallback-null-vs-blank",
        W,
        430,
        "Coalesce Columns falls back to legacy_queue only when current_queue is null. An empty string and a single "
        "space count as values, so tickets T-103 and T-104 keep them unless blanks are trimmed and turned into nulls first.",
    )
    fig.heading(LEFT, 56, "Coalesce skips nulls, not blanks")
    cols = ["ticket_id", "current_queue", "legacy_queue", "coalesce as imported", "blanks as null first"]
    rows = [
        ["T-101", "billing", "general", "billing", "billing"],
        ["T-102", None, "returns", "returns", "returns"],
        ["T-103", '""', "billing", '""', "billing"],
        ["T-104", '" "', "general", '" "', "general"],
        ["T-105", None, None, None, None],
        ["T-106", None, '" "', '" "', None],
    ]
    tw, th, _ = fig.table_size(cols, rows)
    x = (W - tw) / 2
    y = 100
    differs = {}
    for r in (2, 3, 5):
        differs[(r, 3)] = {"fill": RED_SOFT}
        differs[(r, 4)] = {"fill": GREEN_SOFT}
    fig.table(x, y, cols, rows, cell_styles=differs)
    fig.note(
        x,
        y + th + 34,
        ['"" is empty text and " " is one space: both are values,', "so they win over the backup queue"],
        size=22,
        fill=INK_SOFT,
    )
    return fig


@figure("blog/fallback-csv-readers")
def fallback_csv_readers() -> Figure:
    fig = Figure(
        "blog/fallback-csv-readers",
        W,
        430,
        "The same three CSV rows read differently on the two engines. The pandas engine reads both an empty field "
        "and a quoted empty string as null. The Polars engine reads the empty field as null and keeps the quoted "
        "empty string as text. A single space survives on both.",
    )
    fig.heading(LEFT, 56, 'In a CSV, the engine decides whether "" is null')
    csv = ["ticket_id,current_queue", "T-102,", 'T-103,""', 'T-104," "']
    cw = 250
    cy = 150
    ch = code_panel(fig, LEFT, cy, csv, w=cw, line_h=26, size=13)
    fig.note(LEFT, cy - 12, "tickets.csv", size=22, fill=INK_SOFT)
    cols = ["ticket_id", "current_queue"]
    pandas_rows = [["T-102", None], ["T-103", None], ["T-104", '" "']]
    polars_rows = [["T-102", None], ["T-103", '""'], ["T-104", '" "']]
    tw, th, _ = fig.table_size(cols, pandas_rows)
    tx = RIGHT - tw - 200
    ys = (104, 266)
    for ty, label, rows, color, soft, verdict in (
        (ys[0], "pandas engine", pandas_rows, RED, RED_SOFT, ["the blank is gone", "before Coalesce runs"]),
        (ys[1], "Polars engine", polars_rows, GREEN, GREEN_SOFT, ['"" stays text']),
    ):
        fig.note(tx, ty - 12, label, size=22, fill=INK_SOFT)
        fig.table(tx, ty, cols, rows, cell_styles={(1, 1): {"fill": soft}})
        fig.note(tx + tw + 24, ty + 60, verdict, size=22, fill=color)
    mid = cy + ch / 2
    fig.arrow([(LEFT + cw + 14, mid - 10), (tx - 60, ys[0] + 70), (tx - 14, ys[0] + 64)], stroke=INK_SOFT)
    fig.arrow([(LEFT + cw + 14, mid + 10), (tx - 60, ys[1] + 50), (tx - 14, ys[1] + 60)], stroke=INK_SOFT)
    fig.note(LEFT, cy + ch + 40, ['JSON keeps null and ""', "apart on both engines"], size=22, fill=VIOLET)
    return fig


# --------------------------------------------------------------------------
# Excel to Parquet
# --------------------------------------------------------------------------


@figure("blog/excel-leading-zeros")
def excel_leading_zeros() -> Figure:
    fig = Figure(
        "blog/excel-leading-zeros",
        W,
        430,
        "Excel can show 000317 while storing the number 317 under the custom format 000000. File Input reads the "
        "number 317. Change Types to string then gives the text 317, while String Transform padding to width 6 "
        "with 0 on the left gives 000317.",
    )
    fig.heading(LEFT, 56, "The sheet shows 000317. The reader gets 317.")
    y = 200
    w1, h1 = value_card(fig, LEFT, y, "000317", "Excel shows · format 000000", color=INK_SOFT, soft="#F1EBDF")
    vx = LEFT + w1 + 150
    fig.step(LEFT + w1 + 14, vx - 14, y + h1 / 2 + 6, "File Input")
    w2, h2 = value_card(fig, vx, y, "317", "integer column", color=INK_SOFT, soft="#F1EBDF")
    nx = vx + w2 + 40
    _, _, nw, nh = fig.node(nx, 116, "Change Types", "store_code → string", kind="clean")
    _, _, nw2, nh2 = fig.node(nx, 300, "String Transform", "Pad width · 6 · 0 · Left", kind="clean")
    fig.arrow([(vx + w2 + 10, y + 20), (nx - 30, 150), (nx - 12, 147)], stroke=INK_SOFT)
    fig.arrow([(vx + w2 + 10, y + h2 - 20), (nx - 30, 326), (nx - 12, 331)], stroke=INK_SOFT)
    rx = nx + max(nw, nw2) + 30
    fig.arrow([(nx + nw + 10, 147), (rx - 12, 147)], stroke=INK_SOFT)
    fig.arrow([(nx + nw2 + 10, 331), (rx - 12, 331)], stroke=INK_SOFT)
    fig.text(rx, 156, '"317"', role="mono", size=24, fill=RED)
    fig.cross(rx + 4, 180, color=RED)
    fig.note(rx + 28, 194, "join misses", size=21, fill=RED)
    fig.text(rx, 340, '"000317"', role="mono", size=24, fill=GREEN)
    fig.check(rx + 4, 364, color=GREEN)
    fig.note(rx + 28, 378, "join matches", size=21, fill=GREEN)
    return fig


@figure("blog/excel-count-vs-key")
def excel_count_vs_key() -> Figure:
    fig = Figure(
        "blog/excel-count-vs-key",
        W,
        400,
        "If a conversion duplicates line L-002 in place of L-003, the output still has three rows, so Assert Row "
        "Count with both bounds at 3 passes. Assert Unique on line_id finds the two L-002 rows and stops the run.",
    )
    fig.heading(LEFT, 56, "A duplicated key can keep the row count right")
    cols = ["line_id", "store_code", "units"]
    rows = [["L-001", "000317", 2], ["L-002", "000042", 1], ["L-002", "000042", 1]]
    tw, th, _ = fig.table_size(cols, rows)
    y = 150
    fig.note(LEFT, y - 12, "a bad conversion: L-003 is missing", size=22, fill=INK_SOFT)
    fig.table(LEFT, y, cols, rows, cell_styles={(1, 0): {"fill": MARKER}, (2, 0): {"fill": MARKER}})
    nx = 470
    _, _, nw, nh = fig.node(nx, 110, "Assert Row Count", "Min rows 3 · Max rows 3", kind="check")
    _, _, nw2, nh2 = fig.node(nx, 260, "Assert Unique", "Columns: line_id", kind="check")
    fig.arrow([(LEFT + tw + 14, y + 40), (nx - 40, 145), (nx - 12, 141)], stroke=INK_SOFT)
    fig.arrow([(LEFT + tw + 14, y + th - 30), (nx - 40, 288), (nx - 12, 291)], stroke=INK_SOFT)
    rx = nx + max(nw, nw2) + 40
    fig.note(rx, 136, ["passes: 3 rows", "as expected"], size=22, fill=RED)
    fig.note(rx, 286, ["stops the run:", "2 duplicate rows"], size=22, fill=GREEN)
    fig.check(rx - 30, 272, color=GREEN)
    return fig


# --------------------------------------------------------------------------
# Local-first
# --------------------------------------------------------------------------


@figure("blog/local-first-data-path")
def local_first_data_path() -> Figure:
    fig = Figure(
        "blog/local-first-data-path",
        W,
        520,
        "With a hosted tool, your files, app state and credentials are uploaded to the vendor's servers. With "
        "Ciaren, the browser talks to a server on 127.0.0.1, flows and run history stay in a local SQLite file, "
        "data stays in a local folder, secrets stay in an environment variable, the OS keychain or a file, and a remote database or bucket is only read when you add a connection.",
    )
    fig.heading(LEFT, 56, "Where your data goes before the first step runs")
    # hosted
    region(fig, LEFT, 96, 410, 390, "hosted tool")
    fig.node(LEFT + 30, 150, "Your laptop", "customers.csv", kind="input", w=170)
    fig.node(LEFT + 30, 380, "Your browser", "the editor", kind="input", w=170)
    fig.box(LEFT + 250, 220, 140, 150, r=14, fill=RED_SOFT, stroke=INK, width=1.6)
    fig.text(LEFT + 264, 250, "Vendor cloud", role="sans", size=14, weight=650)
    for i, line in enumerate(["your data", "flows and runs", "credentials"]):
        fig.text(LEFT + 264, 278 + i * 22, line, role="sans", size=13, fill=INK_SOFT)
    fig.arrow([(LEFT + 205, 181), (LEFT + 236, 200), (LEFT + 262, 214)], stroke=RED)
    fig.note(LEFT + 210, 168, "upload", size=21, fill=RED)
    fig.arrow([(LEFT + 262, 376), (LEFT + 232, 398), (LEFT + 205, 410)], stroke=INK_SOFT)
    # local
    lx = 506
    region(fig, lx, 96, 430, 390, "Ciaren on your machine", color=GREEN)
    fig.node(lx + 30, 150, "Browser", "the editor", kind="input", w=150)
    fig.node(lx + 236, 150, "ciaren serve", "127.0.0.1:8055", kind="transform", w=168)
    fig.arrow([(lx + 186, 181), (lx + 226, 181)], stroke=INK_SOFT)
    fig.box(lx + 30, 262, 374, 92, r=12, fill=GREEN_SOFT, stroke=INK, width=1.5)
    fig.text(lx + 48, 292, "ciaren.db", role="mono", size=13.5)
    fig.text(lx + 160, 292, "flows, runs, connections", role="sans", size=13, fill=INK_SOFT)
    fig.text(lx + 48, 318, ".data/", role="mono", size=13.5)
    fig.text(lx + 160, 318, "uploads, outputs, previews", role="sans", size=13, fill=INK_SOFT)
    fig.text(lx + 48, 342, "secrets", role="mono", size=13.5)
    fig.text(lx + 160, 342, "env var, keychain or file", role="sans", size=13, fill=INK_SOFT)
    fig.arrow([(lx + 320, 220), (lx + 320, 254)], stroke=INK_SOFT)
    fig.box(lx + 30, 396, 374, 66, r=12, stroke=INK_FAINT, width=1.4, double=False, dash="5 5")
    fig.text(lx + 48, 424, "Postgres, S3, a REST API", role="sans", size=13.5, weight=600, fill=INK_SOFT)
    fig.text(lx + 48, 446, "only through a connection you add", role="sans", size=13, fill=INK_SOFT)
    return fig


@figure("blog/local-first-origin-check")
def local_first_origin_check() -> Figure:
    fig = Figure(
        "blog/local-first-origin-check",
        W,
        420,
        "Any page open in your browser can send a POST to 127.0.0.1. Without an API token, Ciaren accepts "
        "state-changing /api requests from a local or configured origin and from clients that send no Origin header, "
        "such as curl, and refuses a request whose Origin is another site with 403.",
    )
    fig.heading(LEFT, 56, "A page in another tab can reach localhost")
    sx = 700
    fig.box(sx, 150, 236, 170, r=14, fill=VIOLET_SOFT, stroke=INK, width=1.6)
    fig.text(sx + 20, 182, "Ciaren API", role="sans", size=15, weight=650)
    fig.text(sx + 20, 206, "127.0.0.1:8055", role="mono", size=12.5, fill=INK_SOFT)
    fig.text(sx + 20, 246, "POST /api/... checks", role="sans", size=13, fill=INK_SOFT)
    fig.text(sx + 20, 268, "the Origin header", role="sans", size=13, fill=INK_SOFT)
    callers = [
        (120, "Ciaren tab", "Origin: http://localhost:8055", GREEN, "accepted"),
        (220, "curl or a script", "no Origin header", GREEN, "accepted"),
        (320, "another site's tab", "Origin: https://evil.example", RED, "403 refused"),
    ]
    for y, who, origin, color, verdict in callers:
        fig.node(LEFT, y, who, origin, kind="input", w=300)
        start, end = (LEFT + 312, y + 31), (sx - 12, 235 + (y - 220) * 0.35)
        fig.arrow([start, end], stroke=color)
        nx = LEFT + 390
        line_y = start[1] + (end[1] - start[1]) * (nx - start[0]) / (end[0] - start[0])
        fig.note(nx, line_y + (32 if end[1] < start[1] else -14), verdict, size=22, fill=color)
    fig.note(sx, 356, ["with CIAREN_API_TOKEN set,", "the token does this job"], size=20, fill=INK_SOFT)
    return fig


# --------------------------------------------------------------------------
# Exported Python
# --------------------------------------------------------------------------


EXPORT_LINES = [
    "df_orders = pd.read_csv('orders.csv')",
    "df_customers = pd.read_csv('customers.csv')",
    "df_orders = df_orders.loc[lambda _d: _d['status'] == 'completed']",
    "",
    "df_1 = (",
    "    df_orders.merge(df_customers, on='customer_id', how='left')",
    "    .groupby('region')",
    "    .agg({'amount': 'sum'})",
    "    .reset_index()",
    "    .rename(columns={'amount': 'revenue'})",
    "    .sort_values('revenue', ascending=False)",
    ")",
    "",
    "df_1.to_csv('revenue_by_region.csv', index=False)",
]


@figure("blog/export-line-by-line")
def export_line_by_line() -> Figure:
    fig = Figure(
        "blog/export-line-by-line",
        W,
        610,
        "Each node in the orders flow maps to one line or one chained call of the exported pandas script: two "
        "reads, a filter, a merge, groupby with agg and reset_index, rename, sort_values and to_csv. The "
        "reset_index call is pandas-only because groupby moves the key into the index.",
    )
    fig.heading(LEFT, 56, "Every node is a line you can point to")
    cx, cy, line_h = 400, 104, 26
    code_panel(fig, cx, cy, EXPORT_LINES, w=RIGHT - cx, line_h=line_h, size=12.5, marks={8: MARKER})
    nodes = [
        ("File Input · orders", "input", 0),
        ("File Input · customers", "input", 1),
        ("Filter Rows", "clean", 2),
        ("Join / Merge", "transform", 5),
        ("Group By Aggregate", "transform", 6),
        ("Rename Columns", "transform", 9),
        ("Sort Rows", "clean", 10),
        ("File Output", "output", 13),
    ]
    pitch = 52
    for k, (label, kind, line) in enumerate(nodes):
        ny = 100 + k * pitch
        _, _, nw, nh = fig.node(LEFT, ny, label, kind=kind, w=232)
        ty = code_line_y(cy, line, line_h=line_h)
        fig.arrow(
            [(LEFT + nw + 10, ny + nh / 2), (cx - 12, ty)], stroke=VIOLET if line == 6 else INK_SOFT, width=1.5, head=9
        )
    fig.note(
        LEFT,
        100 + 8 * pitch + 34,
        [
            "Group By Aggregate becomes three chained calls. The marked reset_index() is pandas only:",
            "pandas moves region into the index, and the Polars export keeps it as a column.",
        ],
        size=21,
        fill=VIOLET,
    )
    return fig


@figure("blog/vendor-format-vs-script")
def vendor_format_vs_script() -> Figure:
    fig = Figure(
        "blog/vendor-format-vs-script",
        W,
        400,
        "A workflow saved in a visual tool's own format runs only where that tool and its engine are installed. A Ciaren flow can be "
        "exported as a pandas or Polars script that runs with the dataframe library alone, so the logic still "
        "runs after Ciaren is uninstalled.",
    )
    fig.heading(LEFT, 56, "What still runs after you uninstall the tool")
    rows = [
        (
            130,
            "typical visual tool",
            "pipeline.wf",
            "vendor engine",
            "the tool installed",
            RED,
            RED_SOFT,
            "logic runs only inside the product",
        ),
        (
            270,
            "Ciaren",
            "revenue.py",
            "python + polars",
            "pip install polars",
            GREEN,
            GREEN_SOFT,
            "logic runs anywhere Python runs",
        ),
    ]
    for y, label, artifact, runner, needs, color, soft, verdict in rows:
        fig.note(LEFT, y - 14, label, size=23, fill=color)
        is_vendor = artifact.endswith(".wf")
        fig.node(
            LEFT,
            y,
            artifact,
            "saved workflow" if is_vendor else "exported script",
            kind="input" if is_vendor else "output",
            w=190,
        )
        fig.arrow([(LEFT + 202, y + 31), (300, y + 31)], stroke=INK_SOFT)
        fig.box(312, y, 210, 62, r=11, fill=soft, stroke=INK, width=1.5)
        fig.text(330, y + 26, runner, role="sans", size=15, weight=650)
        fig.text(330, y + 46, needs, role="mono", size=12.5, fill=INK_SOFT)
        fig.arrow([(534, y + 31), (600, y + 31)], stroke=INK_SOFT)
        fig.text(612, y + 37, "output", role="sans", size=15, weight=650)
        fig.note(LEFT + 210, y + 98, verdict, size=22, fill=color)
    fig.check(700, 270 + 18, color=GREEN)
    fig.cross(700, 130 + 18, color=RED)
    return fig


# --------------------------------------------------------------------------
# Architecture
# --------------------------------------------------------------------------


@figure("blog/node-three-jobs")
def node_three_jobs() -> Figure:
    fig = Figure(
        "blog/node-three-jobs",
        W,
        510,
        "A transformation node is one class. execute calls the active engine backend, while to_python_code and "
        "to_polars_code return the pandas and Polars source for the same step. The equivalence tests run each "
        "emitted line on the same input and compare its frame with the engine's result.",
    )
    fig.heading(LEFT, 56, "One node class, three jobs, one test that ties them together")
    cls = [
        "class FilterRowsTransformation:",
        "    def execute(...)",
        "    def to_python_code(...)",
        "    def to_polars_code(...)",
    ]
    cy, line_h = 170, 30
    code_panel(fig, LEFT, cy, cls, w=290, line_h=line_h, size=13)
    ox = 440
    outs = [
        (110, "engine.filter_rows(df, 'status', '==', 'completed')", "pandas or Polars backend, chosen per run"),
        (230, "df.loc[lambda _d: _d['status'] == 'completed']", "pandas export"),
        (350, "df.filter(pl.col('status') == 'completed')", "Polars export"),
    ]
    for k, (y, src, caption) in enumerate(outs):
        code_panel(fig, ox, y, [src], w=RIGHT - ox, size=12.5)
        fig.text(ox, y + 58, caption, role="sans", size=13, fill=INK_SOFT)
        fig.arrow([(LEFT + 296, code_line_y(cy, k + 1, line_h=line_h)), (ox - 12, y + 22)], stroke=INK_SOFT, width=1.5)
    label = "equivalence test: exec each export line, compare with execute"
    lw = fig.measure(label, role="sans", size=13.5, weight=600)
    fig.box(ox, 440, lw + 32, 42, r=10, fill=VIOLET_SOFT, stroke=VIOLET, width=1.4, double=False)
    fig.text(ox + 16, 466, label, role="sans", size=13.5, weight=600, fill=VIOLET)
    fig.note(
        LEFT,
        340,
        ["run the emitted line on the", "same input as execute,", "then compare the frames"],
        size=21,
        fill=VIOLET,
    )
    return fig
