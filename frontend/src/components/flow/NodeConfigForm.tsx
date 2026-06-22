import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dataset } from "@/lib/types";
import {
  dtypes,
  filterOperators,
  getConfigSchema,
  joinHows,
  stringOperations,
} from "@/lib/validators";
import {
  ColumnMultiSelect,
  ColumnSelect,
  Field,
  KeyValueEditor,
} from "./configFields";

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

  if (type === "csvInput" || type === "excelInput" || type === "parquetInput") {
    const accepted =
      type === "csvInput" ? "csv" : type === "excelInput" ? "excel" : "parquet";
    const compatible = datasets.filter((d) => d.source_type === accepted);
    return (
      <Field
        label="Dataset"
        error={errors.dataset_id}
        help={`Only ${accepted.toUpperCase()} datasets can be loaded by this node.`}
      >
        <Select
          value={(c.dataset_id as string) ?? ""}
          onChange={(e) => set({ dataset_id: e.target.value })}
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
    );
  }

  switch (type) {
    case "dropNulls":
      return (
        <Field
          label="Subset (optional)"
          hint="Leave empty to check all columns"
          help="A row is dropped when any of these columns is null."
          error={errors.subset}
        >
          <ColumnMultiSelect value={c.subset} columns={columns} onChange={(v) => set({ subset: v })} />
        </Field>
      );

    case "fillNulls":
      return (
        <>
          <Field label="Fill value" error={errors.value} help="The value written into empty cells.">
            <Input value={c.value ?? ""} onChange={(e) => set({ value: e.target.value })} />
          </Field>
          <Field label="Columns (optional)" error={errors.columns} hint="Empty = all columns">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
        </>
      );

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
          <KeyValueEditor
            value={c.mapping}
            onChange={(v) => set({ mapping: v })}
            keyLabel="old name"
            valueLabel="new name"
            keySuggestions={columns}
          />
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
      return (
        <>
          <Field label="Column" error={errors.column}>
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Operator" error={errors.operator} help="How the column is compared to the value.">
            <Select value={operator} onChange={(e) => set({ operator: e.target.value })}>
              {filterOperators.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </Select>
          </Field>
          {needsValue && (
            <Field label="Value" error={errors.value}>
              <Input value={c.value ?? ""} onChange={(e) => set({ value: e.target.value })} />
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
        </>
      );

    case "castDtypes":
      return (
        <Field label="Casts" hint="column → type" error={errors.casts} help="Convert each column to the chosen data type.">
          <DtypeEditor value={c.casts} columns={columns} onChange={(v) => set({ casts: v })} />
        </Field>
      );

    case "limitRows":
      return (
        <Field label="Number of rows" error={errors.n} help="Keep only the first N rows.">
          <Input type="number" value={c.n ?? 100} onChange={(e) => set({ n: Number(e.target.value) })} />
        </Field>
      );

    case "replaceValues":
      return (
        <>
          <Field label="Column" error={errors.column}>
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Replace" error={errors.to_replace} help="The exact value to look for.">
            <Input value={c.to_replace ?? ""} onChange={(e) => set({ to_replace: e.target.value })} />
          </Field>
          <Field label="With" error={errors.value} help="The value to substitute in.">
            <Input value={c.value ?? ""} onChange={(e) => set({ value: e.target.value })} />
          </Field>
        </>
      );

    case "stringTransform":
      return (
        <>
          <Field label="Column" error={errors.column}>
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field label="Operation" error={errors.operation} help="Text transformation applied to every value.">
            <Select value={c.operation ?? "lower"} onChange={(e) => set({ operation: e.target.value })}>
              {stringOperations.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </Select>
          </Field>
        </>
      );

    case "calculatedColumn":
      return (
        <>
          <Field label="New column name" error={errors.column_name}>
            <Input value={c.column_name ?? ""} onChange={(e) => set({ column_name: e.target.value })} />
          </Field>
          <Field
            label="Expression"
            hint={columns.length ? `Available: ${columns.join(", ")}` : "e.g. price * quantity"}
            help="A pandas expression evaluated per row. Reference columns by name."
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
            hint="column → agg (sum, mean, count, min, max)"
            help="For each column, choose how to combine the grouped rows."
            error={errors.aggregations}
          >
            <KeyValueEditor
              value={c.aggregations}
              onChange={(v) => set({ aggregations: v })}
              keyLabel="column"
              valueLabel="agg"
              keySuggestions={columns}
            />
          </Field>
        </>
      );

    case "join":
      return (
        <>
          <Field label="Join on" error={errors.on} help="Column(s) that must match between the left and right inputs.">
            <ColumnMultiSelect
              value={Array.isArray(c.on) ? c.on : c.on ? [c.on] : []}
              columns={columns}
              onChange={(v) => set({ on: v })}
            />
          </Field>
          <Field label="How" error={errors.how} help="Which rows to keep when keys don't match on both sides.">
            <Select value={c.how ?? "inner"} onChange={(e) => set({ how: e.target.value })}>
              {joinHows.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </Select>
          </Field>
        </>
      );

    case "concatRows":
      return (
        <p className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
          Stacks all incoming dataframes vertically. Connect two or more inputs —
          no configuration required.
        </p>
      );

    case "csvOutput":
    case "excelOutput":
    case "parquetOutput":
      return (
        <Field
          label="Output path (optional)"
          hint="Leave empty to auto-generate"
          help="Where the result file is written. Defaults to a generated path."
          error={errors.path}
        >
          <Input value={c.path ?? ""} onChange={(e) => set({ path: e.target.value })} />
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
