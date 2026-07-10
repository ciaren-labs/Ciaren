import { useMemo, useRef, useState } from "react";
import { Database, UploadCloud } from "lucide-react";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import { useDatasets, useDeleteDataset, usePatchDataset, useUploadDataset } from "./hooks";
import { useProjects } from "@/features/projects/hooks";
import { DatasetDetailDialog } from "./DatasetDetailDialog";
import { FilterBar, FilterField, SearchInput } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { ViewToggle } from "@/components/filters/ViewToggle";
import { Button } from "@/components/ui/button";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/PageState";
import { sortRows, useSort } from "@/components/ui/SortableHeader";
import type { Dataset } from "@/features/datasets/types";
import { DATASET_SORT, type DatasetSortKey } from "./components/datasetMeta";
import { DatasetGrid } from "./components/DatasetCard";
import { DatasetTable } from "./components/DatasetTable";
import { UploadDropzone } from "./components/UploadDropzone";
import { ImportOptionsRow } from "./components/ImportOptionsRow";
import { DatasetActionDialog } from "./components/DatasetActionDialog";
import { NewVersionDialog } from "./components/NewVersionDialog";

interface DatasetsPanelProps {
  /** When set, the panel is scoped to one project: no grouping, uploads land here. */
  projectId?: string;
}

