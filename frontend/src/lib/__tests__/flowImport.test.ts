import { describe, expect, it } from "vitest";
import { flowNameConflicts, resolveImportTargetProjectId } from "../flowImport";

const flows = [
  { name: "Imported flow", project_id: "p-analytics" },
  { name: "Nightly ETL", project_id: "p-default" },
];

describe("resolveImportTargetProjectId", () => {
  it("uses the explicit filter when set", () => {
    expect(resolveImportTargetProjectId("p-analytics", [])).toBe("p-analytics");
  });

  it("falls back to the default project when no filter is set", () => {
    const projects = [
      { id: "p-default", is_default: true },
      { id: "p-analytics", is_default: false },
    ];
    expect(resolveImportTargetProjectId("", projects)).toBe("p-default");
  });

  it("is undefined when nothing resolves (no filter, no default known)", () => {
    expect(resolveImportTargetProjectId("", undefined)).toBeUndefined();
  });
});

describe("flowNameConflicts — project-scoped", () => {
  it("does NOT flag a name that only exists in another project", () => {
    // "Imported flow" lives in p-analytics; importing into p-default is fine.
    expect(flowNameConflicts(flows, "Imported flow", "p-default")).toBe(false);
  });

  it("flags a name that exists in the destination project (case-insensitive)", () => {
    expect(flowNameConflicts(flows, "imported FLOW", "p-analytics")).toBe(true);
  });

  it("does not flag a genuinely new name", () => {
    expect(flowNameConflicts(flows, "Brand new", "p-analytics")).toBe(false);
  });
});
