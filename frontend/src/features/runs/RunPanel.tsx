import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useCreateRun } from "@/features/flows/hooks";
import { useDatasets } from "@/features/datasets/hooks";
import { useRun } from "./hooks";
import type { RunStatus } from "@/lib/types";
import { ApiError } from "@/lib/api";

interface RunPanelProps {
  flowId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const STATUS_COLOR: Record<RunStatus, string> = {
  pending: "text-slate-500",
  running: "text-sky-600",
  success: "text-emerald-600",
  failed: "text-destructive",
};

export function RunPanel({ flowId, open, onOpenChange }: RunPanelProps) {
  const { data: datasets } = useDatasets();
  const createRun = useCreateRun(flowId);
  const [runId, setRunId] = useState<string | null>(null);
  const [inputDatasetId, setInputDatasetId] = useState<string>("");
  const run = useRun(runId);

  const trigger = () => {
    createRun.mutate(inputDatasetId || undefined, {
      onSuccess: (created) => setRunId(created.id),
    });
  };

  const current = run.data;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Run Flow</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label>Input dataset (optional)</Label>
            <Select
              value={inputDatasetId}
              onChange={(e) => setInputDatasetId(e.target.value)}
            >
              <option value="">Use input nodes' datasets</option>
              {(datasets ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </div>

          <Button onClick={trigger} disabled={createRun.isPending}>
            {createRun.isPending ? "Starting…" : "Start run"}
          </Button>

          {createRun.isError && (
            <p className="text-sm text-destructive">
              {(createRun.error as ApiError)?.message ?? "Failed to start run."}
            </p>
          )}

          {current && (
            <div className="rounded-md border border-border p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">Status</span>
                <span className={STATUS_COLOR[current.status]}>
                  {current.status}
                </span>
              </div>
              {current.output_location && (
                <div className="mt-2 text-xs text-muted-foreground">
                  Output: {current.output_location}
                </div>
              )}
              {current.error_message && (
                <pre className="mt-2 whitespace-pre-wrap rounded bg-destructive/10 p-2 text-xs text-destructive">
                  {current.error_message}
                </pre>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
