import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ColumnMultiSelect, ColumnSelect, Field, OptionalColumnSelect } from "../configFields";
import type { NodeConfigRenderProps } from "./shared";

// Aggregate choices shared by the chart nodes (mirrors backend VALID_AGGREGATES).
const CHART_AGGREGATE_OPTIONS = [
  { value: "sum", label: "Sum" },
  { value: "mean", label: "Mean (average)" },
  { value: "count", label: "Count rows" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
  { value: "median", label: "Median" },
] as const;

/** Optional per-node chart title, shared by every chart node's form. It heads
 *  the run view's chart card and the exported PNG (default: the node label). */
function ChartTitleField({
  value,
  error,
  onChange,
}: {
  value: unknown;
  error?: string;
  onChange: (title: string) => void;
}) {
  return (
    <Field
      label="Chart title (optional)"
      error={error}
      help="Shown above the chart on the run page and as the exported image's heading. Empty = the node's label."
    >
      <Input
        value={typeof value === "string" ? value : ""}
        maxLength={200}
        placeholder="defaults to the node label"
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

/** Config fields for the 8 chart node types, or `undefined` if `type` isn't one. */
export function renderChartConfig(
  type: string,
  { c, errors, set, columns }: NodeConfigRenderProps,
): ReactNode | undefined {
  switch (type) {
    case "chartBar": {
      const isCount = (c.aggregate ?? "sum") === "count";
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field label="Category (x)" error={errors.x} help="One bar per value of this column.">
            <ColumnSelect value={c.x ?? ""} columns={columns} onChange={(v) => set({ x: v })} />
          </Field>
          <Field label="Aggregate" error={errors.aggregate} help="How rows in each category combine into one bar.">
            <Select value={c.aggregate ?? "sum"} onChange={(e) => set({ aggregate: e.target.value })}>
              {CHART_AGGREGATE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          {!isCount && (
            <Field label="Value (y)" error={errors.y} help="The numeric column being aggregated.">
              <ColumnSelect value={c.y ?? ""} columns={columns} onChange={(v) => set({ y: v })} />
            </Field>
          )}
          <Field
            label="Stack by (optional)"
            error={errors.group_by}
            help="Split each bar into stacked segments by this column."
          >
            <OptionalColumnSelect
              value={c.group_by || null}
              columns={columns}
              onChange={(v) => set({ group_by: v ?? "" })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Orientation" error={errors.orientation}>
              <Select
                value={c.orientation ?? "vertical"}
                onChange={(e) => set({ orientation: e.target.value })}
              >
                <option value="vertical">Vertical</option>
                <option value="horizontal">Horizontal</option>
              </Select>
            </Field>
            <Field label="Top categories" error={errors.limit} hint="Default 25, max 50">
              <Input
                type="number"
                min={1}
                max={50}
                value={c.limit ?? ""}
                placeholder="25"
                onChange={(e) => set({ limit: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </Field>
          </div>
        </>
      );
    }

    case "chartLine":
    case "chartArea":
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field
            label="X axis"
            error={errors.x}
            help="The order column — a date or numeric column works best."
          >
            <ColumnSelect value={c.x ?? ""} columns={columns} onChange={(v) => set({ x: v })} />
          </Field>
          <Field label="Values (y)" error={errors.y_columns} hint="Up to 8 series" help="One line per selected column.">
            <ColumnMultiSelect
              value={c.y_columns}
              columns={columns}
              onChange={(v) => set({ y_columns: v })}
            />
          </Field>
          <Field
            label="Aggregate"
            error={errors.aggregate}
            help="Rows sharing the same x value combine with this function."
          >
            <Select value={c.aggregate ?? "mean"} onChange={(e) => set({ aggregate: e.target.value })}>
              {CHART_AGGREGATE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
        </>
      );

    case "chartScatter":
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field label="X column" error={errors.x} help="Numeric column on the horizontal axis.">
            <ColumnSelect value={c.x ?? ""} columns={columns} onChange={(v) => set({ x: v })} />
          </Field>
          <Field label="Y column" error={errors.y} help="Numeric column on the vertical axis.">
            <ColumnSelect value={c.y ?? ""} columns={columns} onChange={(v) => set({ y: v })} />
          </Field>
        </>
      );

    case "chartPie": {
      const isCount = (c.aggregate ?? "count") === "count";
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field label="Category" error={errors.category} help="One slice per value of this column.">
            <ColumnSelect value={c.category ?? ""} columns={columns} onChange={(v) => set({ category: v })} />
          </Field>
          <Field label="Aggregate" error={errors.aggregate} help="How rows in each slice combine.">
            <Select value={c.aggregate ?? "count"} onChange={(e) => set({ aggregate: e.target.value })}>
              {CHART_AGGREGATE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          {!isCount && (
            <Field label="Value" error={errors.value} help="The numeric column being aggregated.">
              <ColumnSelect value={c.value ?? ""} columns={columns} onChange={(v) => set({ value: v })} />
            </Field>
          )}
          <Field label="Top slices" error={errors.limit} hint="Default 6, max 12 — the rest fold into Other">
            <Input
              type="number"
              min={2}
              max={12}
              value={c.limit ?? ""}
              placeholder="6"
              onChange={(e) => set({ limit: e.target.value === "" ? null : Number(e.target.value) })}
            />
          </Field>
        </>
      );
    }

    case "chartHistogram":
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field label="Column" error={errors.column} help="The numeric column whose distribution is shown.">
            <ColumnSelect value={c.column ?? ""} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Bins" error={errors.bins} hint="1–100">
            <Input
              type="number"
              min={1}
              max={100}
              value={c.bins ?? 20}
              onChange={(e) => set({ bins: Math.min(100, Math.max(1, Number(e.target.value) || 1)) })}
            />
          </Field>
        </>
      );

    case "chartBoxPlot":
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field label="Value column" error={errors.column} help="The numeric column summarized by each box.">
            <ColumnSelect value={c.column ?? ""} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field
            label="Group by (optional)"
            error={errors.group_by}
            help="One box per group; largest 12 groups are shown."
          >
            <OptionalColumnSelect
              value={c.group_by || null}
              columns={columns}
              onChange={(v) => set({ group_by: v ?? "" })}
            />
          </Field>
        </>
      );

    case "chartHeatmap":
      return (
        <>
          <ChartTitleField value={c.title} error={errors.title} onChange={(v) => set({ title: v })} />
          <Field
            label="Columns (optional)"
            error={errors.columns}
            hint="Empty = all numeric columns (up to 12)"
            help="Pairwise correlations between these numeric columns."
          >
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
        </>
      );

    default:
      return undefined;
  }
}
