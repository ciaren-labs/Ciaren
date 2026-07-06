// Theme-aware colour tokens for the preview charts. Both palettes were
// validated with the dataviz six-checks validator against the app's real
// surfaces (light #fcfbfd, dark #130e1b): lightness band, chroma floor,
// CVD adjacent-pair separation (worst ΔE 13.3 light / 13.4 dark) and
// mark-vs-surface contrast. The slot ORDER is the CVD-safety mechanism —
// assign series colours in sequence, never cycle past the 8 slots.
import { useThemeStore } from "@/stores/themeStore";

export interface ChartTheme {
  /** Colour of the panel the chart sits on — used for gaps and marker rings. */
  surface: string;
  /** Hairline gridlines/axis rules, one step off the surface. */
  grid: string;
  /** Axis tick + legend text (muted ink). */
  axis: string;
  /** Primary ink for tooltip text and labels. */
  ink: string;
  tooltipBg: string;
  tooltipBorder: string;
  /** Wash shown under the hovered bar/category. */
  cursor: string;
  /** Reserved for "Other" buckets — deliberately grey, never a series slot. */
  neutral: string;
  /** Categorical slots, fixed order (slot 1 = brand violet). */
  series: string[];
  /** Diverging poles + midpoint for the correlation heatmap. */
  divergingNeg: string;
  divergingMid: string;
  divergingPos: string;
}

const LIGHT: ChartTheme = {
  surface: "#fcfbfd",
  grid: "#e8e4ef",
  axis: "#726783",
  ink: "#1d1528",
  tooltipBg: "#ffffff",
  tooltipBorder: "#e8e3ee",
  cursor: "#e8e4ef66",
  neutral: "#aaa4b8",
  series: ["#7c3aed", "#1baf7a", "#eda100", "#2a78d6", "#e34948", "#008300", "#e87ba4", "#eb6834"],
  divergingNeg: "#2a78d6",
  divergingMid: "#f1eff4",
  divergingPos: "#e34948",
};

const DARK: ChartTheme = {
  surface: "#130e1b",
  grid: "#2b2438",
  axis: "#a196b0",
  ink: "#f4f1f7",
  tooltipBg: "#1b1424",
  tooltipBorder: "#362d43",
  cursor: "#2b243866",
  neutral: "#5f5870",
  series: ["#9085e9", "#199e70", "#c98500", "#3987e5", "#e66767", "#008300", "#d55181", "#d95926"],
  divergingNeg: "#3987e5",
  divergingMid: "#332d40",
  divergingPos: "#e66767",
};

export function getChartTheme(theme: "light" | "dark"): ChartTheme {
  return theme === "dark" ? DARK : LIGHT;
}

/** Reactive chart tokens for the current app theme. */
export function useChartTheme(): ChartTheme {
  const theme = useThemeStore((s) => s.theme);
  return getChartTheme(theme);
}

/** Linear sRGB mix of two hex colours; t in [0, 1] moves from `a` to `b`. */
export function mixHex(a: string, b: string, t: number): string {
  const pa = parseHex(a);
  const pb = parseHex(b);
  const ch = (i: number) => Math.round(pa[i] + (pb[i] - pa[i]) * t);
  return `#${[ch(0), ch(1), ch(2)].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** Pick a readable text colour (white or near-black) for the given fill. */
export function inkForFill(fill: string): string {
  const [r, g, b] = parseHex(fill);
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const luminance = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  return luminance > 0.35 ? "#1d1528" : "#f4f1f7";
}

function parseHex(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}