export function DatasetsPanel({ projectId }: DatasetsPanelProps) {
  const scoped = projectId !== undefined;
  const { data: datasets, isPending, isError, error, refetch } = useDatasets();
  const { data: projects } = useProjects();
  const upload = useUploadDataset();
  const patchDataset = usePatchDataset();
  const deleteDataset = useDeleteDataset();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [uploadProjectId, setUploadProjectId] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [versionWarnOpen, setVersionWarnOpen] = useState(false);
  const [layout, setLayout] = useLayoutPreference("datasets", "cards");
  const { sort, toggle: toggleSort } = useSort<DatasetSortKey>("created", "desc");
  // Pending disable/delete action with cascade confirmation
  const [pendingAction, setPendingAction] = useState<{
    dataset: Dataset;
    kind: "disable" | "enable" | "delete";
  } | null>(null);

  const targetProject = scoped ? projectId : uploadProjectId || undefined;
  // Dialect overrides for the next upload; "" = auto-detect (the default).
  const [importOptions, setImportOptions] = useState({ delimiter: "", encoding: "", decimal: "", sheet: "" });

  const doUpload = (file: File) => {
    const options = Object.fromEntries(
      Object.entries(importOptions).filter(([, v]) => v !== ""),
    );
    upload.mutate({
      file,
      projectId: targetProject,
      options: Object.keys(options).length ? options : undefined,
    });
  };

  const submit = (file: File | undefined) => {
    if (!file) return;
    // Name collisions only trigger a new *version* within the same project
    // (backend: DatasetService.upload scopes the name lookup by project_id) —
    // an unset target resolves to the Default project, same as the backend.
    const resolvedTargetProjectId = targetProject ?? projects?.find((p) => p.is_default)?.id;
    const existing = (datasets ?? []).find(
      (d) =>
        d.name.toLowerCase() === file.name.toLowerCase() &&
        d.project_id === resolvedTargetProjectId,
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
    if (kindFilter) list = list.filter((d) => d.dataset_kind === kindFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((d) => d.name.toLowerCase().includes(q));
    }
    return list;
  }, [datasets, scoped, projectId, projectFilter, kindFilter, search]);

  const groups = useMemo(() => {
    if (scoped || projectFilter) return null;
    const byProject = new Map<string, Dataset[]>();
    for (const d of filtered) {
      if (!d.project_id) continue; // every dataset belongs to a project
      byProject.set(d.project_id, [...(byProject.get(d.project_id) ?? []), d]);
    }
    return (projects ?? [])
      .map((p) => ({ id: p.id, name: p.name, color: p.color as string | null | undefined, items: byProject.get(p.id) ?? [] }))
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
      ) : (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2">
            <span className="shrink-0 text-xs font-medium text-muted-foreground">Upload to project</span>
            <SearchableSelect
              value={uploadProjectId}
              onChange={setUploadProjectId}
              allLabel="Default project"
              placeholder="Search projects…"
              className="max-w-xs flex-1"
              options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
            />
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
      )}
      <ImportOptionsRow options={importOptions} onChange={setImportOptions} />

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
        <FilterField label="Type" className="min-w-[8rem]">
          <SearchableSelect
            value={kindFilter}
            onChange={setKindFilter}
            allLabel="All types"
            options={[
              { value: "input", label: "Uploads" },
              { value: "output", label: "Outputs" },
            ]}
          />
        </FilterField>
        <div className="ml-auto self-end">
          <ViewToggle value={layout} onChange={setLayout} />
        </div>
      </FilterBar>

      {isPending && <LoadingState label="Loading datasets…" />}
      {isError && <ErrorState error={error} title="Couldn't load datasets" onRetry={() => refetch()} />}

      {groups ? (
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <CollapsibleSection
              key={g.id}
              title={g.name}
              colorKey={g.color}
              count={g.items.length}
            >
              {layout === "cards" ? (
                <DatasetGrid datasets={sortRows(g.items, sort, DATASET_SORT)} onSelect={setSelected} onAction={(d, k) => setPendingAction({ dataset: d, kind: k })} />
              ) : (
                <DatasetTable datasets={sortRows(g.items, sort, DATASET_SORT)} sort={sort} onSort={toggleSort} onSelect={setSelected} onAction={(d, k) => setPendingAction({ dataset: d, kind: k })} />
              )}
            </CollapsibleSection>
          ))}
        </div>
      ) : (
        layout === "cards" ? (
          <DatasetGrid datasets={sortRows(filtered, sort, DATASET_SORT)} onSelect={setSelected} onAction={(d, k) => setPendingAction({ dataset: d, kind: k })} />
        ) : (
          <DatasetTable datasets={sortRows(filtered, sort, DATASET_SORT)} sort={sort} onSort={toggleSort} onSelect={setSelected} onAction={(d, k) => setPendingAction({ dataset: d, kind: k })} />
        )
      )}

      {!isPending && !isError && filtered.length === 0 && (
        search || projectFilter || kindFilter ? (
          <EmptyState
            icon={Database}
            title="No datasets match your filters"
            description="Try a different search, or clear the filters."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setSearch(""); setProjectFilter(""); setKindFilter(""); }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={UploadCloud}
            title="Add your first dataset"
            description="Drop a CSV, Excel, Parquet, or JSON file in the box above — it becomes a versioned dataset your flows can read."
          />
        )
      )}

      <DatasetDetailDialog
        dataset={selected}
        open={selected !== null}
        onOpenChange={(o) => !o && setSelected(null)}
      />

      {/* Disable / delete confirmation */}
      {pendingAction && (
        <DatasetActionDialog
          dataset={pendingAction.dataset}
          kind={pendingAction.kind}
          onCancel={() => setPendingAction(null)}
          onConfirm={() => {
            const { dataset, kind } = pendingAction;
            setPendingAction(null);
            if (kind === "disable")
              patchDataset.mutate({ id: dataset.id, body: { is_disabled: true } });
            else if (kind === "enable")
              patchDataset.mutate({ id: dataset.id, body: { is_disabled: false } });
            else
              deleteDataset.mutate(dataset.id);
          }}
          isPending={patchDataset.isPending || deleteDataset.isPending}
        />
      )}

      <NewVersionDialog
        open={versionWarnOpen}
        fileName={pendingFile?.name ?? null}
        isPending={upload.isPending}
        onCancel={cancelNewVersion}
        onConfirm={confirmNewVersion}
      />
    </div>
  );
}
