import { useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  FileText,
  Loader2,
  UploadCloud,
} from "lucide-react";
import { useDatasets, useUploadDataset } from "./hooks";
import { useProjects } from "@/features/projects/hooks";
import { DatasetDetailDialog } from "./DatasetDetailDialog";
import { FilterBar, FilterField, SearchInput } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { projectColor } from "@/lib/projectColors";
import type { Dataset, DatasetSourceType } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCE_META: Record<DatasetSourceType, { icon: typeof FileText; tint: string }> = {
  csv: { icon: FileText, tint: "bg-emerald-500" },
  excel: { icon: FileSpreadsheet, tint: "bg-green-600" },
  parquet: { icon: Database, tint: "bg-indigo-500" },
};

interface DatasetsPanelProps {
  /** When set, the panel is scoped to one project: no grouping, uploads land here. */
  projectId?: string;
}

export function DatasetsPanel({ projectId }: DatasetsPanelProps) {
  const scoped = projectId !== undefined;
  const { data: datasets, isLoading } = useDatasets();
  const { data: projects } = useProjects();
  const upload = useUploadDataset();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [uploadProjectId, setUploadProjectId] = useState("");
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [versionWarnOpen, setVersionWarnOpen] = useState(false);

  const targetProject = scoped ? projectId : uploadProjectId || undefined;

  const doUpload = (file: File) => upload.mutate({ file, projectId: targetProject });

  const submit = (file: File | undefined) => {
    if (!file) return;
    const existing = (datasets ?? []).find(
      (d) => d.name.toLowerCase() === file.name.toLowerCase(),
    );
    if (existing) {
      setPendingFile(file);
      setVersionWarnOpen(true);
    } else {
      doUpload(file);
    }
  };

  const confirmNewVersion = () => {
    if (pendingFile) doUpload(pendingFile);
    setPendingFile(null);
    setVersionWarnOpen(false);
  };

  const cancelNewVersion = () => {
    setPendingFile(null);
    setVersionWarnOpen(false);
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

  const filtered = useMemo(() => {
    let list = datasets ?? [];
    if (scoped) list = list.filter((d) => d.project_id === projectId);
    else if (projectFilter) list = list.filter((d) => d.project_id === projectFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((d) => d.name.toLowerCase().includes(q));
    }
    return list;
  }, [datasets, scoped, projectId, projectFilter, search]);

  const groups = useMemo(() => {
    if (scoped || projectFilter) return null;
    const byProject = new Map<string, Dataset[]>();
    for (const d of filtered) {
      const key = d.project_id ?? "none";
      byProject.set(key, [...(byProject.get(key) ?? []), d]);
    }
    return (projects ?? [])
      .map((p) => ({ project: p, items: byProject.get(p.id) ?? [] }))
      .filter((g) => g.items.length > 0);
  }, [filtered, projects, scoped, projectFilter]);

  return (
    <div className="flex flex-col gap-5">
      {/* Upload section — 2-step when not scoped to a project */}
      {scoped ? (
        <UploadDropzone
          dragging={dragging}
          upload={upload}
          inputRef={inputRef}
          onFile={onFile}
          onDrop={onDrop}
          setDragging={setDragging}
        />
      ) : uploadProjectId ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between rounded-lg border border-border bg-muted/40 px-3 py-2">
            <span className="flex items-center gap-2 text-sm font-medium">
              <span className="h-2 w-2 rounded-full bg-brand-500" />
              {(projects ?? []).find((p) => p.id === uploadProjectId)?.name ?? "Project"}
            </span>
            <button
              type="button"
              onClick={() => setUploadProjectId("")}
              className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              Change
            </button>
          </div>
          <UploadDropzone
            dragging={dragging}
            upload={upload}
            inputRef={inputRef}
            onFile={onFile}
            onDrop={onDrop}
            setDragging={setDragging}
          />
        </div>
      ) : (
        <div className="flex flex-col gap-3 rounded-xl border border-dashed border-border bg-muted/20 px-6 py-8 text-center">
          <p className="text-sm font-medium text-foreground">Step 1 — Choose a project</p>
          <p className="text-xs text-muted-foreground">Select the project this dataset belongs to before uploading.</p>
          <SearchableSelect
            value={uploadProjectId}
            onChange={setUploadProjectId}
            allLabel="Select a project…"
            placeholder="Search projects…"
            className="mx-auto w-full max-w-xs"
            options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </div>
      )}

      {/* Controls */}
      <FilterBar>
        <FilterField label="Search" className="flex-1 min-w-[10rem]">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search datasets…"
          />
        </FilterField>
        {!scoped && (
          <FilterField label="Project">
            <SearchableSelect
              value={projectFilter}
              onChange={setProjectFilter}
              allLabel="All projects"
              placeholder="Search projects…"
              className="sm:w-52"
              options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
            />
          </FilterField>
        )}
      </FilterBar>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}

      {groups ? (
        <div className="flex flex-col gap-5">
          {groups.map(({ project, items }) => {
            const theme = projectColor(project.color);
            return (
              <section key={project.id} className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className={cn("h-2.5 w-2.5 rounded-full", theme.dot)} />
                  <h2 className="text-sm font-semibold">{project.name}</h2>
                  <span className="text-xs text-muted-foreground">{items.length}</span>
                </div>
                <DatasetGrid datasets={items} onSelect={setSelected} />
              </section>
            );
          })}
        </div>
      ) : (
        <DatasetGrid datasets={filtered} onSelect={setSelected} />
      )}

      {!isLoading && filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {search || projectFilter
            ? "No datasets match your filters."
            : "No datasets yet. Upload one to get started."}
        </p>
      )}

      <DatasetDetailDialog
        dataset={selected}
        open={selected !== null}
        onOpenChange={(o) => !o && setSelected(null)}
      />

      {/* New-version warning */}
      <Dialog open={versionWarnOpen} onOpenChange={(o) => !o && cancelNewVersion()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Add new version?
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            A dataset named <strong className="text-foreground">{pendingFile?.name}</strong> already
            exists. Re-uploading will create a new version — existing data and flows that reference
            earlier versions are not affected.
          </p>
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="outline" onClick={cancelNewVersion}>
              Cancel
            </Button>
            <Button onClick={confirmNewVersion} disabled={upload.isPending}>
              {upload.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Add new version
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DatasetGrid({
  datasets,
  onSelect,
}: {
  datasets: Dataset[];
  onSelect: (d: Dataset) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {datasets.map((d) => (
        <DatasetCard key={d.id} dataset={d} onClick={() => onSelect(d)} />
      ))}
    </div>
  );
}

function DatasetCard({ dataset: d, onClick }: { dataset: Dataset; onClick: () => void }) {
  const meta = SOURCE_META[d.source_type] ?? SOURCE_META.csv;
  const Icon = meta.icon;
  const schema = d.column_schema ?? [];

  return (
    <button onClick={onClick} className="text-left">
      <Card className="animate-fade-in-up h-full overflow-hidden transition-shadow hover:shadow-md">
        <CardHeader className="flex-row items-center gap-3 space-y-0">
          <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg text-white shadow-sm", meta.tint)}>
            <Icon className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <CardTitle className="truncate text-sm">{d.name}</CardTitle>
            <CardDescription className="text-xs">
              {d.source_type.toUpperCase()} · {schema.length} columns ·{" "}
              {d.version_count > 1 ? `v${d.latest_version} (${d.version_count} versions)` : "v1"}
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
    </button>
  );
}

function UploadDropzone({
  dragging,
  upload,
  inputRef,
  onFile,
  onDrop,
  setDragging,
}: {
  dragging: boolean;
  upload: ReturnType<typeof useUploadDataset>;
  inputRef: React.RefObject<HTMLInputElement>;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onDrop: (e: React.DragEvent) => void;
  setDragging: (v: boolean) => void;
}) {
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
      <div className="text-xs text-muted-foreground">CSV, Excel or Parquet</div>
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
  );
}
