import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, ExternalLink, History, Loader2, Table2, Workflow } from "lucide-react";
import { datasetsApi } from "@/lib/api";
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
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import type { Dataset } from "@/lib/types";

export function DatasetDetailDialog({
  dataset,
  open,
  onOpenChange,
  defaultTab = "preview",
}: {
  dataset: Dataset | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: string;
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

            <Tabs defaultValue={defaultTab} key={`${dataset.id}-${defaultTab}`}>
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
  const [version, setVersion] = useState<number | undefined>(undefined);
  const { data: versions } = useDatasetVersions(dataset.id);
  const { data: sample, isLoading } = useDatasetSample(dataset.id, version);
  const rows = sample ?? [];
  const columns =
    dataset.column_schema?.map((c) => c.name) ??
    (rows[0] ? Object.keys(rows[0]) : []);
  return (
    <div className="flex flex-col gap-2">
      {(versions?.length ?? 0) > 1 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>Version:</span>
          <select
            value={version ?? ""}
            onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : undefined)}
            className="h-7 rounded border border-input bg-background px-1.5 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Latest (v{dataset.latest_version})</option>
            {(versions ?? []).map((v) => (
              <option key={v.id} value={v.version_number}>
                v{v.version_number} — {v.row_count} rows
              </option>
            ))}
          </select>
        </div>
      )}
      {isLoading ? (
        <Loading />
      ) : (
        <div className="max-h-[50vh] overflow-auto rounded-lg border border-border">
          <DataTable columns={columns} rows={rows.slice(0, 50)} />
        </div>
      )}
    </div>
  );
}

function VersionsTab({ datasetId, latest }: { datasetId: string; latest: number }) {
  const navigate = useNavigate();
  const fmt = useFormatDateTime();
  const { data: versions, isLoading } = useDatasetVersions(datasetId);
  if (isLoading) return <Loading />;
  return (
    <div className="flex max-h-[55vh] flex-col gap-2 overflow-auto">
      {(versions ?? []).map((v) => (
        <div key={v.id} className="rounded-lg border border-border bg-card p-3">
          <div className="mb-1.5 flex items-center gap-2 flex-wrap">
            <span className="rounded-md bg-brand-100 px-1.5 py-0.5 text-xs font-semibold text-brand-700">
              v{v.version_number}
            </span>
            {v.version_number === latest && (
              <span className="rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                latest
              </span>
            )}
            <span className="text-xs text-muted-foreground">
              {v.row_count} rows · {fmt(v.created_at)}
            </span>
            <div className="ml-auto flex items-center gap-2">
              {v.source_run_id && (
                <button
                  onClick={() => navigate(`/runs/${v.source_run_id}`)}
                  className="flex items-center gap-1 text-[11px] text-brand-600 hover:underline"
                >
                  <ExternalLink className="h-3 w-3" /> Generated by run
                </button>
              )}
              <a
                href={datasetsApi.downloadVersionUrl(datasetId, v.version_number)}
                download
                className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
              >
                <Download className="h-3 w-3" /> Download
              </a>
            </div>
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
