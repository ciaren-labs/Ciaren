import { useState } from "react";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";

export type SortDir = "asc" | "desc";
export interface SortState<K extends string> {
  key: K;
  dir: SortDir;
}

/** Sort state + a toggle that flips direction on the active column, or switches
 *  to a new column (starting ascending). Shared by every sortable table. */
export function useSort<K extends string>(initialKey: K, initialDir: SortDir = "asc") {
  const [sort, setSort] = useState<SortState<K>>({ key: initialKey, dir: initialDir });
  const toggle = (key: K) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  return { sort, toggle };
}

/** A `<th>` whose label is a sort toggle, with an up/down/neutral indicator. */
export function SortableTh<K extends string>({
  label,
  sortKey,
  sort,
  onSort,
  className,
}: {
  label: string;
  sortKey: K;
  sort: SortState<K>;
  onSort: (key: K) => void;
  className?: string;
}) {
  const active = sort.key === sortKey;
  return (
    <th className={className}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        // Preflight resets text-transform/letter-spacing on buttons; re-inherit so the
        // label follows the thead's casing convention like a plain <th> does.
        className="flex items-center gap-1 font-semibold hover:text-foreground [letter-spacing:inherit] [text-transform:inherit]"
      >
        {label}
        {active ? (
          sort.dir === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronsUpDown className="h-3 w-3 opacity-40" />
        )}
      </button>
    </th>
  );
}

type SortValue = string | number | boolean | null | undefined;

/**
 * Client-side sort for fully-loaded lists. `accessors` maps each sortable column
 * to a value getter; nulls sort last regardless of direction; numbers compare
 * numerically, everything else via locale-aware string compare.
 */
export function sortRows<T, K extends string>(
  rows: T[],
  { key, dir }: SortState<K>,
  accessors: Record<K, (row: T) => SortValue>,
): T[] {
  const get = accessors[key];
  if (!get) return rows;
  const factor = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = get(a);
    const vb = get(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1; // nulls always last
    if (vb == null) return -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * factor;
    return String(va).localeCompare(String(vb)) * factor;
  });
}
