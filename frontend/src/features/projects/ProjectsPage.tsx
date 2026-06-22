import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Database,
  FolderKanban,
  LayoutGrid,
  List,
  Loader2,
  Pencil,
  Plus,
  Power,
  Trash2,
  Workflow,
} from "lucide-react";
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useToggleProject,
  useUpdateProject,
} from "./hooks";
import { ProjectFormDialog } from "./ProjectFormDialog";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import { projectColor } from "@/lib/projectColors";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";

type PendingAction =
  | { kind: "disable"; project: Project }
  | { kind: "enable"; project: Project }
  | { kind: "delete"; project: Project };

export function ProjectsPage() {
  const navigate = useNavigate();
  const { data: projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();
  const deleteProject = useDeleteProject();
  const toggleProject = useToggleProject();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [layout, setLayout] = useLayoutPreference("projects", "cards");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  const handleConfirm = () => {
    if (!pendingAction) return;
    const { kind, project } = pendingAction;
    setPendingAction(null);
    if (kind === "delete") deleteProject.mutate(project.id);
    else if (kind === "disable") toggleProject.mutate({ id: project.id, is_disabled: true });
    else toggleProject.mutate({ id: project.id, is_disabled: false });
  };

  const confirmTitle = pendingAction
    ? pendingAction.kind === "delete"
      ? `Delete "${pendingAction.project.name}"?`
      : pendingAction.kind === "disable"
        ? `Disable "${pendingAction.project.name}"?`
        : `Enable "${pendingAction.project.name}"?`
    : "";

  const confirmDescription = pendingAction ? (
    pendingAction.kind === "delete" ? (
      <p>
        This will permanently delete the project. Its datasets and flows will be moved to the
        Default project.
      </p>
    ) : pendingAction.kind === "disable" ? (
      <div className="space-y-1.5">
        <p>The project will be marked as disabled. All its datasets and flows will also be disabled.</p>
        <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-800">
          Flows in this project become read-only and cannot be run until the project or each flow is
          re-enabled individually.
        </p>
      </div>
    ) : (
      <p>
        The project will be re-enabled. Datasets and flows disabled by this cascade are not
        automatically re-enabled — enable them individually if needed.
      </p>
    )
  ) : null;

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
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
            <button
              type="button"
              onClick={() => setLayout("cards")}
              className={cn("rounded p-1.5 transition-colors", layout === "cards" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
              title="Card view"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setLayout("table")}
              className={cn("rounded p-1.5 transition-colors", layout === "table" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
              title="Table view"
            >
              <List className="h-3.5 w-3.5" />
            </button>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> New project
          </Button>
        </div>
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}

      {layout === "cards" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(projects ?? []).map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={() => navigate(`/projects/${project.id}`)}
              onEdit={() => setEditing(project)}
              onToggle={() =>
                setPendingAction({ kind: project.is_disabled ? "enable" : "disable", project })
              }
              onDelete={() => setPendingAction({ kind: "delete", project })}
            />
          ))}
        </div>
      ) : (
        <ProjectTable
          projects={projects ?? []}
          onOpen={(id) => navigate(`/projects/${id}`)}
          onEdit={(p) => setEditing(p)}
          onToggle={(p) => setPendingAction({ kind: p.is_disabled ? "enable" : "disable", project: p })}
          onDelete={(p) => setPendingAction({ kind: "delete", project: p })}
        />
      )}

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

      <ConfirmDialog
        open={pendingAction !== null}
        onOpenChange={(o) => !o && setPendingAction(null)}
        title={confirmTitle}
        description={confirmDescription}
        confirmLabel={
          pendingAction?.kind === "delete"
            ? "Delete"
            : pendingAction?.kind === "disable"
              ? "Disable"
              : "Enable"
        }
        variant={pendingAction?.kind === "delete" ? "destructive" : "warning"}
        isPending={deleteProject.isPending || toggleProject.isPending}
        onConfirm={handleConfirm}
      />
    </div>
  );
}

function ProjectCard({
  project,
  onOpen,
  onEdit,
  onToggle,
  onDelete,
}: {
  project: Project;
  onOpen: () => void;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const theme = projectColor(project.color);
  return (
    <div className={cn("group animate-fade-in-up overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md", project.is_disabled ? "border-amber-300 opacity-70" : "border-border")}>
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
              {project.is_disabled && (
                <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                  disabled
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
          <>
            <button
              onClick={onToggle}
              className={cn(
                "rounded-md p-1.5 transition-colors hover:bg-muted",
                project.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
              )}
              title={project.is_disabled ? "Enable project" : "Disable project"}
            >
              <Power className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onDelete}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              title="Delete project"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function ProjectTable({
  projects,
  onOpen,
  onEdit,
  onToggle,
  onDelete,
}: {
  projects: Project[];
  onOpen: (id: string) => void;
  onEdit: (p: Project) => void;
  onToggle: (p: Project) => void;
  onDelete: (p: Project) => void;
}) {
  if (projects.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 text-left font-semibold">Name</th>
            <th className="px-4 py-2.5 text-left font-semibold">Datasets</th>
            <th className="px-4 py-2.5 text-left font-semibold">Flows</th>
            <th className="px-4 py-2.5 text-left font-semibold">Status</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => {
            const theme = projectColor(project.color);
            return (
              <tr
                key={project.id}
                className={cn("border-t border-border hover:bg-accent/40 transition-colors", project.is_disabled && "bg-amber-50/30 opacity-70")}
              >
                <td className="px-4 py-2.5">
                  <button onClick={() => onOpen(project.id)} className="flex items-center gap-2 font-medium hover:underline">
                    <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full", theme.dot)} />
                    {project.name}
                    {project.is_default && (
                      <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        default
                      </span>
                    )}
                  </button>
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">{project.dataset_count}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{project.flow_count}</td>
                <td className="px-4 py-2.5">
                  {project.is_disabled ? (
                    <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                      disabled
                    </span>
                  ) : (
                    <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                      active
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onEdit(project)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      title="Edit"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    {!project.is_default && (
                      <>
                        <button
                          onClick={() => onToggle(project)}
                          className={cn(
                            "rounded-md p-1.5 transition-colors hover:bg-muted",
                            project.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
                          )}
                          title={project.is_disabled ? "Enable" : "Disable"}
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => onDelete(project)}
                          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
