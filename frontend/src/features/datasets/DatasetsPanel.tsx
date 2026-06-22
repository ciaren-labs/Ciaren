import { useRef } from "react";
import { useDatasets, useUploadDataset } from "./hooks";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

export function DatasetsPanel() {
  const { data: datasets, isLoading } = useDatasets();
  const upload = useUploadDataset();
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload.mutate(file);
    e.target.value = "";
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Upload dataset</CardTitle>
          <CardDescription>
            CSV, Excel, or Parquet. Uploaded datasets can be referenced by input
            nodes.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.parquet"
            className="hidden"
            onChange={onFile}
          />
          <Button
            onClick={() => inputRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Uploading…" : "Choose file"}
          </Button>
          {upload.isError && (
            <span className="text-sm text-destructive">
              {(upload.error as ApiError)?.message ?? "Upload failed."}
            </span>
          )}
          {upload.isSuccess && (
            <span className="text-sm text-emerald-600">Uploaded.</span>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {(datasets ?? []).map((d) => (
          <Card key={d.id}>
            <CardHeader>
              <CardTitle className="text-base">{d.name}</CardTitle>
              <CardDescription>
                {d.source_type} ·{" "}
                {d.schema_json ? `${d.schema_json.length} columns` : "schema n/a"}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              <div className="font-mono break-all">{d.id}</div>
            </CardContent>
          </Card>
        ))}
        {datasets && datasets.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No datasets yet. Upload one to get started.
          </p>
        )}
      </div>
    </div>
  );
}
