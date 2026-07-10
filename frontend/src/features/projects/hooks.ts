import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/features/projects/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";
import type { ProjectCreate, ProjectUpdate } from "@/features/projects/types";

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects, queryFn: projectsApi.list });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectCreate) => projectsApi.create(body),
    // The project form dialog renders failures inline.
    meta: { suppressErrorToast: true },
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      toast.success(`Project "${project.name}" created`);
    },
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ProjectUpdate }) =>
      projectsApi.update(id, body),
    // The project form dialog renders failures inline.
    meta: { suppressErrorToast: true },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      toast.success("Project updated");
    },
  });
}

export function useToggleProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_disabled }: { id: string; is_disabled: boolean }) =>
      projectsApi.update(id, { is_disabled }),
    meta: { errorMessage: "Couldn't update the project" },
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      toast.success(
        project.is_disabled
          ? `Project "${project.name}" disabled`
          : `Project "${project.name}" enabled`,
      );
    },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => projectsApi.remove(id),
    meta: { errorMessage: "Couldn't delete the project" },
    onSuccess: () => {
      // Deleting a project reassigns its datasets/flows to Default.
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      toast.success("Project deleted", {
        description: "Its datasets and flows were moved to the Default project.",
      });
    },
  });
}
