import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Dataset } from "@/lib/types";
import { EXPRESSION_TEMPLATES } from "@/lib/nodeDocs";
import {
  aggFunctions,
  binMethods,
  dateParts,
  dtypes,
  fillStrategies,
  filterOperators,
  FILTER_OPERATOR_LABELS,
  getConfigSchema,
  conditionOperators,
  conditionValueless,
  joinHows,
  JOIN_HOW_LABELS,
  outlierActions,
  outlierMethods,
  OUTLIER_METHOD_LABELS,
  splitModes,
  stringOperations,
  windowFunctions,
  windowTargetFuncs,
} from "@/lib/validators";
import {
  ColumnKeyedEditor,
  ColumnMultiSelect,
  ColumnSelect,
  CsvListInput,
  DateFormatPicker,
  DelimiterPicker,
  Field,
  KeyValueEditor,
  TagInput,
} from "./configFields";
import { useConnections, useConnectionObjects, useConnectionTables } from "@/features/connections/hooks";
import { MlTrainConfig } from "./MlTrainConfig";

interface NodeConfigFormProps {
  type: string;
  config: Record<string, unknown>;
  datasets: Dataset[];
  /** Columns available on the wire entering this node (for column pickers). */
  columns: string[];
  onChange: (config: Record<string, unknown>) => void;
  onErrors: (hasErrors: boolean) => void;
}

type ErrorMap = Record<string, string>;

// Operators that compare against a value vs. those that don't need one.
const VALUELESS_OPERATORS = new Set(["isnull", "notnull"]);

