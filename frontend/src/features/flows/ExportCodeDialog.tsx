import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useExportPython } from "./hooks";
import { ApiError } from "@/lib/api";

interface ExportCodeDialogProps {
  flowId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ExportCodeDialog({
  flowId,
  open,
  onOpenChange,
}: ExportCodeDialogProps) {
  const exportPython = useExportPython(flowId);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) {
      setCopied(false);
      exportPython.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const copy = async () => {
    if (exportPython.data?.code) {
      await navigator.clipboard.writeText(exportPython.data.code);
      setCopied(true);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Generated Python</DialogTitle>
        </DialogHeader>

        {exportPython.isPending && (
          <p className="text-sm text-muted-foreground">Generating code…</p>
        )}
        {exportPython.isError && (
          <p className="text-sm text-destructive">
            {(exportPython.error as ApiError)?.message ?? "Export failed."}
          </p>
        )}
        {exportPython.data && (
          <>
            <pre className="max-h-96 overflow-auto rounded-md bg-slate-900 p-4 text-xs text-slate-100">
              <code>{exportPython.data.code}</code>
            </pre>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={copy}>
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
