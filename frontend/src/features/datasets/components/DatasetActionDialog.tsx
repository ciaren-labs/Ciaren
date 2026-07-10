import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Dataset } from "@/features/datasets/types";
import { useDatasetFlows } from "../hooks";

export function DatasetActionDialog({
  dataset,
  kind,
  onCancel,
  onConfirm,
  isPending,
}: {
  dataset: Dataset;
  kind: "disable" | "enable" | "delete";
  onCancel: () => void;
  onConfirm: () => void;
  isPending: boolean;
}) {
  const { data: flows } = useDatasetFlows(dataset.id);
  const affectedFlows = flows ?? [];

  const isDelete = kind === "delete";
  const isEnable = kind === "enable";

  return (
    <Dialog open onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            {isDelete ? "Delete dataset?" : isEnable ? "Enable dataset?" : "Disable dataset?"}
          </DialogTitle>
        </DialogHeader>
        <div className="text-sm text-muted-foreground space-y-2">
          {isDelete && (
            <>
              <p>
                <strong className="text-foreground">{dataset.name}</strong> will be removed from your workspace. This is a soft-delete: its versions and files are retained and it can be restored later — nothing is erased from disk now.
              </p>
              {affectedFlows.length > 0 && (
                <p className="rounded-md bg-amber-50 p-2.5 text-amber-800 text-xs">
                  {affectedFlows.length} flow{affectedFlows.length > 1 ? "s" : ""} that use this dataset as an input will also be disabled:{" "}
                  <strong>{affectedFlows.map((f) => f.name).join(", ")}</strong>. Re-enable them separately after restoring the dataset.
                </p>
              )}
            </>
          )}
          {kind === "disable" && (
            <>
              <p>
                <strong className="text-foreground">{dataset.name}</strong> will be marked as disabled and hidden from use in new flows.
              </p>
              {affectedFlows.length > 0 && (
                <p className="rounded-md bg-amber-50 p-2.5 text-amber-800 text-xs">
                  {affectedFlows.length} flow{affectedFlows.length > 1 ? "s" : ""} that use this dataset will also be disabled:{" "}
                  <strong>{affectedFlows.map((f) => f.name).join(", ")}</strong>.
                </p>
              )}
            </>
          )}
          {isEnable && (
            <p>
              <strong className="text-foreground">{dataset.name}</strong> will be re-enabled. Flows that were disabled due to this dataset are <em>not</em> automatically re-enabled — enable them separately if needed.
            </p>
          )}
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            variant={isDelete ? "destructive" : "default"}
          >
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {isDelete ? "Delete" : isEnable ? "Enable" : "Disable"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