export function NodeConfigForm({
  type,
  config,
  datasets,
  columns,
  onChange,
  onErrors,
}: NodeConfigFormProps) {
  const [errors, setErrors] = useState<ErrorMap>({});

  // Validate the current config against the node's zod schema.
  useEffect(() => {
    const schema = getConfigSchema(type);
    const result = schema.safeParse(config);
    if (result.success) {
      setErrors({});
      onErrors(false);
    } else {
      const map: ErrorMap = {};
      for (const issue of result.error.issues) {
        const key = issue.path[0]?.toString() ?? "_";
        if (!map[key]) map[key] = issue.message;
      }
      setErrors(map);
      onErrors(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, JSON.stringify(config)]);

  const set = (patch: Record<string, unknown>) => onChange({ ...config, ...patch });
  const c = config as Record<string, any>;

  // Connection data for SQL/storage nodes (hooks must run unconditionally; the
  // table query is disabled unless this is a SQL node with a chosen connection).
  const { data: connections = [] } = useConnections();
  const isSqlNode = type === "sqlInput" || type === "sqlOutput";
  const isStorageInput = type === "storageInput";
  const tablesQuery = useConnectionTables(isSqlNode ? c.connection_id || null : null);
  const objectsQuery = useConnectionObjects(isStorageInput ? c.connection_id || null : null);

  const sqlConnections = connections.filter((cn) => cn.connection_type !== "storage");
  const storageConnections = connections.filter((cn) => cn.connection_type === "storage");

  const FILE_INPUT_SOURCE: Record<string, string> = {
    csvInput: "csv",
    excelInput: "excel",
    parquetInput: "parquet",
    jsonInput: "json",
    textInput: "text",
  };
  if (type in FILE_INPUT_SOURCE) {
    const accepted = FILE_INPUT_SOURCE[type];
    const compatible = datasets.filter((d) => d.source_type === accepted);
    const selected = datasets.find((d) => d.id === c.dataset_id);
    const pinned = (c.dataset_version as number | null | undefined) ?? selected?.latest_version;
    const isOutdated =
      selected != null && pinned != null && pinned < selected.latest_version;

    return (
      <>
        <Field
          label="Dataset"
          error={errors.dataset_id}
          help={`Only ${accepted.toUpperCase()} datasets can be loaded by this node.`}
        >
          <Select
            value={(c.dataset_id as string) ?? ""}
            onChange={(e) => {
              // Default to pinning the chosen dataset's latest version.
              const ds = datasets.find((d) => d.id === e.target.value);
              set({ dataset_id: e.target.value, dataset_version: ds?.latest_version ?? null });
            }}
          >
            <option value="">Select a dataset…</option>
            {compatible.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          {compatible.length === 0 && (
            <p className="text-[11px] text-amber-600">
              No {accepted.toUpperCase()} datasets uploaded yet.
            </p>
          )}
        </Field>

        {selected && (
          <Field
            label="Version"
            help="Pin a specific version so scheduled runs always read the same data. New versions don't affect this flow until you update."
          >
            <Select
              value={String(pinned ?? selected.latest_version)}
              onChange={(e) => set({ dataset_version: Number(e.target.value) })}
            >
              {Array.from({ length: selected.latest_version }, (_, i) => selected.latest_version - i).map(
                (v) => (
                  <option key={v} value={v}>
                    v{v}
                    {v === selected.latest_version ? " (latest)" : ""}
                  </option>
                ),
              )}
            </Select>
            {isOutdated && (
              <p className="flex flex-wrap items-center gap-1 text-[11px] text-amber-600">
                Pinned to v{pinned}; v{selected.latest_version} is now available.
                <button
                  type="button"
                  className="font-medium text-primary underline underline-offset-2"
                  onClick={() => set({ dataset_version: selected.latest_version })}
                >
                  Update to latest
                </button>
              </p>
            )}
          </Field>
        )}
      </>
    );
  }

  switch (type) {
    case "dropNulls":
      return (
        <>
          <Field
            label="Subset (optional)"
            hint="Leave empty to check all columns"
            help="Which columns are checked for nulls."
            error={errors.subset}
          >
            <ColumnMultiSelect value={c.subset} columns={columns} onChange={(v) => set({ subset: v })} />
          </Field>
          <Field label="Drop when" error={errors.how} help="Drop a row if ANY checked column is null, or only when ALL are null.">
            <Select value={c.how ?? "any"} onChange={(e) => set({ how: e.target.value })}>
              <option value="any">any value is null</option>
              <option value="all">all values are null</option>
            </Select>
          </Field>
        </>
      );

    case "fillNulls": {
      const strategy = (c.strategy as string) ?? "constant";
      return (
        <>
          <Field
            label="Strategy"
            error={errors.strategy}
            help="How to fill empty cells: a constant value, or a computed statistic such as the column mean."
          >
            <Select value={strategy} onChange={(e) => set({ strategy: e.target.value })}>
              {fillStrategies.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </Field>
          {strategy === "constant" && (
            <Field label="Fill value" error={errors.value} help="The value written into empty cells.">
              <Input value={c.value ?? ""} onChange={(e) => set({ value: e.target.value })} />
            </Field>
          )}
          <Field
            label="Columns (optional)"
            error={errors.columns}
            hint={
              strategy === "mean" || strategy === "median"
                ? "Empty = all numeric columns"
                : "Empty = all columns"
            }
          >
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
        </>
      );
    }

    case "dropColumns":
      return (
        <Field label="Columns to drop" error={errors.columns} help="These columns are removed from the output.">
          <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
        </Field>
      );

    case "selectColumns":
      return (
        <Field label="Columns to keep" error={errors.columns} help="Only these columns survive; the rest are dropped.">
          <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
        </Field>
      );

    case "renameColumns":
      return (
        <Field label="Rename mapping" error={errors.mapping} help="Map each existing column to its new name.">
          {columns.length ? (
            <ColumnKeyedEditor
              value={c.mapping}
              columns={columns}
              onChange={(v) => set({ mapping: v })}
              defaultValue=""
              renderValue={(val, onValueChange) => (
                <Input
                  className="h-8 w-32"
                  placeholder="new name"
                  value={val}
                  onChange={(e) => onValueChange(e.target.value)}
                />
              )}
            />
          ) : (
            <KeyValueEditor
              value={c.mapping}
              onChange={(v) => set({ mapping: v })}
              keyLabel="old name"
              valueLabel="new name"
            />
          )}
        </Field>
      );

    case "removeDuplicates":
      return (
        <>
          <Field
            label="Subset (optional)"
            error={errors.subset}
            hint="Empty = consider all columns"
            help="Rows are duplicates when these columns match."
          >
            <ColumnMultiSelect value={c.subset} columns={columns} onChange={(v) => set({ subset: v })} />
          </Field>
          <Field label="Keep" error={errors.keep} help="Which duplicate to retain.">
            <Select value={c.keep ?? "first"} onChange={(e) => set({ keep: e.target.value })}>
              <option value="first">first occurrence</option>
              <option value="last">last occurrence</option>
            </Select>
          </Field>
        </>
      );

    case "filterRows": {
      const operator = c.operator ?? "==";
      const needsValue = !VALUELESS_OPERATORS.has(operator);
      const isBetween = operator === "between";
      const isIn = operator === "in";
      return (
        <>
          <Field label="Column" error={errors.column}>
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Operator" error={errors.operator} help="How the column is compared to the value.">
            <Select value={operator} onChange={(e) => set({ operator: e.target.value })}>
              {filterOperators.map((op) => (
                <option key={op} value={op}>
                  {FILTER_OPERATOR_LABELS[op] ?? op}
                </option>
              ))}
            </Select>
          </Field>
          {needsValue && (
            <Field
              label={isBetween ? "From (lower bound)" : "Value"}
              error={errors.value}
              help={isIn ? "Keeps rows whose value matches any item in the list." : undefined}
            >
              {isIn ? (
                <TagInput
                  value={typeof c.value === "string" ? c.value : ""}
                  onChange={(v) => set({ value: v })}
                  placeholder="e.g. red, green, blue"
                />
              ) : (
                <Input value={c.value ?? ""} onChange={(e) => set({ value: e.target.value })} />
              )}
            </Field>
          )}
          {isBetween && (
            <Field label="To (upper bound)" error={errors.value2} help="Rows are kept when the value is between the two bounds (inclusive).">
              <Input value={c.value2 ?? ""} onChange={(e) => set({ value2: e.target.value })} />
            </Field>
          )}
        </>
      );
    }

    case "sortRows":
      return (
        <>
          <Field label="Sort by columns" error={errors.columns} help="Rows are ordered by these columns, in order.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="Order" error={errors.ascending}>
            <Select
              value={c.ascending === false ? "false" : "true"}
              onChange={(e) => set({ ascending: e.target.value === "true" })}
            >
              <option value="true">Ascending</option>
              <option value="false">Descending</option>
            </Select>
          </Field>
          <Field label="Nulls" error={errors.na_position} help="Whether missing values sort to the start or the end.">
            <Select value={c.na_position ?? "last"} onChange={(e) => set({ na_position: e.target.value })}>
              <option value="last">Nulls last</option>
              <option value="first">Nulls first</option>
            </Select>
          </Field>
        </>
      );

    case "castDtypes": {
      const hasDatetime = Object.values((c.casts ?? {}) as Record<string, string>).includes(
        "datetime",
      );
      return (
        <>
          <Field label="Casts" hint="column → type" error={errors.casts} help="Convert each column to the chosen data type.">
            {columns.length ? (
              <ColumnKeyedEditor
                value={c.casts}
                columns={columns}
                onChange={(v) => set({ casts: v })}
                defaultValue="string"
                renderValue={(val, onValueChange) => (
                  <Select
                    className="h-8 w-28"
                    value={val || "string"}
                    onChange={(e) => onValueChange(e.target.value)}
                  >
                    {dtypes.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </Select>
                )}
              />
            ) : (
              <DtypeEditor value={c.casts} columns={columns} onChange={(v) => set({ casts: v })} />
            )}
          </Field>
          <Field label="On bad values" error={errors.errors} help="Raise an error, or coerce unparseable values to null.">
            <Select value={c.errors ?? "raise"} onChange={(e) => set({ errors: e.target.value })}>
              <option value="raise">Raise an error</option>
              <option value="coerce">Set to null (coerce)</option>
            </Select>
          </Field>
          {hasDatetime && (
            <Field
              label="Date format (optional)"
              help="strptime format for datetime casts. Leave empty to auto-detect."
              error={errors.format}
            >
              <DateFormatPicker value={c.format} onChange={(v) => set({ format: v })} />
            </Field>
          )}
        </>
      );
    }

    case "limitRows":
      return (
        <>
          <Field label="Number of rows" error={errors.n} help="How many rows to keep.">
            <Input type="number" value={c.n ?? 100} onChange={(e) => set({ n: Number(e.target.value) })} />
          </Field>
          <Field label="Offset (optional)" error={errors.offset} hint="Skip this many rows first" help="Rows to skip before keeping N — useful for paging.">
            <Input type="number" value={c.offset ?? 0} onChange={(e) => set({ offset: Number(e.target.value) })} />
          </Field>
        </>
      );

    case "replaceValues":
      return (
        <>
          <Field label="Column" error={errors.column}>
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Replace" error={errors.to_replace} help="The value (or regex pattern) to look for.">
            <Input value={c.to_replace ?? ""} onChange={(e) => set({ to_replace: e.target.value })} />
          </Field>
          <Field label="With" error={errors.value} help="The value to substitute in.">
            <Input value={c.value ?? ""} onChange={(e) => set({ value: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={!!c.regex}
              onChange={(e) => set({ regex: e.target.checked })}
            />
            Treat “Replace” as a regular expression
          </label>
        </>
      );

    case "stringTransform": {
      const op = (c.operation as string) ?? "lower";
      const OP_LABELS: Record<string, string> = {
        lower: "Lowercase",
        upper: "Uppercase",
        strip: "Strip spaces",
        title: "Title Case",
        capitalize: "Capitalize",
        len: "Count chars",
        replace: "Find & Replace",
        pad: "Pad width",
      };
      return (
        <>
          <Field label="Column" error={errors.column}>
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Operation" error={errors.operation} help="Text transformation applied to every value in the column.">
            <div className="grid grid-cols-2 gap-1">
              {stringOperations.map((o) => {
                const on = op === o;
                return (
                  <button
                    key={o}
                    type="button"
                    onClick={() => set({ operation: o })}
                    className={cn(
                      "rounded border px-2 py-1 text-left text-[11px] font-medium transition-colors",
                      on
                        ? "border-primary bg-primary text-primary-foreground shadow-sm"
                        : "border-border bg-background text-slate-600 hover:border-primary/50 hover:bg-muted",
                    )}
                  >
                    {OP_LABELS[o] ?? o}
                  </button>
                );
              })}
            </div>
          </Field>
          {op === "replace" && (
            <>
              <Field label="Find" error={errors.find} help="Substring to find (replaced literally).">
                <Input value={c.find ?? ""} onChange={(e) => set({ find: e.target.value })} />
              </Field>
              <Field label="Replace with" error={errors.replace_with}>
                <Input value={c.replace_with ?? ""} onChange={(e) => set({ replace_with: e.target.value })} />
              </Field>
            </>
          )}
          {op === "pad" && (
            <>
              <Field label="Target width" error={errors.width} help="Pad each value up to this many characters.">
                <Input type="number" value={c.width ?? 1} onChange={(e) => set({ width: Number(e.target.value) })} />
              </Field>
              <Field label="Fill character" error={errors.fill_char}>
                <Input value={c.fill_char ?? " "} maxLength={1} onChange={(e) => set({ fill_char: e.target.value })} />
              </Field>
              <Field label="Pad side" error={errors.side}>
                <Select value={c.side ?? "left"} onChange={(e) => set({ side: e.target.value })}>
                  <option value="left">Left</option>
                  <option value="right">Right</option>
                </Select>
              </Field>
            </>
          )}
        </>
      );
    }

    case "calculatedColumn":
      return (
        <>
          <Field label="New column name" error={errors.column_name}>
            <Input value={c.column_name ?? ""} onChange={(e) => set({ column_name: e.target.value })} />
          </Field>
          <Field label="Common formula" help="Pick a starting point — it fills the formula below, which you can then edit.">
            <Select
              value=""
              onChange={(e) => {
                const t = EXPRESSION_TEMPLATES.find((t) => t.label === e.target.value);
                if (t) set({ expression: t.build(columns) });
              }}
            >
              <option value="">Choose a template…</option>
              {EXPRESSION_TEMPLATES.map((t) => (
                <option key={t.label} value={t.label}>
                  {t.label} · {t.description}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Formula (advanced)"
            hint={columns.length ? `Columns: ${columns.join(", ")}` : "e.g. price * quantity"}
            help="A pandas expression evaluated per row. Reference columns by name; arithmetic (+ - * /) and comparisons (>, <, ==) are supported."
            error={errors.expression}
          >
            <Input value={c.expression ?? ""} onChange={(e) => set({ expression: e.target.value })} />
          </Field>
        </>
      );

    case "groupByAggregate":
      return (
        <>
          <Field label="Group by columns" error={errors.group_by} help="Rows are grouped by unique combinations of these columns.">
            <ColumnMultiSelect value={c.group_by} columns={columns} onChange={(v) => set({ group_by: v })} />
          </Field>
          <Field
            label="Aggregations"
            hint="column → aggregation"
            help="For each column, choose how to combine the grouped rows."
            error={errors.aggregations}
          >
            {columns.length ? (
              <ColumnKeyedEditor
                value={c.aggregations}
                columns={columns}
                onChange={(v) => set({ aggregations: v })}
                defaultValue="sum"
                renderValue={(val, onValueChange) => (
                  <Select
                    className="h-8 w-28"
                    value={val || "sum"}
                    onChange={(e) => onValueChange(e.target.value)}
                  >
                    {aggFunctions.map((a) => (
                      <option key={a} value={a}>
                        {a}
                      </option>
                    ))}
                  </Select>
                )}
              />
            ) : (
              <KeyValueEditor
                value={c.aggregations}
                onChange={(v) => set({ aggregations: v })}
                keyLabel="column"
                valueLabel="agg"
              />
            )}
          </Field>
        </>
      );

    case "join": {
      const splitKeys = !!(c.left_on?.length || c.right_on?.length);
      return (
        <>
          <Field label="Join type" error={errors.how} help="Which rows to keep when keys don't match on both sides.">
            <Select value={c.how ?? "inner"} onChange={(e) => set({ how: e.target.value })}>
              {joinHows.map((h) => (
                <option key={h} value={h}>
                  {JOIN_HOW_LABELS[h] ?? h}
                </option>
              ))}
            </Select>
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={splitKeys}
              onChange={(e) =>
                e.target.checked
                  ? set({ left_on: [], right_on: [], on: "" })
                  : set({ left_on: [], right_on: [] })
              }
            />
            Keys have different names on each side
          </label>
          {splitKeys ? (
            <>
              <Field label="Left key(s)" error={errors.left_on} help="Key column(s) from the left input.">
                <ColumnMultiSelect value={c.left_on} columns={columns} onChange={(v) => set({ left_on: v })} />
              </Field>
              <Field label="Right key(s)" error={errors.right_on} help="Key column(s) from the right input, matched positionally to the left keys.">
                <ColumnMultiSelect value={c.right_on} columns={columns} onChange={(v) => set({ right_on: v })} />
              </Field>
            </>
          ) : (
            <Field label="Join on" error={errors.on} help="Column(s) that must match between the left and right inputs.">
              <ColumnMultiSelect
                value={Array.isArray(c.on) ? c.on : c.on ? [c.on] : []}
                columns={columns}
                onChange={(v) => set({ on: v })}
              />
            </Field>
          )}
        </>
      );
    }

    case "concatRows":
      return (
        <p className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
          Stacks all incoming dataframes vertically. Connect two or more inputs —
          no configuration required.
        </p>
      );

    case "sampleRows": {
      const useFrac = c.frac != null && c.frac !== "";
      return (
        <>
          <Field label="Sample by" help="Take a fixed number of rows, or a fraction of the table.">
            <Select
              value={useFrac ? "frac" : "n"}
              onChange={(e) =>
                e.target.value === "frac"
                  ? set({ frac: 0.1, n: undefined })
                  : set({ n: 100, frac: undefined })
              }
            >
              <option value="n">Row count</option>
              <option value="frac">Fraction</option>
            </Select>
          </Field>
          {useFrac ? (
            <Field label="Fraction" error={errors.frac} hint="0–1, e.g. 0.1 = 10%">
              <Input type="number" step="0.01" value={c.frac ?? 0.1} onChange={(e) => set({ frac: Number(e.target.value) })} />
            </Field>
          ) : (
            <Field label="Number of rows" error={errors.n}>
              <Input type="number" value={c.n ?? 100} onChange={(e) => set({ n: Number(e.target.value) })} />
            </Field>
          )}
          <Field label="Random seed (optional)" error={errors.seed} help="Set for reproducible samples across runs.">
            <Input
              type="number"
              value={c.seed ?? ""}
              onChange={(e) => set({ seed: e.target.value === "" ? null : Number(e.target.value) })}
            />
          </Field>
        </>
      );
    }

    case "removeOutliers": {
      const method = (c.method as string) ?? "iqr";
      return (
        <>
          <Field label="Columns" error={errors.columns} help="Numeric columns to check for outliers.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="Method" error={errors.method} help="IQR and z-score detect statistical spread; percentile clips to a custom range.">
            <Select value={method} onChange={(e) => set({ method: e.target.value })}>
              {outlierMethods.map((m) => (
                <option key={m} value={m}>
                  {OUTLIER_METHOD_LABELS[m] ?? m}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Action" error={errors.action} help="Drop offending rows, or clip values to the bounds.">
            <Select value={c.action ?? "drop"} onChange={(e) => set({ action: e.target.value })}>
              {outlierActions.map((a) => (
                <option key={a} value={a}>
                  {a === "drop" ? "Drop rows" : "Clip to bounds"}
                </option>
              ))}
            </Select>
          </Field>
          {method === "iqr" && (
            <Field label="IQR factor" error={errors.factor} hint="Bounds = Q1/Q3 ± factor × IQR (default 1.5)">
              <Input type="number" step="0.1" value={c.factor ?? 1.5} onChange={(e) => set({ factor: Number(e.target.value) })} />
            </Field>
          )}
          {method === "zscore" && (
            <Field label="Z-score threshold" error={errors.threshold} hint="Standard deviations (default 3)">
              <Input type="number" step="0.1" value={c.threshold ?? 3} onChange={(e) => set({ threshold: Number(e.target.value) })} />
            </Field>
          )}
          {method === "percentile" && (
            <>
              <Field label="Lower percentile" error={errors.lower} hint="0–100">
                <Input type="number" value={c.lower ?? 1} onChange={(e) => set({ lower: Number(e.target.value) })} />
              </Field>
              <Field label="Upper percentile" error={errors.upper} hint="0–100">
                <Input type="number" value={c.upper ?? 99} onChange={(e) => set({ upper: Number(e.target.value) })} />
              </Field>
            </>
          )}
        </>
      );
    }

    case "roundNumbers":
      return (
        <>
          <Field label="Columns" error={errors.columns} help="Numeric columns to round.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="Decimals" error={errors.decimals} help="Number of decimal places (0 = whole numbers).">
            <Input type="number" value={c.decimals ?? 0} onChange={(e) => set({ decimals: Number(e.target.value) })} />
          </Field>
        </>
      );

    case "binColumn":
      return (
        <>
          <Field label="Column" error={errors.column} help="The numeric column to bucket.">
            <ColumnSelect
              value={c.column}
              columns={columns}
              onChange={(v) => {
                const patch: Record<string, unknown> = { column: v };
                if (!c.new_column) patch.new_column = `${v}_bin`;
                set(patch);
              }}
            />
          </Field>
          <Field label="New column" error={errors.new_column} help="Name for the bucket label column that's added.">
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="bucket" />
          </Field>
          <Field label="Method" error={errors.method} help="Equal-width splits the value range; quantile makes equally-sized groups.">
            <Select value={c.method ?? "equalwidth"} onChange={(e) => set({ method: e.target.value })}>
              {binMethods.map((m) => (
                <option key={m} value={m}>
                  {m === "equalwidth" ? "Equal width" : "Quantile"}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Number of bins" error={errors.bins}>
            <Input type="number" value={c.bins ?? 4} onChange={(e) => set({ bins: Number(e.target.value) })} />
          </Field>
        </>
      );

    case "extractDateParts": {
      const selected = (c.parts as string[]) ?? [];
      const toggle = (p: string) =>
        set({ parts: selected.includes(p) ? selected.filter((x) => x !== p) : [...selected, p] });
      return (
        <>
          <Field label="Date column" error={errors.column} help="A datetime (or parseable date string) column.">
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Parts to extract" error={errors.parts} help="Each chosen part becomes a new column (e.g. date_year).">
            <div className="flex flex-wrap gap-1.5">
              {dateParts.map((p) => {
                const on = selected.includes(p);
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => toggle(p)}
                    className={cn(
                      "rounded-full border px-2.5 py-0.5 text-xs font-medium transition-all",
                      on
                        ? "border-primary bg-primary text-primary-foreground shadow-sm"
                        : "border-border bg-background text-slate-600 hover:border-primary/50 hover:bg-muted",
                    )}
                  >
                    {p}
                  </button>
                );
              })}
            </div>
          </Field>
        </>
      );
    }

    case "unpivot":
      return (
        <>
          <Field label="Keep columns (id)" error={errors.id_vars} help="Identifier columns kept on every output row.">
            <ColumnMultiSelect value={c.id_vars} columns={columns} onChange={(v) => set({ id_vars: v })} />
          </Field>
          <Field label="Unpivot columns (optional)" error={errors.value_vars} hint="Empty = all remaining columns" help="Columns folded into the key/value pair.">
            <ColumnMultiSelect value={c.value_vars} columns={columns} onChange={(v) => set({ value_vars: v })} />
          </Field>
          <Field label="Variable column name" error={errors.var_name}>
            <Input value={c.var_name ?? "variable"} onChange={(e) => set({ var_name: e.target.value })} />
          </Field>
          <Field label="Value column name" error={errors.value_name}>
            <Input value={c.value_name ?? "value"} onChange={(e) => set({ value_name: e.target.value })} />
          </Field>
        </>
      );

    case "pivot":
      return (
        <>
          <Field label="Index columns" error={errors.index} help="Row groups — these become the output's row identity.">
            <ColumnMultiSelect value={c.index} columns={columns} onChange={(v) => set({ index: v })} />
          </Field>
          <Field label="Columns from" error={errors.columns} help="The column whose distinct values become new columns.">
            <ColumnSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="Values from" error={errors.values} help="The column to aggregate into each cell.">
            <ColumnSelect value={c.values} columns={columns} onChange={(v) => set({ values: v })} />
          </Field>
          <Field label="Aggregation" error={errors.aggfunc} help="How to combine values that fall in the same cell.">
            <Select value={c.aggfunc ?? "sum"} onChange={(e) => set({ aggfunc: e.target.value })}>
              {aggFunctions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </Field>
        </>
      );

    case "splitColumn": {
      const mode = (c.mode as string) ?? "delimiter";
      return (
        <>
          <Field label="Column" error={errors.column} help="The text column to split.">
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Split by" error={errors.mode} help="A literal delimiter, or a regex whose capture groups become columns.">
            <Select value={mode} onChange={(e) => set({ mode: e.target.value })}>
              {splitModes.map((m) => (
                <option key={m} value={m}>
                  {m === "delimiter" ? "Delimiter" : "Regex groups"}
                </option>
              ))}
            </Select>
          </Field>
          {mode === "delimiter" ? (
            <Field label="Delimiter" error={errors.delimiter} help="Character or text to split on.">
              <DelimiterPicker value={c.delimiter} onChange={(v) => set({ delimiter: v })} />
            </Field>
          ) : (
            <Field label="Pattern" error={errors.pattern} help="Regex with capture groups; group 1 → first column, etc.">
              <Input value={c.pattern ?? ""} onChange={(e) => set({ pattern: e.target.value })} placeholder="(\d+)-(\d+)" />
            </Field>
          )}
          <Field
            label="New columns"
            error={errors.into}
            hint="Comma-separated names, in order"
            help="Each split piece (or capture group) is written to these columns."
          >
            <CsvListInput value={c.into} onChange={(v) => set({ into: v })} placeholder="first, last" />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={c.keep_original !== false}
              onChange={(e) => set({ keep_original: e.target.checked })}
            />
            Keep the original column
          </label>
        </>
      );
    }

    case "parseDates":
      return (
        <>
          <Field label="Columns" error={errors.columns} help="Text columns to parse into datetimes.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field
            label="Date format (optional)"
            help="strptime format. Leave empty to auto-detect."
            error={errors.format}
          >
            <DateFormatPicker value={c.format} onChange={(v) => set({ format: v })} />
          </Field>
          <Field label="On bad values" error={errors.errors} help="Raise an error, or coerce unparseable values to null.">
            <Select value={c.errors ?? "coerce"} onChange={(e) => set({ errors: e.target.value })}>
              <option value="coerce">Set to null (coerce)</option>
              <option value="raise">Raise an error</option>
            </Select>
          </Field>
        </>
      );

    case "mapValues":
      return (
        <>
          <Field label="Column" error={errors.column} help="The column whose values are mapped.">
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field
            label="New column (optional)"
            error={errors.new_column}
            hint="Empty = overwrite the source column"
            help="Where the mapped result is written."
          >
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="mapped" />
          </Field>
          <Field label="Mapping" hint="value → becomes" error={errors.mapping} help="Each listed value is replaced with its mapped value.">
            <KeyValueEditor
              value={c.mapping}
              onChange={(v) => set({ mapping: v })}
              keyLabel="value"
              valueLabel="becomes"
            />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={!!c.use_default}
              onChange={(e) => set({ use_default: e.target.checked })}
            />
            Replace unmapped values with a default
          </label>
          {c.use_default && (
            <Field label="Default value" error={errors.default} help="Used for any value not listed in the mapping.">
              <Input value={c.default ?? ""} onChange={(e) => set({ default: e.target.value })} />
            </Field>
          )}
        </>
      );

    case "windowFunction": {
      const fn = (c.function as string) ?? "row_number";
      const needsTarget = windowTargetFuncs.has(fn);
      const isLagLead = fn === "lag" || fn === "lead";
      return (
        <>
          <Field label="Function" error={errors.function} help="row_number/rank order rows; cumsum/cummax/cummin run totals; lag/lead shift values.">
            <Select
              value={fn}
              onChange={(e) => {
                const patch: Record<string, unknown> = { function: e.target.value };
                if (!c.new_column) patch.new_column = e.target.value;
                set(patch);
              }}
            >
              {windowFunctions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="New column" error={errors.new_column} help="Name for the column the window result is written to.">
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="rank" />
          </Field>
          <Field label="Partition by (optional)" error={errors.partition_by} hint="Empty = whole table" help="Restart the window within each group of these columns.">
            <ColumnMultiSelect value={c.partition_by} columns={columns} onChange={(v) => set({ partition_by: v })} />
          </Field>
          <Field label="Order by" error={errors.order_by} help="Row order within each partition (required for ranking, lag/lead, and running totals to be meaningful).">
            <ColumnMultiSelect value={c.order_by} columns={columns} onChange={(v) => set({ order_by: v })} />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={!!c.descending}
              onChange={(e) => set({ descending: e.target.checked })}
            />
            Order descending
          </label>
          {needsTarget && (
            <Field label="Target column" error={errors.target} help="The value column the function operates on.">
              <ColumnSelect value={c.target} columns={columns} onChange={(v) => set({ target: v })} />
            </Field>
          )}
          {isLagLead && (
            <Field label="Offset" error={errors.offset} help="How many rows to shift (default 1).">
              <Input type="number" value={c.offset ?? 1} onChange={(e) => set({ offset: Number(e.target.value) })} />
            </Field>
          )}
        </>
      );
    }

    case "conditionalColumn": {
      const rules = (c.rules as Record<string, any>[]) ?? [];
      // A rule is either the new shape ({ match, conditions[], result }) or a
      // legacy flat rule ({ column, operator, value, result }); normalize the
      // conditions for display and migrate to the new shape on any edit.
      const condsOf = (r: Record<string, any>): Record<string, any>[] =>
        Array.isArray(r.conditions) && r.conditions.length
          ? r.conditions
          : [{ column: r.column ?? "", operator: r.operator ?? "==", value: r.value ?? "" }];
      const matchOf = (r: Record<string, any>): "all" | "any" =>
        r.match === "any" ? "any" : "all";
      const updateRule = (i: number, patch: Record<string, unknown>) =>
        set({
          rules: rules.map((r, idx) =>
            idx === i
              ? { match: matchOf(r), conditions: condsOf(r), result: r.result ?? "", ...patch }
              : r,
          ),
        });
      const updateCondition = (i: number, j: number, patch: Record<string, unknown>) =>
        updateRule(i, {
          conditions: condsOf(rules[i]).map((cn, k) => (k === j ? { ...cn, ...patch } : cn)),
        });
      const addCondition = (i: number) =>
        updateRule(i, {
          conditions: [...condsOf(rules[i]), { column: "", operator: "==", value: "" }],
        });
      const removeCondition = (i: number, j: number) =>
        updateRule(i, { conditions: condsOf(rules[i]).filter((_, k) => k !== j) });
      const addRule = () =>
        set({
          rules: [
            ...rules,
            { match: "all", conditions: [{ column: "", operator: "==", value: "" }], result: "" },
          ],
        });
      const removeRule = (i: number) => set({ rules: rules.filter((_, idx) => idx !== i) });
      return (
        <>
          <Field label="New column" error={errors.new_column} help="Name for the column built from the rules below.">
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="tier" />
          </Field>
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-slate-600">Rules (first match wins)</span>
            {rules.map((r, i) => {
              const conditions = condsOf(r);
              return (
                <div key={i} className="flex flex-col gap-1.5 rounded-md border border-border p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      if
                    </span>
                    {conditions.length > 1 && (
                      <Select
                        className="h-7 w-36 text-[11px]"
                        value={matchOf(r)}
                        onChange={(e) => updateRule(i, { match: e.target.value })}
                      >
                        <option value="all">match ALL (AND)</option>
                        <option value="any">match ANY (OR)</option>
                      </Select>
                    )}
                    <button
                      type="button"
                      onClick={() => removeRule(i)}
                      className="ml-auto text-[11px] text-muted-foreground hover:text-destructive"
                    >
                      remove
                    </button>
                  </div>
                  {conditions.map((cn, j) => {
                    const valueless = conditionValueless.has(cn.operator);
                    return (
                      <div key={j} className="flex flex-col gap-1">
                        {j > 0 && (
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                            {matchOf(r) === "any" ? "or" : "and"}
                          </span>
                        )}
                        <div className="flex items-start gap-1">
                          <div className="flex flex-1 flex-col gap-1">
                            <ColumnSelect
                              value={cn.column}
                              columns={columns}
                              onChange={(v) => updateCondition(i, j, { column: v })}
                            />
                            <div className="flex gap-1">
                              <Select
                                className="h-8 w-28"
                                value={cn.operator ?? "=="}
                                onChange={(e) => updateCondition(i, j, { operator: e.target.value })}
                              >
                                {conditionOperators.map((op) => (
                                  <option key={op} value={op}>
                                    {op}
                                  </option>
                                ))}
                              </Select>
                              {!valueless && (
                                <Input
                                  className="h-8"
                                  placeholder="value"
                                  value={cn.value ?? ""}
                                  onChange={(e) => updateCondition(i, j, { value: e.target.value })}
                                />
                              )}
                            </div>
                          </div>
                          {conditions.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeCondition(i, j)}
                              title="Remove condition"
                              className="mt-1 px-1 text-[11px] text-muted-foreground hover:text-destructive"
                            >
                              ×
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => addCondition(i)}
                    className="self-start text-[11px] font-medium text-primary hover:underline"
                  >
                    + add condition
                  </button>
                  <Input
                    placeholder="then result →"
                    value={r.result ?? ""}
                    onChange={(e) => updateRule(i, { result: e.target.value })}
                  />
                </div>
              );
            })}
            <button
              type="button"
              onClick={addRule}
              className="rounded-md border border-dashed border-border px-2 py-1.5 text-xs font-medium text-slate-600 hover:border-primary/50 hover:bg-muted"
            >
              + Add rule
            </button>
            {errors.rules && (
              <p className="text-[11px] font-medium text-destructive">{errors.rules}</p>
            )}
          </div>
          <Field label="Default (else)" error={errors.default} help="Value used when no rule matches.">
            <Input value={c.default ?? ""} onChange={(e) => set({ default: e.target.value })} placeholder="other" />
          </Field>
        </>
      );
    }

    case "sqlInput": {
      const mode = (c.mode as string) ?? "table";
      const currentTable = c.schema ? `${c.schema}.${c.table}` : c.table;
      const connectionPicker = (
        <Field label="Connection" error={errors.connection_id} help="Reusable database connection (manage these on the Connections page).">
          <Select
            value={c.connection_id ?? ""}
            onChange={(e) => set({ connection_id: e.target.value, table: "", schema: null })}
          >
            <option value="">Select a connection…</option>
            {sqlConnections.map((cn) => (
              <option key={cn.id} value={cn.id}>
                {cn.name}
              </option>
            ))}
          </Select>
          {sqlConnections.length === 0 && (
            <p className="text-[11px] text-amber-600">
              No database connections yet — add one on the Connections page.
            </p>
          )}
        </Field>
      );
      return (
        <>
          {connectionPicker}
          <Field label="Source" help="Read a whole table, or run a custom SQL query.">
            <Select value={mode} onChange={(e) => set({ mode: e.target.value })}>
              <option value="table">Table</option>
              <option value="query">Custom SQL</option>
            </Select>
          </Field>
          {mode === "query" ? (
            <Field label="SQL query" error={errors.query} help="Runs against the selected connection.">
              <textarea
                className="min-h-[80px] w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={c.query ?? ""}
                onChange={(e) => set({ query: e.target.value })}
                placeholder="SELECT * FROM orders WHERE status = 'paid'"
              />
            </Field>
          ) : (
            <Field label="Table" error={errors.table} help="Tables are listed from the connection.">
              {tablesQuery.data && tablesQuery.data.length > 0 ? (
                <Select
                  value={currentTable ?? ""}
                  onChange={(e) => {
                    const t = tablesQuery.data!.find((x) => x.qualified === e.target.value);
                    set({ table: t?.name ?? e.target.value, schema: t?.schema_name ?? null });
                  }}
                >
                  <option value="">Select a table…</option>
                  {tablesQuery.data.map((t) => (
                    <option key={t.qualified} value={t.qualified}>
                      {t.qualified}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  value={c.table ?? ""}
                  onChange={(e) => set({ table: e.target.value })}
                  placeholder="table name"
                />
              )}
              {tablesQuery.isFetching && (
                <p className="text-[11px] text-muted-foreground">Loading tables…</p>
              )}
              {tablesQuery.isError && (
                <p className="text-[11px] text-amber-600">
                  Couldn't list tables — type the name manually.
                </p>
              )}
            </Field>
          )}
        </>
      );
    }

    case "sqlOutput":
      return (
        <>
          <Field label="Connection" error={errors.connection_id} help="Where to write the result.">
            <Select
              value={c.connection_id ?? ""}
              onChange={(e) => set({ connection_id: e.target.value })}
            >
              <option value="">Select a connection…</option>
              {sqlConnections.map((cn) => (
                <option key={cn.id} value={cn.id}>
                  {cn.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Target table" error={errors.table} help="The table (or collection) to write to.">
            <Input
              value={c.table ?? ""}
              onChange={(e) => set({ table: e.target.value })}
              placeholder="cleaned_orders"
            />
          </Field>
          <Field label="If table exists" error={errors.if_exists} help="What to do when the target already exists.">
            <Select value={c.if_exists ?? "replace"} onChange={(e) => set({ if_exists: e.target.value })}>
              <option value="replace">Replace</option>
              <option value="append">Append</option>
              <option value="fail">Fail</option>
            </Select>
          </Field>
        </>
      );

    case "storageInput": {
      const SUPPORTED_EXTS = new Set(["csv", "xlsx", "xls", "parquet", "json", "txt"]);
      const allObjects = objectsQuery.data ?? [];
      const objects = allObjects.filter((obj) => {
        const ext = obj.split(".").pop()?.toLowerCase() ?? "";
        return SUPPORTED_EXTS.has(ext);
      });
      const selectedPath = (c.path as string) ?? "";
      const formatFromPath = (p: string): string => {
        const ext = p.split(".").pop()?.toLowerCase();
        if (ext === "parquet") return "parquet";
        if (ext === "xlsx" || ext === "xls") return "excel";
        if (ext === "json") return "json";
        if (ext === "txt") return "text";
        return "csv";
      };
      return (
        <>
          <Field label="Storage connection" error={errors.connection_id} help="S3, Azure Blob, GCS, or local folder (manage on the Connections page).">
            <Select
              value={c.connection_id ?? ""}
              onChange={(e) => set({ connection_id: e.target.value, path: "", format: "csv" })}
            >
              <option value="">Select a storage connection…</option>
              {storageConnections.map((cn) => (
                <option key={cn.id} value={cn.id}>
                  {cn.name}
                </option>
              ))}
            </Select>
            {storageConnections.length === 0 && (
              <p className="text-[11px] text-amber-600">
                No storage connections yet — add one on the Connections page.
              </p>
            )}
          </Field>
          {c.connection_id && (
            <Field
              label="File"
              error={errors.path}
              help="Select a file from the storage connection, or type a path manually."
            >
              {objectsQuery.isFetching ? (
                <p className="text-[11px] text-muted-foreground">Loading files…</p>
              ) : objects.length > 0 ? (
                <div className="flex flex-col gap-1">
                  <div className="max-h-40 overflow-y-auto rounded-md border border-input bg-background">
                    {objects.map((obj) => (
                      <button
                        key={obj}
                        type="button"
                        onClick={() => set({ path: obj, format: formatFromPath(obj) })}
                        className={cn(
                          "w-full px-2 py-1 text-left text-[11px] font-mono hover:bg-muted",
                          selectedPath === obj && "bg-primary/10 font-semibold text-primary",
                        )}
                      >
                        {obj}
                      </button>
                    ))}
                  </div>
                  {selectedPath && !objects.includes(selectedPath) && (
                    <p className="text-[11px] text-amber-600">
                      Current path not found in connection — update or retype below.
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  No files found in this connection.
                </p>
              )}
              <Input
                className="mt-1"
                value={selectedPath}
                onChange={(e) => set({ path: e.target.value, format: formatFromPath(e.target.value) })}
                placeholder="data/input.csv"
              />
            </Field>
          )}
          <Field label="Format" error={errors.format} help="File format to read.">
            <Select value={c.format ?? "csv"} onChange={(e) => set({ format: e.target.value })}>
              <option value="csv">CSV</option>
              <option value="excel">Excel (.xlsx)</option>
              <option value="parquet">Parquet</option>
              <option value="json">JSON</option>
              <option value="text">Text (one row per line)</option>
            </Select>
          </Field>
        </>
      );
    }

    case "storageOutput":
      return (
        <>
          <Field label="Storage connection" error={errors.connection_id} help="S3, Azure Blob, GCS, or local folder (manage on the Connections page).">
            <Select
              value={c.connection_id ?? ""}
              onChange={(e) => set({ connection_id: e.target.value })}
            >
              <option value="">Select a storage connection…</option>
              {storageConnections.map((cn) => (
                <option key={cn.id} value={cn.id}>
                  {cn.name}
                </option>
              ))}
            </Select>
            {storageConnections.length === 0 && (
              <p className="text-[11px] text-amber-600">
                No storage connections yet — add one on the Connections page.
              </p>
            )}
          </Field>
          <Field
            label="Destination path"
            error={errors.path}
            hint="e.g. outputs/result.parquet"
            help="Where the file is written within the bucket or folder."
          >
            <Input
              value={c.path ?? ""}
              onChange={(e) => set({ path: e.target.value })}
              placeholder="outputs/result.parquet"
            />
          </Field>
          <Field label="Format" error={errors.format} help="File format to write.">
            <Select value={c.format ?? "parquet"} onChange={(e) => set({ format: e.target.value })}>
              <option value="csv">CSV</option>
              <option value="excel">Excel</option>
              <option value="parquet">Parquet</option>
            </Select>
          </Field>
          <Field label="If file exists" error={errors.if_exists} help="Overwrite the existing file, or fail if it already exists.">
            <Select value={c.if_exists ?? "overwrite"} onChange={(e) => set({ if_exists: e.target.value })}>
              <option value="overwrite">Overwrite</option>
              <option value="error">Fail with error</option>
            </Select>
          </Field>
        </>
      );

    case "csvOutput":
    case "excelOutput":
    case "parquetOutput":
      return (
        <Field
          label="Dataset name"
          hint="e.g. cleaned_sales"
          help="The output is saved as a reusable dataset in your project under this name. Re-running adds a new version."
          error={errors.dataset_name}
        >
          <Input
            value={c.dataset_name ?? ""}
            onChange={(e) => set({ dataset_name: e.target.value })}
            placeholder="my_output_dataset"
          />
        </Field>
      );

    // ----- Machine learning -----
    case "mlTrain":
      return <MlTrainConfig config={c} columns={columns} errors={errors} set={set} />;

    case "trainTestSplit":
      return (
        <>
          <Field
            label="Test size"
            error={errors.test_size}
            help="Fraction of rows held out for testing (e.g. 0.2 = 20% test, 80% train)."
          >
            <Input
              type="number"
              min={0.05}
              max={0.95}
              step={0.05}
              value={c.test_size ?? 0.2}
              onChange={(e) => set({ test_size: Number(e.target.value) })}
            />
          </Field>
          <Field
            label="Stratify by (optional)"
            error={errors.stratify_column}
            help="Keep the same class balance in train and test by stratifying on this column. Leave empty for a plain random split."
          >
            <ColumnSelect
              value={c.stratify_column ?? ""}
              columns={columns}
              onChange={(v) => set({ stratify_column: v || null })}
              placeholder="(no stratification)"
            />
          </Field>
          <Field
            label="Random seed"
            error={errors.seed}
            help="Required: the same seed reproduces the exact same split every run."
          >
            <Input
              type="number"
              value={c.seed ?? 42}
              onChange={(e) => set({ seed: Number(e.target.value) })}
            />
          </Field>
        </>
      );

    case "scaleFeatures":
      return (
        <>
          <Field label="Method" error={errors.method} help="StandardScaler (mean 0, std 1), MinMax (0–1), or Robust (median/IQR, outlier-resistant).">
            <Select value={c.method ?? "standard"} onChange={(e) => set({ method: e.target.value })}>
              <option value="standard">Standard (z-score)</option>
              <option value="minmax">Min-max (0 to 1)</option>
              <option value="robust">Robust (median / IQR)</option>
            </Select>
          </Field>
          <Field label="Columns" error={errors.columns} help="The numeric columns to scale.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
        </>
      );

    case "encodeCategories": {
      const method = (c.method as string) ?? "onehot";
      return (
        <>
          <Field label="Method" error={errors.method} help="One-hot creates a 0/1 column per category; ordinal maps each category to an integer.">
            <Select value={method} onChange={(e) => set({ method: e.target.value })}>
              <option value="onehot">One-hot (dummy columns)</option>
              <option value="ordinal">Ordinal (integer codes)</option>
            </Select>
          </Field>
          <Field label="Columns" error={errors.columns} help="The categorical (text) columns to encode.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          {method === "onehot" && (
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={!!c.drop_first}
                onChange={(e) => set({ drop_first: e.target.checked })}
              />
              Drop the first category (avoids collinearity)
            </label>
          )}
        </>
      );
    }

    case "imputeMissing": {
      const strategy = (c.strategy as string) ?? "mean";
      return (
        <>
          <Field label="Strategy" error={errors.strategy} help="How to fill missing values.">
            <Select value={strategy} onChange={(e) => set({ strategy: e.target.value })}>
              <option value="mean">Mean</option>
              <option value="median">Median</option>
              <option value="most_frequent">Most frequent</option>
              <option value="constant">Constant value</option>
              <option value="knn">KNN (nearest neighbours)</option>
            </Select>
          </Field>
          <Field label="Columns" error={errors.columns} help="The columns to fill.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          {strategy === "constant" && (
            <Field label="Fill value" error={errors.fill_value} help="The value written into empty cells.">
              <Input value={c.fill_value ?? ""} onChange={(e) => set({ fill_value: e.target.value })} />
            </Field>
          )}
          {strategy === "knn" && (
            <Field label="Neighbours (k)" error={errors.n_neighbors} help="How many nearest rows to average when imputing.">
              <Input
                type="number"
                min={1}
                value={c.n_neighbors ?? 5}
                onChange={(e) => set({ n_neighbors: Number(e.target.value) })}
              />
            </Field>
          )}
        </>
      );
    }

    case "selectFeatures": {
      const method = (c.method as string) ?? "variance";
      return (
        <>
          <Field label="Method" error={errors.method} help="Variance drops near-constant columns; correlation drops one of each highly-correlated pair; SelectKBest keeps the top features by relevance to a target.">
            <Select value={method} onChange={(e) => set({ method: e.target.value })}>
              <option value="variance">Variance threshold</option>
              <option value="correlation">Correlation filter</option>
              <option value="kbest">Top-K by relevance</option>
            </Select>
          </Field>
          {method !== "kbest" && (
            <Field
              label="Threshold"
              error={errors.threshold}
              help={method === "variance" ? "Drop columns with variance at or below this." : "Drop a column when its absolute correlation with another exceeds this (0–1)."}
            >
              <Input
                type="number"
                step={0.05}
                value={c.threshold ?? (method === "variance" ? 0 : 0.9)}
                onChange={(e) => set({ threshold: Number(e.target.value) })}
              />
            </Field>
          )}
          {method === "kbest" && (
            <>
              <Field label="Target column" error={errors.target_column} help="The column being predicted — relevance is scored against it.">
                <ColumnSelect value={c.target_column ?? ""} columns={columns} onChange={(v) => set({ target_column: v })} />
              </Field>
              <Field label="Keep top K" error={errors.k} help="How many of the best features to keep.">
                <Input type="number" min={1} value={c.k ?? 10} onChange={(e) => set({ k: Number(e.target.value) })} />
              </Field>
            </>
          )}
        </>
      );
    }

    case "reduceDimensions":
      return (
        <>
          <Field label="Components" error={errors.n_components} help="A whole number = how many components to keep; a fraction in (0,1) = keep enough to explain that much variance.">
            <Input
              type="number"
              step={0.05}
              min={0}
              value={c.n_components ?? 2}
              onChange={(e) => set({ n_components: Number(e.target.value) })}
            />
          </Field>
          <Field label="Columns (optional)" error={errors.columns} hint="Empty = all numeric columns" help="The numeric columns to compress into components.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="Component prefix" error={errors.prefix} help="New columns are named prefix_1, prefix_2, …">
            <Input value={c.prefix ?? "pc"} onChange={(e) => set({ prefix: e.target.value })} />
          </Field>
          <Field label="Random seed" error={errors.seed} help="Makes the (randomized) solver reproducible.">
            <Input type="number" value={c.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
          </Field>
        </>
      );

    case "mlPredict":
      return (
        <>
          <Field
            label="Model URI (optional)"
            error={errors.model_uri}
            hint="Leave empty to use the connected model wire"
            help="Reference a registered model by alias (models:/churn@production) or version (models:/churn/1). Otherwise connect mlTrain's model output to the model input."
          >
            <Input
              value={c.model_uri ?? ""}
              placeholder="models:/your-model@production"
              onChange={(e) => set({ model_uri: e.target.value })}
            />
          </Field>
          <Field label="Prediction column" error={errors.output_column} help="Name of the new column holding the model's prediction.">
            <Input value={c.output_column ?? "prediction"} onChange={(e) => set({ output_column: e.target.value })} />
          </Field>
          <Field
            label="Probability columns (optional)"
            error={errors.output_proba_columns}
            hint="One name per class, e.g. proba_0, proba_1"
            help="For classifiers: also output class probabilities under these column names."
          >
            <CsvListInput
              value={c.output_proba_columns}
              onChange={(v) => set({ output_proba_columns: v })}
              placeholder="proba_0, proba_1"
            />
          </Field>
        </>
      );

    case "mlEvaluate": {
      const task = (c.task_type as string) ?? "classification";
      const metricOptions: Record<string, string[]> = {
        classification: ["accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"],
        regression: ["rmse", "mae", "r2", "mape", "residual_std"],
        clustering: ["silhouette", "davies_bouldin"],
      };
      return (
        <>
          <Field label="Task type" error={errors.task_type} help="Pick the kind of model whose predictions you're scoring.">
            <Select value={task} onChange={(e) => set({ task_type: e.target.value })}>
              <option value="classification">Classification</option>
              <option value="regression">Regression</option>
              <option value="clustering">Clustering</option>
            </Select>
          </Field>
          {task !== "clustering" && (
            <Field label="True value column" error={errors.target_column} help="The actual/observed values to compare predictions against.">
              <ColumnSelect value={c.target_column ?? ""} columns={columns} onChange={(v) => set({ target_column: v })} />
            </Field>
          )}
          <Field
            label={task === "clustering" ? "Cluster label column" : "Prediction column"}
            error={errors.prediction_column}
            help="The column holding the model output (from mlPredict)."
          >
            <ColumnSelect value={c.prediction_column ?? "prediction"} columns={columns} onChange={(v) => set({ prediction_column: v })} />
          </Field>
          {task === "classification" && (
            <Field
              label="Probability columns (optional)"
              error={errors.proba_columns}
              hint="Needed for ROC-AUC"
              help="Class-probability columns produced by mlPredict."
            >
              <ColumnMultiSelect value={c.proba_columns} columns={columns} onChange={(v) => set({ proba_columns: v })} />
            </Field>
          )}
          <Field label="Metrics (optional)" error={errors.metrics} hint="Empty = a sensible default set" help="Pick which metrics to compute.">
            <ColumnMultiSelect
              value={c.metrics}
              columns={metricOptions[task] ?? []}
              onChange={(v) => set({ metrics: v })}
            />
          </Field>
        </>
      );
    }

    case "featureImportance":
      return (
        <Field
          label="Show top N (optional)"
          error={errors.top_n}
          hint="Empty = all features"
          help="Limit the output to the N most important features."
        >
          <Input
            type="number"
            min={1}
            value={c.top_n ?? ""}
            placeholder="all"
            onChange={(e) => set({ top_n: e.target.value === "" ? null : Number(e.target.value) })}
          />
        </Field>
      );

    default:
      return <p className="text-xs text-muted-foreground">No configuration for this node type.</p>;
  }
}

// Specialized key/value editor where the value is a constrained dtype select.
function DtypeEditor({
  value,
  columns,
  onChange,
}: {
  value: Record<string, string> | undefined;
  columns: string[];
  onChange: (v: Record<string, string>) => void;
}) {
  const entries = Object.entries(value ?? {});
  const rows = [...entries, ["", "string"]] as [string, string][];
  const listId = columns.length ? "cols-cast" : undefined;

  const update = (idx: number, k: string, v: string) => {
    const next: Record<string, string> = {};
    rows.forEach(([rk, rv], i) => {
      const key = i === idx ? k : rk;
      const val = i === idx ? v : rv;
      if (key.trim()) next[key] = val;
    });
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-1">
      {listId && (
        <datalist id={listId}>
          {columns.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      )}
      {rows.map(([k, v], idx) => (
        <div key={idx} className="flex gap-1">
          <Input
            className="h-8"
            list={listId}
            placeholder="column"
            value={k}
            onChange={(e) => update(idx, e.target.value, v)}
          />
          <Select className="h-8 w-28" value={v} onChange={(e) => update(idx, k, e.target.value)}>
            {dtypes.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
        </div>
      ))}
    </div>
  );
}
