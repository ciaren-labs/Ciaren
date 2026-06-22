import { useNavigate } from "react-router-dom";
import { History, Loader2, Table2, Workflow } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable } from "@/components/flow/DataTable";
import { useDatasetFlows, useDatasetSample, useDatasetVersions } from "./hooks";
import { formatDateTime } from "@/lib/format";
import type { Dataset } from "@/lib/types";

export function DatasetDetailDialog({
  dataset,
  open,
  onOpenChange,
}: {
  dataset: Dataset | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        {dataset && (
          <>
            <DialogHeader>
              <DialogTitle>{dataset.name}</DialogTitle>
              <DialogDescription>
                {dataset.source_type.toUpperCase()} ·{" "}
                {dataset.column_schema?.length ?? 0} columns · v
                {dataset.latest_version} ({dataset.version_count} version
                {dataset.version_count === 1 ? "" : "s"})
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="preview">
              <TabsList>
                <TabsTrigger value="preview">
                  <Table2 className="mr-1.5 h-3.5 w-3.5" /> Preview
                </TabsTrigger>
                <TabsTrigger value="versions">
                  <History className="mr-1.5 h-3.5 w-3.5" /> Versions
                </TabsTrigger>
                <TabsTrigger value="flows">
                  <Workflow className="mr-1.5 h-3.5 w-3.5" /> Used by
                </TabsTrigger>
              </TabsList>

              <TabsContent value="preview">
                <PreviewTab dataset={dataset} />
              </TabsContent>
              <TabsContent value="versions">
                <VersionsTab datasetId={dataset.id} latest={dataset.latest_version} />
              </TabsContent>
              <TabsContent value="flows">
                <FlowsTab datasetId={dataset.id} onNavigate={() => onOpenChange(false)} />
              </TabsContent>
            </Tabs>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PreviewTab({ dataset }: { dataset: Dataset }) {
  const { data: sample, isLoading } = useDatasetSample(dataset.id);
  if (isLoading) return <Loading />;
  const rows = sample ?? [];
  const columns =
    dataset.column_schema?.map((c) => c.name) ??
    (rows[0] ? Object.keys(rows[0]) : []);
  return (
    <div className="max-h-[55vh] overflow-auto rounded-lg border border-border">
      <DataTable columns={columns} rows={rows.slice(0, 50)} />
    </div>
  );
}

function VersionsTab({ datasetId, latest }: { datasetId: string; latest: number }) {
  const { data: versions, isLoading } = useDatasetVersions(datasetId);
  if (isLoading) return <Loading />;
  return (
    <div className="flex max-h-[55vh] flex-col gap-2 overflow-auto">
      {(versions ?? []).map((v) => (
        <div key={v.id} className="rounded-lg border border-border bg-card p-3">
          <div className="mb-1.5 flex items-center gap-2">
            <span className="rounded-md bg-brand-100 px-1.5 py-0.5 text-xs font-semibold text-brand-700">
              v{v.version_number}
            </span>
            {v.version_number === latest && (
              <span className="rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                latest
              </span>
            )}
            <span className="text-xs text-muted-foreground">
              {v.row_count} rows · {formatDateTime(v.created_at)}
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {(v.column_schema ?? []).slice(0, 12).map((col) => (
              <span
                key={col.name}
                className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
                title={`${col.name}: ${col.type}`}
              >
                {col.name}
              </span>
            ))}
            {(v.column_schema?.length ?? 0) > 12 && (
              <span className="px-1 text-[10px] text-muted-foreground">
                +{(v.column_schema?.length ?? 0) - 12} more
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function FlowsTab({
  datasetId,
  onNavigate,
}: {
  datasetId: string;
  onNavigate: () => void;
}) {
  const navigate = useNavigate();
  const { data: flows, isLoading } = useDatasetFlows(datasetId);
  if (isLoading) return <Loading />;
  if (!flows || flows.length === 0) {
    return (
      <p className="p-6 text-center text-sm text-muted-foreground">
        No flows use this dataset yet.
      </p>
    );
  }
  return (
    <div className="flex max-h-[55vh] flex-col gap-1.5 overflow-auto">
      {flows.map((flow) => (
        <button
          key={flow.id}
          onClick={() => {
            onNavigate();
            navigate(`/flows/${flow.id}`);
          }}
          className="flex items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2 text-left text-sm transition-colors hover:bg-accent/40"
        >
          <Workflow className="h-4 w-4 text-brand-600" />
          <span className="flex-1 font-medium">{flow.name}</span>
          <span className="text-xs text-muted-foreground">
            {flow.graph_json?.nodes.length ?? 0} nodes
          </span>
        </button>
      ))}
    </div>
  );
}

function Loading() {
  return (
    <p className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading…
    </p>
  );
}
