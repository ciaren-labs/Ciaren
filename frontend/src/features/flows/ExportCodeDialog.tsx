import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
  const [freeIntermediates, setFreeIntermediates] = useState(false);

  useEffect(() => {
    if (open) exportPython.mutate(freeIntermediates);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, freeIntermediates]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-[92vw] max-h-[88vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle>Generated code</DialogTitle>
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
          <Tabs defaultValue="pandas" className="min-w-0">
            <TabsList>
              <TabsTrigger value="pandas">pandas</TabsTrigger>
              <TabsTrigger value="polars">polars</TabsTrigger>
              <TabsTrigger value="polars_lazy">polars (lazy)</TabsTrigger>
            </TabsList>
            <TabsContent value="pandas" className="min-w-0">
              <CodeBlock code={exportPython.data.code} />
            </TabsContent>
            <TabsContent value="polars" className="min-w-0">
              <CodeBlock code={exportPython.data.polars} />
            </TabsContent>
            <TabsContent value="polars_lazy" className="min-w-0">
              <p className="mb-2 text-xs text-muted-foreground">
                Builds a single lazy query (scan → collect) so polars can apply
                projection / predicate pushdown. Best for large inputs.
              </p>
              <CodeBlock code={exportPython.data.polars_lazy} />
            </TabsContent>
          </Tabs>
        )}

        <div className="flex items-start gap-2 border-t pt-3">
          <input
            id="free-intermediates"
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
            checked={freeIntermediates}
            onChange={(e) => setFreeIntermediates(e.target.checked)}
          />
          <div className="min-w-0">
            <Label htmlFor="free-intermediates" className="cursor-pointer">
              Free intermediate tables (<code>del</code>)
            </Label>
            <p className="text-xs text-muted-foreground">
              Releases each table right after its last use to lower peak memory.
              Applies to the pandas and polars tabs; the lazy plan needs no{" "}
              <code>del</code>.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="relative min-w-0">
      <Button
        variant="outline"
        size="sm"
        onClick={copy}
        className="absolute right-2 top-2 z-10"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? "Copied" : "Copy"}
      </Button>
      <pre className="max-h-[70vh] overflow-auto rounded-md bg-slate-900 p-4 text-xs text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}
