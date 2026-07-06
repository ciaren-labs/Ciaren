import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import { useFlowPreview } from "@/features/flows/hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { friendlyErrorMessage } from "@/lib/errors";
import { ColumnProfileList } from "@/components/data/ColumnProfileList";
import {
  buildColumnMeta,
  chartDefaults,
  clamp,
  type Aggregate,
  type ChartDefaults,
  type ColumnMeta,
} from "@/lib/chartData";
import { DataTable } from "./DataTable";
import { ChartPreview } from "./ChartPreview";

interface PreviewPanelProps {
  flowId: string;
  onClose: () => void;
}

type View = "table" | "profile" | "chart";

// More rows make the client-side charts meaningful, but it is still a sample.
const CHART_SAMPLE_LIMIT = 500;

const CHART_TYPE_GROUPS: { label: string; types: { value: string; label: string }[] }[] = [
  {
    label: "Distribution",
    types: [
      { value: "histogramChart", label: "Histogram" },
      { value: "boxPlot", label: "Box plot" },
      { value: "valueCounts", label: "Value counts" },
    ],
  },
  {
    label: "Comparison",
    types: [
      { value: "barChart", label: "Bar" },
      { value: "horizontalBarChart", label: "Horizontal bar" },
      { value: "stackedBarChart", label: "Stacked bar" },
      { value: "pieChart", label: "Pie" },
    ],
  },
  {
    label: "Trend",
    types: [
      { value: "lineChart", label: "Line / time series" },
      { value: "areaChart", label: "Area" },
    ],
  },
  {
    label: "Relationship",
    types: [
      { value: "scatterChart", label: "Scatter" },
      { value: "correlationHeatmap", label: "Correlation heatmap" },
    ],
  },
];

// Which controls each chart type needs.
const SINGLE_COLUMN = new Set(["histogramChart", "valueCounts"]);
const XY = new Set([
  "barChart",
  "horizontalBarChart",
  "stackedBarChart",
  "pieChart",
  "lineChart",
  "areaChart",
  "scatterChart",
]);
const CATEGORY_XY = new Set(["barChart", "horizontalBarChart", "stackedBarChart", "pieChart"]);
const WITH_AGGREGATE = new Set(["barChart", "horizontalBarChart", "stackedBarChart", "pieChart"]);
const WITH_GROUP = new Set(["stackedBarChart"]);

const AGGREGATES: Aggregate[] = ["sum", "mean", "count", "min", "max"];

