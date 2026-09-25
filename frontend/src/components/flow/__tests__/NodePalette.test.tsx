import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NodePalette } from "../NodePalette";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RECENT_NODES_KEY } from "@/features/flows/recentNodes";

beforeEach(() => {
  // Catalog + available-types requests resolve empty, so the palette shows the
  // static catalog (ML nodes hidden).
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => [] })),
  );
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

function renderPalette({ unlocked = true } = {}) {
  const onAdd = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <NodePalette onAdd={onAdd} unlocked={unlocked} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
  return { onAdd };
}

const recentSection = () => screen.queryByRole("region", { name: "Recently used" });
const itemNames = (container: HTMLElement) =>
  within(container)
    .getAllByRole("button")
    .map((b) => b.textContent);
const search = (value: string) =>
  fireEvent.change(screen.getByPlaceholderText("Search nodes…"), { target: { value } });

describe("NodePalette recently used section", () => {
  it("lists recent catalog nodes with an empty query and hides them while searching", () => {
    localStorage.setItem(
      RECENT_NODES_KEY,
      // An unknown (uninstalled plugin) type and a palette-hidden legacy type are skipped.
      JSON.stringify(["sortRows", "ghostPlugin.node", "csvInput", "fileInput"]),
    );
    renderPalette();

    const section = recentSection();
    expect(section).not.toBeNull();
    expect(itemNames(section!)).toEqual(["Sort Rows", "File Input"]);

    search("sort rows");
    expect(recentSection()).toBeNull();
    // Search results are the plain match list: exactly one "Sort Rows" entry.
    expect(screen.getAllByRole("button", { name: "Sort Rows" })).toHaveLength(1);

    search("");
    expect(recentSection()).not.toBeNull();
  });

  it("moves a node placed from the palette to the front of the section", () => {
    localStorage.setItem(RECENT_NODES_KEY, JSON.stringify(["sortRows", "fileInput"]));
    const { onAdd } = renderPalette();

    search("drop nulls");
    fireEvent.click(screen.getByRole("button", { name: "Drop Nulls" }));
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ type: "dropNulls" }));
    search("");
    expect(itemNames(recentSection()!)).toEqual(["Drop Nulls", "Sort Rows", "File Input"]);

    fireEvent.click(within(recentSection()!).getByRole("button", { name: "File Input" }));
    expect(itemNames(recentSection()!)).toEqual(["File Input", "Drop Nulls", "Sort Rows"]);
  });

  it("keeps the input-first lock on recent items", () => {
    localStorage.setItem(RECENT_NODES_KEY, JSON.stringify(["sortRows", "fileInput"]));
    renderPalette({ unlocked: false });

    const section = recentSection()!;
    expect(within(section).getByRole("button", { name: "Sort Rows" })).toBeDisabled();
    expect(within(section).getByRole("button", { name: "File Input" })).toBeEnabled();
  });

  it("hides the section but keeps the palette working when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    const { onAdd } = renderPalette();
    expect(recentSection()).toBeNull();

    search("file input");
    fireEvent.click(screen.getByRole("button", { name: "File Input" }));
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ type: "fileInput" }));
    search("");
    expect(recentSection()).toBeNull();
  });
});
