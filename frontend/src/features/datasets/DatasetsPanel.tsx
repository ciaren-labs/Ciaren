import { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  FileText,
  Loader2,
  UploadCloud,
} from "lucide-react";
import { useDatasets, useUploadDataset } from "./hooks";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import type { Dataset, DatasetSourceType } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCE_META: Record<DatasetSourceType, { icon: typeof FileText; tint: string }> = {
  csv: { icon: FileText, tint: "bg-emerald-500" },
  excel: { icon: FileSpreadsheet, tint: "bg-green-600" },
  parquet: { icon: Database, tint: "bg-indigo-500" },
};

export function DatasetsPanel() {
  const { data: datasets, isLoading } = useDatasets();
  const upload = useUploadDataset();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const submit = (file: File | undefined) => {
    if (file) upload.mutate(file);
  };

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    submit(e.target.files?.[0]);
    e.target.value = "";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    submit(e.dataTransfer.files?.[0]);
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Upload dropzone */}
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
          "group flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging
            ? "border-primary bg-accent"
            : "border-border bg-muted/30 hover:border-primary/50 hover:bg-accent/40",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.parquet"
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
          CSV, Excel or Parquet · names must be unique
        </div>
        {upload.isError && (
          <span className="mt-1 flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive">
            <AlertCircle className="h-3.5 w-3.5" />
            {(upload.error as ApiError)?.message ?? "Upload failed."}
          </span>
        )}
        {upload.isSuccess && !upload.isPending && (
          <span className="mt-1 flex items-center gap-1.5 text-xs font-medium text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" /> Uploaded
          </span>
        )}
      </button>

      {/* Dataset grid */}
      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(datasets ?? []).map((d) => (
          <DatasetCard key={d.id} dataset={d} />
        ))}
      </div>
      {datasets && datasets.length === 0 && !isLoading && (
        <p className="text-sm text-muted-foreground">
          No datasets yet. Upload one to get started.
        </p>
      )}
    </div>
  );
}

function DatasetCard({ dataset: d }: { dataset: Dataset }) {
  const meta = SOURCE_META[d.source_type] ?? SOURCE_META.csv;
  const Icon = meta.icon;
  const schema = d.column_schema ?? [];

  return (
    <Card className="animate-fade-in-up overflow-hidden transition-shadow hover:shadow-md">
      <CardHeader className="flex-row items-center gap-3 space-y-0">
        <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg text-white shadow-sm", meta.tint)}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <CardTitle className="truncate text-sm">{d.name}</CardTitle>
          <CardDescription className="text-xs">
            {d.source_type.toUpperCase()} · {schema.length} columns
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {schema.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {schema.slice(0, 8).map((col) => (
              <span
                key={col.name}
                className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
                title={`${col.name}: ${col.type}`}
              >
                {col.name}
              </span>
            ))}
            {schema.length > 8 && (
              <span className="rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground">
                +{schema.length - 8} more
              </span>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Schema unavailable.</p>
        )}
      </CardContent>
    </Card>
  );
}
