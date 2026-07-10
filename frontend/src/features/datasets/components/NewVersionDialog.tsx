import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function NewVersionDialog({
  open,
  fileName,
  isPending,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  fileName: string | null;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Add new version?
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          A dataset named <strong className="text-foreground">{fileName}</strong> already
          exists. Re-uploading will create a new version — existing data and flows that reference
          earlier versions are not affected.
        </p>
        <div className="mt-2 flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={isPending}>
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Add new version
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
