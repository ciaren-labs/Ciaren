"""Hand-drawn SVG primitives for the Ciaren documentation illustrations.

Every figure is a "field-notes" card: warm paper, ink outlines with a gentle
hand-drawn wobble, marker highlights and handwritten annotations. Fonts are
subset to the glyphs a figure uses and embedded, so a figure renders the same in
VitePress, on ciaren.com and in a raw file viewer. Randomness is seeded by the
figure name, so rebuilding an unchanged figure produces identical bytes.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import random
import urllib.request
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

PAPER = "#FBF8F2"
PAPER_EDGE = "#EAE3D6"
GRID = "#E6DECF"
INK = "#2A2733"
INK_SOFT = "#6B6577"
INK_FAINT = "#A39DAE"

VIOLET = "#7B3AED"  # Ciaren brand-600
VIOLET_SOFT = "#E9DDFC"
MARKER = "#FFD84D"  # highlighter yellow
MARKER_SOFT = "#FFF0A8"
RED = "#D64545"
RED_SOFT = "#FBDADA"
GREEN = "#2E8B62"
GREEN_SOFT = "#D5EEDF"
BLUE = "#2F6FD0"
BLUE_SOFT = "#DCE8FA"
AMBER = "#C9851B"
AMBER_SOFT = "#FBEBCB"
PINK = "#C2418C"
PINK_SOFT = "#F7DCEB"

# Node categories mirror the colors of <FlowPipeline> in the docs.
KIND = {
    "input": (BLUE, BLUE_SOFT),
    "clean": (AMBER, AMBER_SOFT),
    "transform": (VIOLET, VIOLET_SOFT),
    "output": (GREEN, GREEN_SOFT),
    "ml": (PINK, PINK_SOFT),
    "check": (RED, RED_SOFT),
}

# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

FONT_DIR = Path(__file__).with_name(".fonts")
# google/fonts pinned to one commit; the digests below must match it.
_GF = "https://raw.githubusercontent.com/google/fonts/5026800714d07231937d92eb4cceabf06e05d74e/ofl"
FONT_SOURCES = {
    "hand": (
        f"{_GF}/caveat/Caveat%5Bwght%5D.ttf",
        "Caveat[wght].ttf",
        "0bdb6b660482d31531b3945849fba5916b3ef8695da7024a9e6b9ee3c4157988",
    ),
    "sans": (
        f"{_GF}/inter/Inter%5Bopsz,wght%5D.ttf",
        "Inter[opsz,wght].ttf",
        "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031",
    ),
    "mono": (
        f"{_GF}/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
        "JetBrainsMono[wght].ttf",
        "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda",
    ),
}
FAMILY = {"hand": "CiarenHand", "sans": "CiarenSans", "mono": "CiarenMono"}


def _font_path(role: str) -> Path:
    url, name, digest = FONT_SOURCES[role]
    path = FONT_DIR / name
    if not path.exists():
        FONT_DIR.mkdir(exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - pinned digest below
            data = response.read()
        path.write_bytes(data)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        path.unlink()
        raise RuntimeError(f"{name}: sha256 {actual} does not match the pinned {digest}")
    return path


_STATIC: dict[tuple[str, int], TTFont] = {}


def static_font(role: str, weight: int) -> TTFont:
    """Return the variable font pinned to one weight (cached)."""
    key = (role, weight)
    if key not in _STATIC:
        font = TTFont(_font_path(role))
        axes = {"wght": weight}
        if role == "sans":
            axes["opsz"] = 14
        _STATIC[key] = instancer.instantiateVariableFont(font, axes)
    return _STATIC[key]


def text_width(text: str, role: str, size: float, weight: int) -> float:
    font = static_font(role, weight)
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    upm = font["head"].unitsPerEm
    total = 0
    for char in text:
        glyph = cmap.get(ord(char)) or cmap.get(ord("?"))
        total += hmtx[glyph][0]
    return total * size / upm


def _subset_woff(role: str, weight: int, chars: set[str]) -> str:
    font = static_font(role, weight)
    buffer = io.BytesIO()
    font.save(buffer)
    buffer.seek(0)
    copy = TTFont(buffer, recalcTimestamp=False)
    # Fixed timestamps keep rebuilt SVGs byte-identical.
    copy["head"].created = copy["head"].modified = 0
    options = subset.Options()
    options.flavor = "woff"
    options.layout_features = ["kern"]
    options.name_IDs = []
    options.hinting = False
    options.desubroutinize = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(copy)
    out = io.BytesIO()
    copy.flavor = "woff"
    copy.save(out)
    return base64.b64encode(out.getvalue()).decode("ascii")


# --------------------------------------------------------------------------
# Rough geometry
# --------------------------------------------------------------------------


def _f(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _smooth_closed(points: list[tuple[float, float]]) -> str:
    """Catmull-Rom spline through closed points, as a cubic Bezier path."""
    n = len(points)
    parts = [f"M{_f(points[0][0])} {_f(points[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = (points[(i + k) % n] for k in (-1, 0, 1, 2))
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        parts.append(f"C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(p2[0])} {_f(p2[1])}")
    return "".join(parts) + "Z"


def _smooth_open(points: list[tuple[float, float]]) -> str:
    parts = [f"M{_f(points[0][0])} {_f(points[0][1])}"]
    n = len(points)
    for i in range(n - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        parts.append(f"C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(p2[0])} {_f(p2[1])}")
    return "".join(parts)


def _round_rect_outline(x: float, y: float, w: float, h: float, r: float, step: float = 14):
    """Points along a rounded rectangle, clockwise, roughly `step` apart."""
    r = max(0.0, min(r, w / 2, h / 2))
    pts: list[tuple[float, float]] = []

    def edge(ax, ay, bx, by):
        length = math.hypot(bx - ax, by - ay)
        count = max(1, int(length / step))
        for k in range(count):
            t = k / count
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))

    def corner(cx, cy, start):
        if r == 0:
            pts.append((cx, cy))
            return
        for k in range(4):
            a = math.radians(start + 90 * k / 4)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    edge(x + r, y, x + w - r, y)
    corner(x + w - r, y + r, -90)
    edge(x + w, y + r, x + w, y + h - r)
    corner(x + w - r, y + h - r, 0)
    edge(x + w - r, y + h, x + r, y + h)
    corner(x + r, y + h - r, 90)
    edge(x, y + h - r, x, y + r)
    corner(x + r, y + r, 180)
    return pts


class Wobble:
    """Low-frequency noise: a sum of sines with random phases."""

    def __init__(self, rng: random.Random, amplitude: float):
        self.terms = [
            (rng.uniform(0.6, 1.0) * amplitude / (k + 1), k + 1, rng.uniform(0, 2 * math.pi)) for k in range(3)
        ]

    def __call__(self, t: float) -> float:
        return sum(a * math.sin(2 * math.pi * f * t + p) for a, f, p in self.terms)


@dataclass
class Figure:
    name: str
    width: int
    height: int
    title: str
    rough: float = 1.0
    body: list[str] = field(default_factory=list)
    _chars: dict[tuple[str, int], set[str]] = field(default_factory=dict)
    _owner: str | None = None
    _blocks: list[tuple[str | None, float, float, float, float, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.name)

    # -- layout checks ---------------------------------------------------

    def _open(self, label, x0, y0, x1, y1):
        self._block(x0, y0, x1, y1, label)
        self._owner = label

    def _block(self, x0, y0, x1, y1, label):
        self._blocks.append((self._owner, x0, y0, x1, y1, label))

    def problems(self) -> list[str]:
        """Overlapping labels/blocks and content outside the card."""
        found = []
        margin = 10
        for owner, x0, y0, x1, y1, label in self._blocks:
            if x0 < margin or y0 < margin or x1 > self.width - margin or y1 > self.height - margin:
                found.append(f"outside the card: {label!r} ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")
        items = self._blocks
        for i in range(len(items)):
            oi, ax0, ay0, ax1, ay1, la = items[i]
            for j in range(i + 1, len(items)):
                oj, bx0, by0, bx1, by1, lb = items[j]
                if oi is not None and oi == oj:
                    continue
                if (oi is not None and lb == oi) or (oj is not None and la == oj):
                    continue
                if min(ax1, bx1) - max(ax0, bx0) > 1.5 and min(ay1, by1) - max(ay0, by0) > 1.5:
                    found.append(f"overlap: {la!r} and {lb!r}")
        return found

    # -- low level -------------------------------------------------------

    def add(self, element: str) -> None:
        self.body.append(element)

    def _jitter_closed(self, pts, amount):
        n = len(pts)
        wob_x, wob_y = Wobble(self.rng, amount), Wobble(self.rng, amount)
        return [(px + wob_x(i / n), py + wob_y(i / n)) for i, (px, py) in enumerate(pts)]

    # -- shapes ----------------------------------------------------------

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        r: float = 10,
        stroke: str = INK,
        fill: str | None = None,
        width: float = 1.7,
        double: bool = True,
        fill_offset: float = 3,
        dash: str | None = None,
        opacity: float = 1.0,
    ) -> None:
        """A hand-drawn rounded rectangle with an optional, slightly offset fill."""
        base = _round_rect_outline(x, y, w, h, r)
        amount = 1.3 * self.rough
        if fill:
            shifted = [(px + fill_offset * 0.6, py + fill_offset) for px, py in base]
            self.add(
                f'<path d="{_smooth_closed(self._jitter_closed(shifted, amount * 1.6))}" '
                f'fill="{fill}" opacity="{opacity}"/>'
            )
        passes = 2 if double else 1
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        for k in range(passes):
            path = _smooth_closed(self._jitter_closed(base, amount))
            alpha = 1 if k == 0 else 0.45
            self.add(
                f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="{_f(width)}" '
                f'stroke-linejoin="round" stroke-linecap="round" opacity="{alpha}"{extra}/>'
            )

    def ellipse(self, cx, cy, rx, ry, *, stroke=INK, fill=None, width=1.7) -> None:
        pts = [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in (2 * math.pi * k / 28 for k in range(28))]
        if fill:
            self.add(
                f'<path d="{_smooth_closed(self._jitter_closed([(px + 2, py + 2.5) for px, py in pts], 1.8))}" fill="{fill}"/>'
            )
        for k in range(2):
            self.add(
                f'<path d="{_smooth_closed(self._jitter_closed(pts, 1.2 * self.rough))}" fill="none" '
                f'stroke="{stroke}" stroke-width="{_f(width)}" opacity="{1 if k == 0 else 0.45}"/>'
            )

    def line(self, x1, y1, x2, y2, *, stroke=INK, width=1.7, double=True, dash=None) -> None:
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = (-(y2 - y1) / length, (x2 - x1) / length) if length else (0, 0)
        for k in range(2 if double else 1):
            bow = self.rng.uniform(-1, 1) * min(length / 90, 2.2) * self.rough
            j = lambda: self.rng.uniform(-0.9, 0.9) * self.rough  # noqa: E731
            pts = []
            for t in (0, 0.33, 0.66, 1):
                curve = math.sin(math.pi * t) * bow
                pts.append((x1 + (x2 - x1) * t + nx * curve + j(), y1 + (y2 - y1) * t + ny * curve + j()))
            extra = f' stroke-dasharray="{dash}"' if dash else ""
            self.add(
                f'<path d="{_smooth_open(pts)}" fill="none" stroke="{stroke}" stroke-width="{_f(width)}" '
                f'stroke-linecap="round" opacity="{1 if k == 0 else 0.4}"{extra}/>'
            )

    def arrow(
        self,
        points: list[tuple[float, float]],
        *,
        stroke: str = INK,
        width: float = 1.8,
        head: float = 11,
        dash: str | None = None,
    ) -> None:
        """A curved hand-drawn arrow through `points`, with an open arrowhead."""
        jittered = (
            [points[0]]
            + [
                (px + self.rng.uniform(-1, 1) * self.rough, py + self.rng.uniform(-1, 1) * self.rough)
                for px, py in points[1:-1]
            ]
            + [points[-1]]
        )
        if len(jittered) == 2:
            (ax, ay), (bx, by) = jittered
            mid = ((ax + bx) / 2, (ay + by) / 2)
            length = math.hypot(bx - ax, by - ay) or 1
            bow = self.rng.uniform(-1, 1) * min(length / 40, 3)
            mid = (mid[0] - (by - ay) / length * bow, mid[1] + (bx - ax) / length * bow)
            jittered = [jittered[0], mid, jittered[1]]
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<path d="{_smooth_open(jittered)}" fill="none" stroke="{stroke}" stroke-width="{_f(width)}" '
            f'stroke-linecap="round"{extra}/>'
        )
        (px, py), (tx, ty) = jittered[-2], jittered[-1]
        angle = math.atan2(ty - py, tx - px)
        for side in (-1, 1):
            a = angle + math.pi + side * math.radians(28 + self.rng.uniform(-4, 4))
            hx, hy = tx + head * math.cos(a), ty + head * math.sin(a)
            self.add(
                f'<path d="M{_f(hx)} {_f(hy)}Q{_f((hx + tx) / 2 + side)} {_f((hy + ty) / 2 - side)} {_f(tx)} {_f(ty)}" '
                f'fill="none" stroke="{stroke}" stroke-width="{_f(width)}" stroke-linecap="round"/>'
            )

    def marker(self, x, y, w, h, *, color=MARKER, opacity=0.75) -> None:
        """A highlighter swipe behind text: slanted ends, uneven edges."""
        top = Wobble(self.rng, 1.4)
        bottom = Wobble(self.rng, 1.4)
        steps = max(4, int(w / 18))
        upper = [(x + w * k / steps, y + top(k / steps)) for k in range(steps + 1)]
        lower = [(x + w * k / steps, y + h + bottom(k / steps)) for k in range(steps, -1, -1)]
        upper[0] = (upper[0][0] + 3, upper[0][1])
        lower[0] = (lower[0][0] + 2, lower[0][1])
        d = "M" + "L".join(f"{_f(px)} {_f(py)}" for px, py in upper + lower) + "Z"
        self.add(
            f'<path d="{d}" fill="{color}" opacity="{opacity}" stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="round"/>'
        )

    def strike(self, x, y, w, *, color=RED, width=2.2) -> None:
        self.line(
            x,
            y + self.rng.uniform(-1, 1),
            x + w,
            y + self.rng.uniform(-1.5, 1.5),
            stroke=color,
            width=width,
            double=False,
        )

    def check(self, x, y, *, size=16, color=GREEN, width=2.8) -> None:
        s = size
        pts = [(x, y + s * 0.5), (x + s * 0.36, y + s * 0.88), (x + s, y)]
        self.add(
            f'<path d="{_smooth_open(pts[:2])}L{_f(pts[2][0])} {_f(pts[2][1])}" fill="none" stroke="{color}" '
            f'stroke-width="{_f(width)}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def cross(self, x, y, *, size=14, color=RED, width=2.6) -> None:
        self.line(x, y, x + size, y + size, stroke=color, width=width, double=False)
        self.line(x + size, y, x, y + size, stroke=color, width=width, double=False)

    # -- text ------------------------------------------------------------

    def text(
        self,
        x: float,
        y: float,
        content: str,
        *,
        role: str = "sans",
        size: float = 15,
        weight: int | None = None,
        fill: str = INK,
        anchor: str = "start",
        rotate: float = 0,
        opacity: float = 1.0,
    ) -> float:
        """Draw one line of text; return its width."""
        weight = weight or {"hand": 600, "sans": 500, "mono": 400}[role]
        self._chars.setdefault((role, weight), set()).update(content)
        width = text_width(content, role, size, weight)
        if self._owner is None and not rotate:
            x0 = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
            self._block(x0, y - size * 0.72, x0 + width, y + size * 0.22, content)
        transform = f' transform="rotate({_f(rotate)} {_f(x)} {_f(y)})"' if rotate else ""
        extra = f' opacity="{opacity}"' if opacity != 1 else ""
        self.add(
            f'<text xml:space="preserve" x="{_f(x)}" y="{_f(y)}" font-family="{FAMILY[role]}" font-size="{_f(size)}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{transform}{extra}>'
            f"{escape(content, quote=False)}</text>"
        )
        return width

    def measure(self, content: str, *, role="sans", size=15, weight=None) -> float:
        weight = weight or {"hand": 600, "sans": 500, "mono": 400}[role]
        return text_width(content, role, size, weight)

    def note(self, x, y, lines: list[str] | str, *, size=24, fill=INK_SOFT, anchor="start", rotate=0, leading=1.05):
        """Handwritten annotation, one or more lines."""
        if isinstance(lines, str):
            lines = [lines]
        for i, line in enumerate(lines):
            self.text(x, y + i * size * leading, line, role="hand", size=size, fill=fill, anchor=anchor, rotate=rotate)

    # -- composites ------------------------------------------------------

    def node(
        self,
        x: float,
        y: float,
        label: str,
        detail: str = "",
        *,
        kind: str = "transform",
        w: float | None = None,
        h: float = 62,
    ) -> tuple[float, float, float, float]:
        """A Ciaren node card: colored edge tab, bold label, mono detail."""
        color, soft = KIND[kind]
        lw = self.measure(label, role="sans", size=15, weight=650)
        dw = self.measure(detail, role="mono", size=12.5) if detail else 0
        w = w or max(lw, dw) + 46
        if not detail:
            h = min(h, 46)
        self._open(f"node {label}", x, y, x + w, y + h)
        self.box(x, y, w, h, r=11, fill=soft, stroke=INK)
        self.add(
            f'<path d="{_smooth_open([(x + 11, y + 9), (x + 11.6, y + h / 2), (x + 11, y + h - 9)])}" '
            f'stroke="{color}" stroke-width="5" stroke-linecap="round" fill="none"/>'
        )
        if detail:
            self.text(x + 25, y + 26, label, size=15, weight=650)
            self.text(x + 25, y + 46, detail, role="mono", size=12.5, fill=INK_SOFT)
        else:
            self.text(x + 25, y + h / 2 + 5.5, label, size=15, weight=650)
        self._owner = None
        return x, y, w, h

    def table(
        self,
        x: float,
        y: float,
        columns: list[str],
        rows: list[list[object]],
        *,
        widths: list[float] | None = None,
        row_h: float = 30,
        size: float = 13.5,
        header_fill: str = "#F1EBDF",
        row_styles: dict[int, dict] | None = None,
        cell_styles: dict[tuple[int, int], dict] | None = None,
        col_styles: dict[int, dict] | None = None,
        pad: float = 12,
    ) -> tuple[float, float]:
        """A hand-ruled data table. Returns (width, height).

        row_styles / cell_styles / col_styles accept keys:
          fill   - marker color behind the row/cell/column
          strike - True to strike the row through (rows only)
          color  - text color
          weight - text weight
        """
        row_styles = row_styles or {}
        cell_styles = cell_styles or {}
        col_styles = col_styles or {}
        cells = [[_cell(v) for v in row] for row in rows]
        if widths is None:
            widths = self.table_size(columns, rows, size=size, pad=pad, row_h=row_h)[2]
        total_w = sum(widths)
        total_h = row_h * (len(rows) + 1)
        self._open(f"table {columns[0]}@{x:.0f},{y:.0f}", x, y, x + total_w, y + total_h)
        self.box(x, y, total_w, row_h, r=6, fill=header_fill, stroke=INK, width=0, double=False, fill_offset=0)
        # markers first so text sits on top
        for c, style in col_styles.items():
            if "fill" in style:
                cx = x + sum(widths[:c])
                self.marker(
                    cx + 4, y + row_h + 4, widths[c] - 8, total_h - row_h - 8, color=style["fill"], opacity=0.55
                )
        for r, style in row_styles.items():
            if "fill" in style:
                self.marker(
                    x + 3,
                    y + row_h * (r + 1) + 5,
                    total_w - 6,
                    row_h - 10,
                    color=style["fill"],
                    opacity=style.get("opacity", 0.6),
                )
        for (r, c), style in cell_styles.items():
            if "fill" in style:
                cx = x + sum(widths[:c])
                self.marker(
                    cx + 4, y + row_h * (r + 1) + 5, widths[c] - 8, row_h - 10, color=style["fill"], opacity=0.7
                )
        self.box(x, y, total_w, total_h, r=8, stroke=INK, width=1.6)
        self.line(x + 2, y + row_h, x + total_w - 2, y + row_h, width=1.4, double=False)
        for r in range(1, len(rows)):
            self.line(
                x + 6,
                y + row_h * (r + 1),
                x + total_w - 6,
                y + row_h * (r + 1),
                stroke=INK_FAINT,
                width=0.9,
                double=False,
            )
        cx = x
        for c in range(len(columns) - 1):
            cx += widths[c]
            self.line(cx, y + 4, cx, y + total_h - 4, stroke=INK_FAINT, width=0.9, double=False)
        cx = x
        for c, col in enumerate(columns):
            self.text(cx + pad, y + row_h / 2 + 5, col, size=size - 0.5, weight=650)
            cx += widths[c]
        for r, row in enumerate(cells):
            style = row_styles.get(r, {})
            cy = y + row_h * (r + 1) + row_h / 2 + 4.6
            cx = x
            for c, value in enumerate(row):
                cs = {**col_styles.get(c, {}), **style, **cell_styles.get((r, c), {})}
                color = cs.get("color", INK_FAINT if value in ("null", "") else INK)
                shown = value if value != "" else " "
                if value == "null":
                    self.text(cx + pad, cy, "null", role="mono", size=size - 0.5, fill=color, weight=400)
                else:
                    self.text(cx + pad, cy, shown, role="mono", size=size, fill=color, weight=cs.get("weight", 400))
                cx += widths[c]
            if style.get("strike"):
                self.strike(x + 6, y + row_h * (r + 1) + row_h / 2, total_w - 12, color=style.get("strike_color", RED))
        self._owner = None
        return total_w, total_h

    def table_size(self, columns, rows, *, size=13.5, pad=12, row_h=30) -> tuple[float, float, list[float]]:
        cells = [[_cell(v) for v in row] for row in rows]
        widths = []
        for c, col in enumerate(columns):
            longest = max(
                [self.measure(col, role="sans", size=size - 0.5, weight=650)]
                + [self.measure(r[c], role="mono", size=size) for r in cells]
            )
            widths.append(longest + 2 * pad)
        return sum(widths), row_h * (len(rows) + 1), widths

    def pill(self, x, y, label, *, color=VIOLET, soft=VIOLET_SOFT, size=13, role="sans", weight=600) -> float:
        w = self.measure(label, role=role, size=size, weight=weight) + 22
        self._open(f"pill {label}", x, y, x + w, y + size + 13)
        self.box(
            x, y, w, size + 13, r=(size + 13) / 2, fill=soft, stroke=color, width=1.4, double=False, fill_offset=1.5
        )
        self.text(x + 11, y + size + 3.5, label, role=role, size=size, weight=weight, fill=color)
        self._owner = None
        return w

    def step(self, x0, x1, y, label, *, role="mono", size=12, color=VIOLET, soft=VIOLET_SOFT) -> None:
        """A horizontal arrow from x0 to x1 at height y, with a pill label centered above it."""
        w = self.measure(label, role=role, size=size, weight=500) + 22
        self.pill((x0 + x1) / 2 - w / 2, y - size - 27, label, role=role, size=size, weight=500, color=color, soft=soft)
        self.arrow([(x0, y), (x1, y)], stroke=INK_SOFT)

    def heading(self, x, y, content, *, size=30, color=INK) -> None:
        width = self.measure(content, role="hand", size=size, weight=700)
        self.marker(x - 6, y - size * 0.42, width + 12, size * 0.5, color=MARKER_SOFT, opacity=0.9)
        self.text(x, y, content, role="hand", size=size, weight=700, fill=color)

    # -- output ----------------------------------------------------------

    def render(self) -> str:
        faces = []
        for (role, weight), chars in sorted(self._chars.items()):
            data = _subset_woff(role, weight, chars | {" "})
            faces.append(
                f"@font-face{{font-family:{FAMILY[role]};font-weight:{weight};"
                f"src:url(data:font/woff;base64,{data}) format('woff')}}"
            )
        w, h = self.width, self.height
        dots = (
            '<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
            f'<circle cx="2" cy="2" r="1.1" fill="{GRID}"/></pattern>'
        )
        defs = dots
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-labelledby="t">'
            f'<title id="t">{escape(self.title)}</title>'
            f"<defs><style>{''.join(faces)}text{{font-kerning:normal}}</style>{defs}</defs>"
            f'<rect width="{w}" height="{h}" rx="18" fill="{PAPER}"/>'
            f'<rect width="{w}" height="{h}" rx="18" fill="url(#dots)"/>'
            f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="17.5" fill="none" stroke="{PAPER_EDGE}" stroke-width="1.5"/>'
            + "".join(self.body)
            + "</svg>\n"
        )


def _cell(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
