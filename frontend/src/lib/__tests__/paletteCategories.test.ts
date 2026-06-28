import { describe, expect, it } from "vitest";
import {
  CATEGORY_ORDER,
  getCategoryLabel,
  paletteCategories,
  type NodeTypeDef,
} from "../nodeCatalog";
import { getCategoryIcon, getCategoryTheme } from "../nodeVisuals";

function def(type: string, category: string): NodeTypeDef {
  return {
    type,
    label: type,
    category: category as NodeTypeDef["category"],
    defaultConfig: {},
    inputHandles: ["in"],
    hasOutput: true,
    description: "",
  };
}

describe("paletteCategories", () => {
  it("keeps the built-in order and appends plugin categories sorted", () => {
    const defs = [
      def("filterRows", "clean"),
      def("zNode", "integrations"),
      def("aNode", "ai_tools"),
    ];
    const cats = paletteCategories(defs);
    // Built-ins come first, in their canonical order…
    expect(cats.slice(0, CATEGORY_ORDER.length)).toEqual(CATEGORY_ORDER);
    // …then the novel plugin categories, de-duplicated and sorted.
    expect(cats.slice(CATEGORY_ORDER.length)).toEqual(["ai_tools", "integrations"]);
  });

  it("does not duplicate a category that is also built in", () => {
    const cats = paletteCategories([def("x", "clean"), def("y", "clean")]);
    expect(cats).toEqual(CATEGORY_ORDER);
  });
});

describe("getCategoryLabel", () => {
  it("uses the curated label for built-in categories", () => {
    expect(getCategoryLabel("clean")).toBe("Cleaning");
    expect(getCategoryLabel("ml")).toBe("Machine Learning");
  });

  it("title-cases an unknown plugin category", () => {
    expect(getCategoryLabel("ai_tools")).toBe("Ai Tools");
    expect(getCategoryLabel("custom-stuff")).toBe("Custom Stuff");
  });
});

describe("category visuals fall back for unknown categories", () => {
  it("returns an icon and a theme for a plugin category without throwing", () => {
    expect(getCategoryIcon("integrations")).toBeTruthy();
    const theme = getCategoryTheme("integrations");
    expect(theme.badge).toBeTruthy();
    // Falls back to the neutral plugin theme rather than crashing on undefined.
    expect(getCategoryTheme("clean")).not.toBe(getCategoryTheme("integrations"));
  });
});
