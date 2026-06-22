// A small set of project accent colours. Purple is the default/brand; the rest
// give projects a distinguishable but harmonious identity on their cards.

export interface ProjectColorTheme {
  key: string;
  label: string;
  /** Solid avatar/badge background. */
  badge: string;
  /** Soft tinted surface for the card header. */
  tint: string;
  /** Small accent dot / ring. */
  dot: string;
}

export const PROJECT_COLORS: ProjectColorTheme[] = [
  { key: "violet", label: "Violet", badge: "bg-brand-600", tint: "bg-brand-50", dot: "bg-brand-600" },
  { key: "indigo", label: "Indigo", badge: "bg-indigo-500", tint: "bg-indigo-50", dot: "bg-indigo-500" },
  { key: "blue", label: "Blue", badge: "bg-sky-500", tint: "bg-sky-50", dot: "bg-sky-500" },
  { key: "emerald", label: "Emerald", badge: "bg-emerald-500", tint: "bg-emerald-50", dot: "bg-emerald-500" },
  { key: "amber", label: "Amber", badge: "bg-amber-500", tint: "bg-amber-50", dot: "bg-amber-500" },
  { key: "rose", label: "Rose", badge: "bg-rose-500", tint: "bg-rose-50", dot: "bg-rose-500" },
];

const BY_KEY = new Map(PROJECT_COLORS.map((c) => [c.key, c]));

export function projectColor(key: string | null | undefined): ProjectColorTheme {
  return (key && BY_KEY.get(key)) || PROJECT_COLORS[0];
}
