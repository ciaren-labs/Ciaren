import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { Loader2, Plus, Trash2, Workflow } from "lucide-react";
import { useCreateFlow, useDeleteFlow, useFlows } from "./hooks";
import { useProjects } from "@/features/projects/hooks";
import { flowFormSchema, type FlowFormValues } from "@/lib/validators";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SearchInput } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { projectColor } from "@/lib/projectColors";
import type { Flow } from "@/lib/types";
import { cn } from "@/lib/utils";

export function FlowListPage() {
  const { data: flows, isLoading } = useFlows();
  const { data: projects } = useProjects();
  const createFlow = useCreateFlow();
  const deleteFlow = useDeleteFlow();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");

  const projectById = useMemo(
    () => new Map((projects ?? []).map((p) => [p.id, p])),
    [projects],
  );

  const filtered = useMemo(() => {
    let list = flows ?? [];
    if (projectFilter) list = list.filter((f) => f.project_id === projectFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.name.toLowerCase().includes(q) ||
          (f.description ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [flows, projectFilter, search]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FlowFormValues>({ defaultValues: { name: "", description: "" } });

  const onCreate = handleSubmit((values) => {
    const parsed = flowFormSchema.safeParse(values);
    if (!parsed.success) return;
    createFlow.mutate(
      {
        name: values.name,
        description: values.description,
        project_id: projectFilter || undefined,
        graph_json: { nodes: [], edges: [] },
      },
      {
        onSuccess: (flow) => {
          reset();
          setOpen(false);
          navigate(`/flows/${flow.id}`);
        },
      },
    );
  });

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <Workflow className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Flows</h1>
            <p className="text-xs text-muted-foreground">
              Visual pipelines you can preview, run, and export.
            </p>
          </div>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" /> New flow
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create flow</DialogTitle>
            </DialogHeader>
            <form onSubmit={onCreate} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <Label>Name</Label>
                <Input {...register("name")} placeholder="My ETL flow" />
                {errors.name && (
                  <p className="text-[11px] text-destructive">{errors.name.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label>Description</Label>
                <Textarea {...register("description")} />
              </div>
              <Button type="submit" disabled={createFlow.isPending}>
                {createFlow.isPending ? "Creating…" : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search flows…"
          className="flex-1 sm:max-w-xs"
        />
        <SearchableSelect
          value={projectFilter}
          onChange={setProjectFilter}
          allLabel="All projects"
          placeholder="Search projects…"
          className="sm:w-52"
          options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
        />
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((flow) => (
          <FlowCard
            key={flow.id}
            flow={flow}
            projectName={flow.project_id ? projectById.get(flow.project_id)?.name : undefined}
            projectColorKey={
              flow.project_id ? projectById.get(flow.project_id)?.color : undefined
            }
            onOpen={() => navigate(`/flows/${flow.id}`)}
            onDelete={() => {
              if (confirm(`Delete flow "${flow.name}"?`)) deleteFlow.mutate(flow.id);
            }}
          />
        ))}
      </div>

      {!isLoading && filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {search || projectFilter
            ? "No flows match your filters."
            : "No flows yet. Create one to start building."}
        </p>
      )}
    </div>
  );
}

function FlowCard({
  flow,
  projectName,
  projectColorKey,
  onOpen,
  onDelete,
}: {
  flow: Flow;
  projectName?: string;
  projectColorKey?: string;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const theme = projectColor(projectColorKey);
  return (
    <div className="group animate-fade-in-up flex flex-col rounded-xl border border-border bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      <button onClick={onOpen} className="flex-1 text-left">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-brand-600" />
          <span className="truncate font-semibold">{flow.name}</span>
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
          {flow.description || "No description"}
        </p>
        <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{flow.graph_json?.nodes.length ?? 0} nodes</span>
          {projectName && (
            <span className="flex items-center gap-1.5">
              <span className={cn("h-2 w-2 rounded-full", theme.dot)} />
              {projectName}
            </span>
          )}
        </div>
      </button>
      <div className="mt-3 flex items-center justify-end gap-2 border-t border-border pt-2.5">
        <Button size="sm" variant="outline" onClick={onOpen}>
          Open
        </Button>
        <button
          onClick={onDelete}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          title="Delete flow"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
