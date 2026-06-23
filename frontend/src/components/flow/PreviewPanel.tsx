import { useMemo, useState } from "react";
import { useFlowPreview } from "@/features/flows/hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/api";
import { ColumnProfileList } from "@/components/data/ColumnProfileList";
import { categoricalColumns, numericColumns, type Aggregate } from "@/lib/chartData";
import { DataTable } from "./DataTable";
import { ChartPreview } from "./ChartPreview";

interface PreviewPanelProps {
  flowId: string;
  onClose: () => void;
}

type View = "table" | "profile" | "chart";

// More rows make the client-side charts meaningful, but it is still a sample.
const CHART_SAMPLE_LIMIT = 500;

const CHART_TYPES: { value: string; label: string }[] = [
  { value: "histogramChart", label: "Histogram" },
  { value: "valueCounts", label: "Value counts" },
  { value: "barChart", label: "Bar" },
  { value: "stackedBarChart", label: "Stacked bar" },
  { value: "pieChart", label: "Pie" },
  { value: "lineChart", label: "Line / time series" },
  { value: "areaChart", label: "Area" },
  { value: "scatterChart", label: "Scatter" },
  { value: "correlationHeatmap", label: "Correlation heatmap" },
];

// Which controls each chart type needs.
const SINGLE_COLUMN = new Set(["histogramChart", "valueCounts"]);
const XY = new Set(["barChart", "stackedBarChart", "pieChart", "lineChart", "areaChart", "scatterChart"]);
const CATEGORY_XY = new Set(["barChart", "stackedBarChart", "pieChart"]);
const WITH_AGGREGATE = new Set(["barChart", "stackedBarChart", "pieChart"]);
const WITH_GROUP = new Set(["stackedBarChart"]);

const AGGREGATES: Aggregate[] = ["sum", "mean", "count", "min", "max"];

