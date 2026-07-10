import { useEffect } from "react";
import { AlertCircle, CheckCircle2, Loader2, UploadCloud } from "lucide-react";
import { friendlyErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import type { useUploadDataset } from "../hooks";

export function UploadDropzone({
  dragging,
  upload,
  inputRef,
  onFile,
  onDrop,
  setDragging,
}: {
  dragging: boolean;
  upload: ReturnType<typeof useUploadDataset>;
  inputRef: React.RefObject<HTMLInputElement | null>;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onDrop: (e: React.DragEvent) => void;
  setDragging: (v: boolean) => void;
}) {
  // The success/error indicator below would otherwise linger indefinitely
  // (react-query keeps the last mutation status until the next call) — clear
  // it after a few seconds, same as the connection Test button's feedback.
  useEffect(() => {
    if (!upload.isSuccess && !upload.isError) return;
    const t = setTimeout(() => upload.reset(), 5000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [upload.isSuccess, upload.isError]);

  return (
    <button
      type="button"
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "group flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
        dragging
          ? "border-primary bg-accent"
          : "border-border bg-muted/30 hover:border-primary/50 hover:bg-accent/40",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.tsv,.xlsx,.xls,.parquet,.json,.jsonl,.txt"
        className="hidden"
        onChange={onFile}
      />
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-primary transition-transform group-hover:scale-105">
        {upload.isPending ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <UploadCloud className="h-5 w-5" />
        )}
      </span>
      <div className="text-sm font-medium">
        {upload.isPending ? "Uploading…" : "Drop a file here, or click to browse"}
      </div>
      <div className="text-xs text-muted-foreground">
        CSV, TSV, Excel, Parquet, JSON, JSON Lines, or plain text
      </div>
      {upload.isError && (
        <span className="mt-1 flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {friendlyErrorMessage(upload.error, "Upload failed.")}
        </span>
      )}
      {upload.isSuccess && !upload.isPending && (
        <span className="mt-1 flex items-center gap-1.5 text-xs font-medium text-emerald-600">
          <CheckCircle2 className="h-3.5 w-3.5" /> Uploaded
        </span>
      )}
    </button>
  );
}
