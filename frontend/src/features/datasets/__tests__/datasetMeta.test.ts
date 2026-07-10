import { describe, expect, it } from "vitest";
import { versionLabel } from "../components/datasetMeta";

describe("versionLabel", () => {
  it("shows just the version when the kept count matches", () => {
    expect(versionLabel(5, 5)).toBe("v5");
  });

  it("appends the kept count when older versions were purged", () => {
    expect(versionLabel(5, 2)).toBe("v5 (2 kept)");
  });

  it("handles a brand-new dataset (v1, 1 kept)", () => {
    expect(versionLabel(1, 1)).toBe("v1");
  });

  it("handles the degenerate case where nothing is kept", () => {
    expect(versionLabel(3, 0)).toBe("v3 (0 kept)");
  });
});
