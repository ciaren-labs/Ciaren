import { afterEach, describe, expect, it, vi } from "vitest";
import {
  pushRecentNodeType,
  readRecentNodeTypes,
  recordRecentNodeType,
  RECENT_NODES_KEY,
} from "@/features/flows/recentNodes";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("pushRecentNodeType", () => {
  it.each([
    { name: "adds to an empty list", list: [], type: "a", expected: ["a"] },
    { name: "puts a new type first", list: ["a", "b"], type: "c", expected: ["c", "a", "b"] },
    { name: "moves an existing type to the front", list: ["a", "b", "c"], type: "c", expected: ["c", "a", "b"] },
    { name: "keeps the front type in place", list: ["a", "b"], type: "a", expected: ["a", "b"] },
    {
      name: "drops the oldest past five",
      list: ["a", "b", "c", "d", "e"],
      type: "f",
      expected: ["f", "a", "b", "c", "d"],
    },
  ])("$name", ({ list, type, expected }) => {
    expect(pushRecentNodeType(list, type)).toEqual(expected);
  });
});

describe("readRecentNodeTypes", () => {
  it.each([
    { name: "absent key", raw: null, expected: [] },
    { name: "corrupt JSON", raw: "[not json", expected: [] },
    { name: "an object", raw: '{"0":"a"}', expected: [] },
    { name: "a bare string", raw: '"a"', expected: [] },
    { name: "non-strings, empties and duplicates", raw: '[1,"a",null,"a","",{"t":"b"},"b"]', expected: ["a", "b"] },
    { name: "more than five items", raw: '["a","b","c","d","e","f","g"]', expected: ["a", "b", "c", "d", "e"] },
  ])("sanitizes $name", ({ raw, expected }) => {
    if (raw !== null) localStorage.setItem(RECENT_NODES_KEY, raw);
    expect(readRecentNodeTypes()).toEqual(expected);
  });
});

describe("recordRecentNodeType", () => {
  it("persists placements most recent first, deduped and capped", () => {
    for (const type of ["a", "b", "a", "c", "d", "e", "f"]) recordRecentNodeType(type);

    expect(readRecentNodeTypes()).toEqual(["f", "e", "d", "c", "a"]);
    expect(JSON.parse(localStorage.getItem(RECENT_NODES_KEY)!)).toEqual(["f", "e", "d", "c", "a"]);
  });

  it("starts over from a corrupt stored value", () => {
    localStorage.setItem(RECENT_NODES_KEY, '{"broken":true}');
    recordRecentNodeType("a");
    expect(readRecentNodeTypes()).toEqual(["a"]);
  });

  it("stays empty without throwing when storage is blocked", () => {
    const blocked = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);

    expect(() => recordRecentNodeType("a")).not.toThrow();
    expect(readRecentNodeTypes()).toEqual([]);
  });
});