export function PreviewPanel({ flowId, onClose }: PreviewPanelProps) {
  const selectedNodeId = useFlowEditorStore((s) => s.selectedNodeId);
  const nodes = useFlowEditorStore((s) => s.nodes);
  const dirty = useFlowEditorStore((s) => s.dirty);
  const preview = useFlowPreview(flowId);
  const [view, setView] = useState<View>("table");
  // The node the currently-shown results belong to (null = whole flow, undefined = no run yet).
  const [previewedNodeId, setPreviewedNodeId] = useState<string | null | undefined>(undefined);
  const hasRun = useRef(false);
  // Bumped on every run and on every node switch, so a response for a node we've
  // since navigated away from can be recognized as stale and dropped.
  const requestIdRef = useRef(0);

  // Human name for the selected node ("Filter Rows"), not its machine id.
  const selectedNodeLabel = selectedNodeId
    ? (nodes.find((n) => n.id === selectedNodeId)?.data.label ?? selectedNodeId)
    : null;
  const previewedNodeLabel = previewedNodeId
    ? (nodes.find((n) => n.id === previewedNodeId)?.data.label ?? previewedNodeId)
    : null;

  // Discard stale results when the user selects a different node — otherwise
  // the old node's preview stays on screen and looks like it belongs to the
  // newly selected node.
  useEffect(() => {
    if (hasRun.current && selectedNodeId !== previewedNodeId) {
      requestIdRef.current += 1;
      preview.reset();
      setPreviewedNodeId(undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId]);

  const runPreview = (mode: View = view) => {
    setView(mode);
    hasRun.current = true;
    setPreviewedNodeId(selectedNodeId ?? null);
    const requestId = ++requestIdRef.current;
    preview.mutate(
      {
        node_id: selectedNodeId ?? undefined,
        limit: mode === "chart" ? CHART_SAMPLE_LIMIT : 50,
        profile: mode === "profile",
      },
      {
        onSettled: () => {
          // The selected node moved on before this response came back — drop it
          // instead of letting it repopulate the panel for the wrong node.
          if (requestId !== requestIdRef.current) {
            preview.reset();
          }
        },
      },
    );
  };

  return (
    <div className="flex h-full flex-col border-t border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Data Preview</h3>
          {previewedNodeId !== undefined ? (
            <span
              className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
              title="The node whose output is shown below"
            >
              {previewedNodeLabel ? `Node: ${previewedNodeLabel}` : "Whole flow"}
            </span>
          ) : (
            selectedNodeLabel && (
              <span className="text-xs text-muted-foreground">
                up to "{selectedNodeLabel}"
              </span>
            )
          )}
          {dirty && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              previews the last saved version
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => runPreview("table")}
            disabled={preview.isPending}
          >
            {preview.isPending && view === "table" ? "Previewing…" : "Run preview"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runPreview("profile")}
            disabled={preview.isPending}
          >
            {preview.isPending && view === "profile" ? "Profiling…" : "Profile"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runPreview("chart")}
            disabled={preview.isPending}
          >
            {preview.isPending && view === "chart" ? "Charting…" : "Chart"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {preview.isError && (
          <div className="m-3 flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0">
              <p className="font-medium">
                {previewedNodeLabel
                  ? `Preview failed at "${previewedNodeLabel}"`
                  : "Preview failed"}
              </p>
              <p className="mt-0.5 break-words">
                {friendlyErrorMessage(preview.error, "The preview couldn't be generated.")}
              </p>
              {dirty && (
                <p className="mt-1 text-xs text-destructive/80">
                  Note: previews run the last saved version of the flow — if you just fixed
                  this, save and preview again.
                </p>
              )}
            </div>
          </div>
        )}
        {preview.data ? (
          <>
            <div className="px-3 py-1 text-xs text-muted-foreground">
              {preview.data.row_count} rows
              {preview.data.truncated && " (truncated)"}
            </div>
            {view === "profile" && preview.data.profile ? (
              <ColumnProfileList profile={preview.data.profile} />
            ) : view === "chart" ? (
              // Keyed by the schema: previewing a node with different columns
              // remounts the chart controls so stale column picks (from the
              // previous node) can't silently chart the wrong columns.
              <ChartView
                key={preview.data.columns.join("\u0000")}
                columns={preview.data.columns}
                rows={preview.data.rows}
              />
            ) : (
              <DataTable columns={preview.data.columns} rows={preview.data.rows} />
            )}
          </>
        ) : (
          !preview.isError && (
            <p className="p-3 text-sm text-muted-foreground">
              Save the flow, then run a preview. Select a node to preview its
              output, or preview the whole flow.
            </p>
          )
        )}
      </div>
    </div>
  );
}

/**
 * Renders a chart for the selected node from its preview sample. Picking the
 * chart type and columns is purely client-side over the already-fetched rows —
 * no re-fetch — so it stays snappy. The rows are a sample (see the caption).
 */
function ChartView({
  columns,
  rows,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
}) {
  const meta = useMemo(() => buildColumnMeta(rows, columns), [rows, columns]);

  const [type, setType] = useState("histogramChart");
  const [bins, setBins] = useState(20);
  const [aggregate, setAggregate] = useState<Aggregate>("sum");
  // Column picks per role — initialized (and re-picked on type change) via
  // chartDefaults, which chooses columns that fit the chart's roles instead of
  // "first alphabetical". ChartView is remounted (keyed) when the previewed
  // schema changes, so these never go stale across nodes.
  const [sel, setSel] = useState<ChartDefaults>(() => chartDefaults("histogramChart", meta));

  const handleTypeChange = (newType: string) => {
    setType(newType);
    const defaults = chartDefaults(newType, meta);
    setSel((prev) => ({ ...prev, ...defaults }));
    if (defaults.aggregate) setAggregate(defaults.aggregate);
  };

  const setRole = (role: keyof ChartDefaults) => (value: string) =>
    setSel((prev) => ({ ...prev, [role]: value }));

  // Guard against a pick that no longer exists; the placeholder then asks for one.
  const valid = (c?: string) => (c && columns.includes(c) ? c : "");
  const col = valid(sel.column);
  const xCol = valid(sel.x);
  const yCol = valid(sel.y);
  const groupCol = valid(sel.group);

  const config: Record<string, unknown> = (() => {
    switch (type) {
      case "histogramChart":
        return { column: col, bins };
      case "valueCounts":
        return { column: col };
      case "boxPlot":
        return { y: yCol, group: groupCol };
      case "correlationHeatmap":
        return { columns: [] };
      case "lineChart":
      case "areaChart":
        return { x: xCol, y: yCol ? [yCol] : [] };
      case "scatterChart":
        return { x: xCol, y: yCol };
      case "barChart":
      case "horizontalBarChart":
      case "pieChart":
        return { x: xCol, y: yCol, aggregate };
      case "stackedBarChart":
        return { x: xCol, y: yCol, group: groupCol, aggregate };
      default:
        return {};
    }
  })();

  const dateFirst = type === "lineChart" || type === "areaChart";

  return (
    <div className="flex flex-col gap-2 px-3 py-2">
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Chart">
          <Select value={type} onChange={(e) => handleTypeChange(e.target.value)} className="h-8">
            {CHART_TYPE_GROUPS.map((g) => (
              <optgroup key={g.label} label={g.label}>
                {g.types.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </Field>

        {SINGLE_COLUMN.has(type) && (
          <Field label="Column">
            <ColumnSelect
              value={col}
              meta={meta}
              order={type === "histogramChart" ? "numeric" : "categorical"}
              onChange={setRole("column")}
            />
          </Field>
        )}

        {type === "histogramChart" && (
          <Field label="Bins">
            <Input
              type="number"
              min={1}
              max={100}
              value={bins}
              onChange={(e) => setBins(clamp(Number(e.target.value) || 1, 1, 100))}
              className="h-8 w-20"
            />
          </Field>
        )}

        {type === "boxPlot" && (
          <>
            <Field label="Value">
              <ColumnSelect value={yCol} meta={meta} order="numeric" onChange={setRole("y")} />
            </Field>
            <Field label="Group by">
              <ColumnSelect
                value={groupCol}
                meta={meta}
                order="categorical"
                allowNone
                onChange={setRole("group")}
              />
            </Field>
          </>
        )}

        {XY.has(type) && (
          <>
            <Field label={CATEGORY_XY.has(type) ? "Category (x)" : "X axis"}>
              <ColumnSelect
                value={xCol}
                meta={meta}
                order={CATEGORY_XY.has(type) ? "categorical" : dateFirst ? "datetime" : "numeric"}
                onChange={setRole("x")}
              />
            </Field>
            <Field label={CATEGORY_XY.has(type) ? "Value (y)" : "Y axis"}>
              <ColumnSelect value={yCol} meta={meta} order="numeric" onChange={setRole("y")} />
            </Field>
          </>
        )}

        {WITH_GROUP.has(type) && (
          <Field label="Group by">
            <ColumnSelect value={groupCol} meta={meta} order="categorical" onChange={setRole("group")} />
          </Field>
        )}

        {WITH_AGGREGATE.has(type) && (
          <Field label="Aggregate">
            <Select
              value={aggregate}
              onChange={(e) => setAggregate(e.target.value as Aggregate)}
              className="h-8"
            >
              {AGGREGATES.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </Field>
        )}

        {type === "correlationHeatmap" && (
          <p className="self-center text-xs text-muted-foreground">
            Uses the numeric columns in the sample.
          </p>
        )}
      </div>

      <ChartPreview type={type} config={config} rows={rows} />

      <p className="text-xs text-muted-foreground">
        Based on a sample of {rows.length} row{rows.length === 1 ? "" : "s"} — not
        the full dataset.
      </p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}

/**
 * Column picker grouped by data kind, with the group that fits the current
 * role listed first (numeric for measures, text for categories, dates for
 * time axes) so the suitable columns are the easy picks.
 */
function ColumnSelect({
  value,
  meta,
  order,
  allowNone = false,
  onChange,
}: {
  value: string;
  meta: ColumnMeta;
  order: "numeric" | "categorical" | "datetime";
  allowNone?: boolean;
  onChange: (value: string) => void;
}) {
  const groups: { label: string; cols: string[] }[] = [
    { label: "Numeric", cols: meta.numeric },
    { label: "Text", cols: meta.categorical },
    { label: "Date", cols: meta.datetime },
  ];
  const firstIndex = order === "numeric" ? 0 : order === "categorical" ? 1 : 2;
  const ordered = [groups[firstIndex], ...groups.filter((_, i) => i !== firstIndex)];
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)} className="h-8">
      {allowNone && <option value="">(none)</option>}
      {ordered
        .filter((g) => g.cols.length > 0)
        .map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.cols.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </optgroup>
        ))}
    </Select>
  );
}
