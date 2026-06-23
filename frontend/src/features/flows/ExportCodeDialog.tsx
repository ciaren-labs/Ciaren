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

  useEffect(() => {
    if (open) exportPython.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
            </TabsList>
            <TabsContent value="pandas" className="min-w-0">
              <CodeBlock code={exportPython.data.code} />
            </TabsContent>
            <TabsContent value="polars" className="min-w-0">
              <CodeBlock code={exportPython.data.polars} />
            </TabsContent>
          </Tabs>
        )}
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
