import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Database,
  FolderKanban,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Workflow,
} from "lucide-react";
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useUpdateProject,
} from "./hooks";
import { ProjectFormDialog } from "./ProjectFormDialog";
import { Button } from "@/components/ui/button";
import { projectColor } from "@/lib/projectColors";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ProjectsPage() {
  const navigate = useNavigate();
  const { data: projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();
  const deleteProject = useDeleteProject();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <FolderKanban className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Projects</h1>
            <p className="text-xs text-muted-foreground">
              Workspaces that group related datasets and flows.
            </p>
          </div>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" /> New project
        </Button>
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(projects ?? []).map((project) => (
          <ProjectCard
            key={project.id}
            project={project}
            onOpen={() => navigate(`/projects/${project.id}`)}
            onEdit={() => setEditing(project)}
            onDelete={() => {
              if (
                confirm(
                  `Delete project "${project.name}"? Its datasets and flows move to Default.`,
                )
              ) {
                deleteProject.mutate(project.id);
              }
            }}
          />
        ))}
      </div>

      <ProjectFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Create project"
        submitting={createProject.isPending}
        error={createProject.error}
        onSubmit={(values) =>
          createProject.mutate(values, { onSuccess: () => setCreateOpen(false) })
        }
      />
      <ProjectFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Edit project"
        initial={editing ?? undefined}
        submitting={updateProject.isPending}
        error={updateProject.error}
        onSubmit={(values) =>
          editing &&
          updateProject.mutate(
            { id: editing.id, body: values },
            { onSuccess: () => setEditing(null) },
          )
        }
      />
    </div>
  );
}

function ProjectCard({
  project,
  onOpen,
  onEdit,
  onDelete,
}: {
  project: Project;
  onOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const theme = projectColor(project.color);
  return (
    <div className="group animate-fade-in-up overflow-hidden rounded-xl border border-border bg-card shadow-sm transition-shadow hover:shadow-md">
      <button onClick={onOpen} className="block w-full text-left">
        <div className={cn("flex items-center gap-3 px-4 py-3", theme.tint)}>
          <span
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-lg text-base font-semibold text-white shadow-sm",
              theme.badge,
            )}
          >
            {project.name.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate font-semibold">{project.name}</span>
              {project.is_default && (
                <span className="rounded-full bg-card/70 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  default
                </span>
              )}
            </div>
            <p className="truncate text-xs text-muted-foreground">
              {project.description || "No description"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 px-4 py-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5" /> {project.dataset_count} datasets
          </span>
          <span className="flex items-center gap-1.5">
            <Workflow className="h-3.5 w-3.5" /> {project.flow_count} flows
          </span>
        </div>
      </button>
      <div className="flex items-center justify-end gap-1 border-t border-border px-2 py-1.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={onEdit}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Edit project"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        {!project.is_default && (
          <button
            onClick={onDelete}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            title="Delete project"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
