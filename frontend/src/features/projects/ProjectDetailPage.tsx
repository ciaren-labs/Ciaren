import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Database, FileOutput, Loader2, Plus, Workflow } from "lucide-react";
import { useProjects } from "./hooks";
import { useCreateFlow, useFlows } from "@/features/flows/hooks";
import { useDatasets } from "@/features/datasets/hooks";
import { DatasetDetailDialog } from "@/features/datasets/DatasetDetailDialog";
import { DatasetsPanel } from "@/features/datasets/DatasetsPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { projectColor } from "@/lib/projectColors";
import { cn } from "@/lib/utils";
import type { Dataset } from "@/lib/types";

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: projects, isLoading } = useProjects();
  const project = projects?.find((p) => p.id === projectId);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }
  if (!project) {
    return <div className="p-6 text-sm text-destructive">Project not found.</div>;
  }

  const theme = projectColor(project.color);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <button
        onClick={() => navigate("/projects")}
        className="mb-3 flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Projects
      </button>

      <div className="mb-5 flex items-center gap-3">
        <span
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-xl text-lg font-semibold text-white shadow-sm",
            theme.badge,
          )}
        >
          {project.name.charAt(0).toUpperCase()}
        </span>
        <div>
          <h1 className="text-xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground">
            {project.description || "No description"}
          </p>
        </div>
      </div>

      <Tabs defaultValue="datasets">
        <TabsList>
          <TabsTrigger value="datasets">
            <Database className="mr-1.5 h-3.5 w-3.5" /> Datasets ({project.dataset_count})
          </TabsTrigger>
          <TabsTrigger value="flows">
            <Workflow className="mr-1.5 h-3.5 w-3.5" /> Flows ({project.flow_count})
          </TabsTrigger>
          <TabsTrigger value="outputs">
            <FileOutput className="mr-1.5 h-3.5 w-3.5" /> Outputs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="datasets" className="mt-4">
          <DatasetsPanel projectId={project.id} />
        </TabsContent>
        <TabsContent value="flows" className="mt-4">
          <ProjectFlows projectId={project.id} />
        </TabsContent>
        <TabsContent value="outputs" className="mt-4">
          <ProjectOutputsTab projectId={project.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ProjectOutputsTab({ projectId }: { projectId: string }) {
  const { data: datasets, isLoading } = useDatasets(projectId);
  const [selected, setSelected] = useState<Dataset | null>(null);

  const outputs = (datasets ?? []).filter((d) => d.dataset_kind === "output");

  if (isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </p>
    );
  }

  if (outputs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No outputs yet. Run a flow with an output node to generate datasets here.
      </p>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {outputs.map((d) => (
          <button
            key={d.id}
            onClick={() => setSelected(d)}
            className="animate-fade-in-up rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                output
              </span>
              <span className="truncate font-semibold text-sm">{d.name}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {d.source_type.toUpperCase()} · {d.column_schema?.length ?? 0} columns
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {d.version_count === 1
                ? "1 version"
                : `${d.version_count} versions (latest v${d.latest_version})`}
            </p>
          </button>
        ))}
      </div>

      <DatasetDetailDialog
        dataset={selected}
        open={selected !== null}
        onOpenChange={(o) => !o && setSelected(null)}
        defaultTab="versions"
      />
    </>
  );
}

function ProjectFlows({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const { data: flows, isLoading } = useFlows(projectId);
  const createFlow = useCreateFlow();
  const [name, setName] = useState("");

  const create = () => {
    const trimmed = name.trim() || "Untitled flow";
    createFlow.mutate(
      { name: trimmed, project_id: projectId, graph_json: { nodes: [], edges: [] } },
      { onSuccess: (flow) => navigate(`/flows/${flow.id}`) },
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create()}
          placeholder="New flow name…"
          className="h-9 flex-1 rounded-md border border-input bg-background px-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:max-w-xs"
        />
        <Button onClick={create} disabled={createFlow.isPending}>
          <Plus className="h-4 w-4" /> New flow
        </Button>
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(flows ?? []).map((flow) => (
          <button
            key={flow.id}
            onClick={() => navigate(`/flows/${flow.id}`)}
            className="animate-fade-in-up rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-center gap-2">
              <Workflow className="h-4 w-4 text-brand-600" />
              <span className="truncate font-semibold">{flow.name}</span>
            </div>
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {flow.description || "No description"}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              {flow.graph_json?.nodes.length ?? 0} nodes
            </p>
          </button>
        ))}
      </div>
      {flows && flows.length === 0 && !isLoading && (
        <p className="text-sm text-muted-foreground">No flows in this project yet.</p>
      )}
    </div>
  );
}
