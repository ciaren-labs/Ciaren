import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SortableTh, sortRows, type SortState } from "../SortableHeader";

interface Row {
  name: string;
  size: number | null;
}

const ACCESSORS = {
  name: (r: Row) => r.name.toLowerCase(),
  size: (r: Row) => r.size,
} as const;

const rows: Row[] = [
  { name: "Banana", size: 3 },
  { name: "apple", size: 1 },
  { name: "Cherry", size: null },
];

describe("sortRows", () => {
  it("sorts strings case-insensitively ascending and descending", () => {
    const asc = sortRows(rows, { key: "name", dir: "asc" }, ACCESSORS).map((r) => r.name);
    expect(asc).toEqual(["apple", "Banana", "Cherry"]);
    const desc = sortRows(rows, { key: "name", dir: "desc" }, ACCESSORS).map((r) => r.name);
    expect(desc).toEqual(["Cherry", "Banana", "apple"]);
  });

  it("sorts numbers numerically", () => {
    const asc = sortRows(rows, { key: "size", dir: "asc" }, ACCESSORS).map((r) => r.size);
    expect(asc.slice(0, 2)).toEqual([1, 3]);
  });

  it("always puts nulls last, regardless of direction", () => {
    const asc = sortRows(rows, { key: "size", dir: "asc" }, ACCESSORS);
    const desc = sortRows(rows, { key: "size", dir: "desc" }, ACCESSORS);
    expect(asc[asc.length - 1].size).toBeNull();
    expect(desc[desc.length - 1].size).toBeNull();
  });

  it("does not mutate the input array", () => {
    const original = [...rows];
    sortRows(rows, { key: "name", dir: "asc" }, ACCESSORS);
    expect(rows).toEqual(original);
  });
});

describe("SortableTh", () => {
  it("calls onSort with its key when clicked", () => {
    const onSort = vi.fn();
    const sort: SortState<"name"> = { key: "name", dir: "asc" };
    render(
      <table><thead><tr>
        <SortableTh label="Name" sortKey="name" sort={sort} onSort={onSort} />
      </tr></thead></table>,
    );
    screen.getByText("Name").click();
    expect(onSort).toHaveBeenCalledWith("name");
  });
});
