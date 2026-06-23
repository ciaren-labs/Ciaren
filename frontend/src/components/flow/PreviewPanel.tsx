import { useState } from "react";
import { useFlowPreview } from "@/features/flows/hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { ColumnProfileList } from "@/components/data/ColumnProfileList";
import { DataTable } from "./DataTable";

interface PreviewPanelProps {
  flowId: string;
  onClose: () => void;
}

export function PreviewPanel({ flowId, onClose }: PreviewPanelProps) {
  const selectedNodeId = useFlowEditorStore((s) => s.selectedNodeId);
  const preview = useFlowPreview(flowId);
  const [view, setView] = useState<"table" | "profile">("table");

  const runPreview = (mode: "table" | "profile" = view) => {
    setView(mode);
    preview.mutate({
      node_id: selectedNodeId ?? undefined,
      limit: 50,
      profile: mode === "profile",
    });
  };

  return (
    <div className="flex h-64 flex-col border-t border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Data Preview</h3>
          {selectedNodeId && (
            <span className="text-xs text-muted-foreground">
              node: {selectedNodeId}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => runPreview("table")}
            disabled={preview.isPending}
          >
            {preview.isPending && view === "table" ? "Previewing…" : "Run preview"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runPreview("profile")}
            disabled={preview.isPending}
          >
            {preview.isPending && view === "profile" ? "Profiling…" : "Profile"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {preview.isError && (
          <p className="p-3 text-sm text-destructive">
            {(preview.error as ApiError)?.message ?? "Preview failed."}
          </p>
        )}
        {preview.data ? (
          <>
            <div className="px-3 py-1 text-[11px] text-muted-foreground">
              {preview.data.row_count} rows
              {preview.data.truncated && " (truncated)"}
            </div>
            {view === "profile" && preview.data.profile ? (
              <ColumnProfileList profile={preview.data.profile} />
            ) : (
              <DataTable columns={preview.data.columns} rows={preview.data.rows} />
            )}
          </>
        ) : (
          !preview.isError && (
            <p className="p-3 text-sm text-muted-foreground">
              Save the flow, then run a preview. Select a node to preview its
              output, or preview the whole flow.
            </p>
          )
        )}
      </div>
    </div>
  );
}
