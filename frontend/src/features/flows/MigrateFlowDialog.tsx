import { useRef, useState } from "react";
import { AlertCircle, Download, FileUp } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useMigrateFlowDocument } from "./hooks";
import { friendlyErrorMessage } from "@/lib/errors";

interface MigrateFlowDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Standalone file-to-file utility: upgrade an exported .flow.json to the
 * current schema version without importing it into a project. Backs the
 * "Migrate a file…" action next to Import on the flows page. */
export function MigrateFlowDialog({ open, onOpenChange }: MigrateFlowDialogProps) {
  const migrate = useMigrateFlowDocument();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const reset = () => {
    setFileName(null);
    setParseError(null);
    migrate.reset();
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    setParseError(null);
    let doc: Record<string, unknown>;
    try {
      doc = JSON.parse(await file.text()) as Record<string, unknown>;
    } catch {
      setFileName(null);
      setParseError("That file isn't valid JSON.");
      return;
    }
    setFileName(file.name);
    migrate.mutate(doc);
  };

  const download = () => {
    if (!migrate.data) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(migrate.data.document, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileName?.replace(/\.json$/i, "") ?? "flow"}.migrated.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Migrate a flow file</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Upload an exported <code>.flow.json</code> file to check and, if needed, upgrade it to
            the current schema version. This doesn't import anything into a project.
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={onFile}
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={migrate.isPending}
          >
            <FileUp className="h-4 w-4" /> Choose file…
          </Button>

          {fileName && (
            <p className="text-xs text-muted-foreground">Selected: {fileName}</p>
          )}

          {parseError && (
            <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-[11px] text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {parseError}
            </p>
          )}
          {migrate.isError && (
            <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-[11px] text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {friendlyErrorMessage(migrate.error, "That file couldn't be validated.")}
            </p>
          )}
          {migrate.data && (
            <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/30 p-3">
              {migrate.data.migrated ? (
                <p className="text-xs">
                  Upgraded from schema v{migrate.data.from_version} to v{migrate.data.to_version}.
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Already up to date (schema v{migrate.data.to_version}).
                </p>
              )}
              {migrate.data.migrated && (
                <Button size="sm" onClick={download}>
                  <Download className="h-3.5 w-3.5" /> Download migrated file
                </Button>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
