import type { Flow } from "@/features/flows/types";
import type { Project } from "@/features/projects/types";

/**
 * The project an imported flow will actually land in: the explicitly selected
 * one, or the Default project when none is chosen (mirrors the backend, which
 * resolves an omitted project_id to Default).
 */
export function resolveImportTargetProjectId(
  projectFilter: string,
  projects: Pick<Project, "id" | "is_default">[] | undefined,
): string | undefined {
  return projectFilter || projects?.find((p) => p.is_default)?.id;
}

/**
 * Whether importing under `name` would clash with an existing flow — scoped to
 * the destination project only. The backend has no global flow-name uniqueness
 * (the same name is fine across projects), so a clash in a *different* project
 * must not block the import. Comparison is case-insensitive.
 */
export function flowNameConflicts(
  flows: Pick<Flow, "name" | "project_id">[],
  name: string,
  targetProjectId: string | undefined,
): boolean {
  const wanted = name.trim().toLowerCase();
  return flows.some(
    (f) => f.name.toLowerCase() === wanted && f.project_id === targetProjectId,
  );
}