export function PreviewPanel({ flowId, onClose }: PreviewPanelProps) {
  const selectedNodeId = useFlowEditorStore((s) => s.selectedNodeId);
  const preview = useFlowPreview(flowId);
  const [view, setView] = useState<View>("table");

  const runPreview = (mode: View = view) => {
    setView(mode);
    preview.mutate({
      node_id: selectedNodeId ?? undefined,
      limit: mode === "chart" ? CHART_SAMPLE_LIMIT : 50,
      profile: mode === "profile",
    });
  };

  return (
    <div className="flex h-full flex-col border-t border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Data Preview</h3>
          {selectedNodeId && (
            <span className="text-xs text-muted-foreground">
              node: {selectedNodeId}
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
          <p className="p-3 text-sm text-destructive">
            {(preview.error as ApiError)?.message ?? "Preview failed."}
          </p>
        )}
        {preview.data ? (
          <>
            <div className="px-3 py-1 text-[11px] text-muted-foreground">
              {preview.data.row_count} rows
              {preview.data.truncated && " (truncated)"}
            </div>
            {view === "profile" && preview.data.profile ? (
              <ColumnProfileList profile={preview.data.profile} />
            ) : view === "chart" ? (
              <ChartView columns={preview.data.columns} rows={preview.data.rows} />
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
  const numCols = useMemo(() => numericColumns(rows, columns), [rows, columns]);
  const catCols = useMemo(() => categoricalColumns(rows, columns), [rows, columns]);
  const numColSet = useMemo(() => new Set(numCols), [numCols]);

  // Initialize to smart defaults for the starting chart type (histogram → numeric col).
  const [type, setType] = useState("histogramChart");
  const [column, setColumn] = useState(() => numericColumns(rows, columns)[0] ?? columns[0] ?? "");
  const [bins, setBins] = useState(20);
  const [x, setX] = useState(() => {
    const cats = categoricalColumns(rows, columns);
    return cats[0] ?? columns[0] ?? "";
  });
  const [y, setY] = useState(() => {
    const nums = numericColumns(rows, columns);
    return nums[0] ?? columns[1] ?? "";
  });
  const [group, setGroup] = useState(() => {
    const cats = categoricalColumns(rows, columns);
    return cats[1] ?? cats[0] ?? columns[2] ?? "";
  });
  const [aggregate, setAggregate] = useState<Aggregate>("sum");

  // When the chart type changes, pre-select columns that match what the chart needs.
  const handleTypeChange = (newType: string) => {
    setType(newType);
    switch (newType) {
      case "histogramChart":
        setColumn(numCols[0] ?? columns[0] ?? "");
        break;
      case "valueCounts":
        setColumn(catCols[0] ?? columns[0] ?? "");
        break;
      case "scatterChart":
        setX(numCols[0] ?? columns[0] ?? "");
        setY(numCols[1] ?? columns[1] ?? "");
        break;
      case "lineChart":
      case "areaChart":
        setX(columns[0] ?? "");
        setY(numCols[0] ?? columns[1] ?? "");
        break;
      case "barChart":
      case "pieChart":
        setX(catCols[0] ?? columns[0] ?? "");
        setY(numCols[0] ?? columns[1] ?? "");
        break;
      case "stackedBarChart":
        setX(catCols[0] ?? columns[0] ?? "");
        setY(numCols[0] ?? columns[1] ?? "");
        setGroup(catCols[1] ?? catCols[0] ?? columns[2] ?? "");
        break;
    }
  };

  // Validated picks — fall back by index so the chart always has something to show.
  const pick = (value: string, fallbackIndex = 0) =>
    value && columns.includes(value) ? value : columns[fallbackIndex] ?? "";
  const col = pick(column);
  const xCol = pick(x);
  const yCol = pick(y, 1);
  const groupCol = pick(group, 2);

  const config: Record<string, unknown> = (() => {
    switch (type) {
      case "histogramChart":
        return { column: col, bins };
      case "valueCounts":
        return { column: col };
      case "correlationHeatmap":
        return { columns: [] };
      case "lineChart":
      case "areaChart":
        return { x: xCol, y: yCol ? [yCol] : [] };
      case "scatterChart":
        return { x: xCol, y: yCol };
      case "barChart":
      case "pieChart":
        return { x: xCol, y: yCol, aggregate };
      case "stackedBarChart":
        return { x: xCol, y: yCol, group: groupCol, aggregate };
      default:
        return {};
    }
  })();

  return (
    <div className="flex flex-col gap-2 px-3 py-2">
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Chart">
          <Select value={type} onChange={(e) => handleTypeChange(e.target.value)}>
            {CHART_TYPES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </Select>
        </Field>

        {SINGLE_COLUMN.has(type) && (
          <Field label="Column">
            <ColumnSelect value={col} columns={columns} numericColSet={numColSet} onChange={setColumn} />
          </Field>
        )}

        {type === "histogramChart" && (
          <Field label="Bins">
            <Input
              type="number"
              min={1}
              value={bins}
              onChange={(e) => setBins(Math.max(1, Number(e.target.value) || 1))}
              className="h-8 w-20"
            />
          </Field>
        )}

        {XY.has(type) && (
          <>
            <Field label={CATEGORY_XY.has(type) ? "Category (x)" : "X axis"}>
              <ColumnSelect value={xCol} columns={columns} numericColSet={numColSet} onChange={setX} />
            </Field>
            <Field label={CATEGORY_XY.has(type) ? "Value (y)" : "Y axis"}>
              <ColumnSelect value={yCol} columns={columns} numericColSet={numColSet} onChange={setY} />
            </Field>
          </>
        )}

        {WITH_GROUP.has(type) && (
          <Field label="Group by">
            <ColumnSelect value={groupCol} columns={columns} numericColSet={numColSet} onChange={setGroup} />
          </Field>
        )}

        {WITH_AGGREGATE.has(type) && (
          <Field label="Aggregate">
            <Select
              value={aggregate}
              onChange={(e) => setAggregate(e.target.value as Aggregate)}
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
          <p className="self-center text-[11px] text-muted-foreground">
            Uses all numeric columns in the sample.
          </p>
        )}
      </div>

      <ChartPreview type={type} config={config} rows={rows} />

      <p className="text-[11px] text-muted-foreground">
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

function ColumnSelect({
  value,
  columns,
  numericColSet,
  onChange,
}: {
  value: string;
  columns: string[];
  numericColSet?: Set<string>;
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)} className="h-8">
      {columns.map((c) => {
        const prefix = numericColSet ? (numericColSet.has(c) ? "# " : "T ") : "";
        return (
          <option key={c} value={c}>
            {prefix}{c}
          </option>
        );
      })}
    </Select>
  );
}
