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
import { CsvListInput, Field, KeyValueEditor } from "./configFields";

interface NodeConfigFormProps {
  type: string;
  config: Record<string, unknown>;
  datasets: Dataset[];
  onChange: (config: Record<string, unknown>) => void;
  onErrors: (hasErrors: boolean) => void;
}

type ErrorMap = Record<string, string>;

export function NodeConfigForm({
  type,
  config,
  datasets,
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

  const set = (patch: Record<string, unknown>) =>
    onChange({ ...config, ...patch });

  const c = config as Record<string, any>;

  if (type === "csvInput" || type === "excelInput" || type === "parquetInput") {
    return (
      <Field label="Dataset" error={errors.dataset_id}>
        <Select
          value={(c.dataset_id as string) ?? ""}
          onChange={(e) => set({ dataset_id: e.target.value })}
        >
          <option value="">Select a dataset…</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </Select>
      </Field>
    );
  }

  switch (type) {
    case "dropNulls":
      return (
        <Field
          label="Subset (optional)"
          hint="Leave empty to check all columns"
          error={errors.subset}
        >
          <CsvListInput
            value={c.subset}
            onChange={(v) => set({ subset: v })}
          />
        </Field>
      );

    case "fillNulls":
      return (
        <>
          <Field label="Fill value" error={errors.value}>
            <Input
              value={c.value ?? ""}
              onChange={(e) => set({ value: e.target.value })}
            />
          </Field>
          <Field label="Columns (optional)" error={errors.columns}>
            <CsvListInput
              value={c.columns}
              onChange={(v) => set({ columns: v })}
            />
          </Field>
        </>
      );

    case "dropColumns":
    case "selectColumns":
      return (
        <Field label="Columns" error={errors.columns}>
          <CsvListInput
            value={c.columns}
            onChange={(v) => set({ columns: v })}
          />
        </Field>
      );

    case "renameColumns":
      return (
        <Field label="Rename mapping" error={errors.mapping}>
          <KeyValueEditor
            value={c.mapping}
            onChange={(v) => set({ mapping: v })}
            keyLabel="old name"
            valueLabel="new name"
          />
        </Field>
      );

    case "removeDuplicates":
      return (
        <>
          <Field label="Subset (optional)" error={errors.subset}>
            <CsvListInput
              value={c.subset}
              onChange={(v) => set({ subset: v })}
            />
          </Field>
          <Field label="Keep" error={errors.keep}>
            <Select
              value={c.keep ?? "first"}
              onChange={(e) => set({ keep: e.target.value })}
            >
              <option value="first">first</option>
              <option value="last">last</option>
            </Select>
          </Field>
        </>
      );

    case "filterRows":
      return (
        <>
          <Field label="Column" error={errors.column}>
            <Input
              value={c.column ?? ""}
              onChange={(e) => set({ column: e.target.value })}
            />
          </Field>
          <Field label="Operator" error={errors.operator}>
            <Select
              value={c.operator ?? "=="}
              onChange={(e) => set({ operator: e.target.value })}
            >
              {filterOperators.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Value" error={errors.value}>
            <Input
              value={c.value ?? ""}
              onChange={(e) => set({ value: e.target.value })}
            />
          </Field>
        </>
      );

    case "sortRows":
      return (
        <>
          <Field label="Columns" error={errors.columns}>
            <CsvListInput
              value={c.columns}
              onChange={(v) => set({ columns: v })}
            />
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
        <Field label="Casts" hint="column -> type" error={errors.casts}>
          <DtypeEditor
            value={c.casts}
            onChange={(v) => set({ casts: v })}
          />
        </Field>
      );

    case "limitRows":
      return (
        <Field label="Number of rows" error={errors.n}>
          <Input
            type="number"
            value={c.n ?? 100}
            onChange={(e) => set({ n: Number(e.target.value) })}
          />
        </Field>
      );

    case "replaceValues":
      return (
        <>
          <Field label="Column" error={errors.column}>
            <Input
              value={c.column ?? ""}
              onChange={(e) => set({ column: e.target.value })}
            />
          </Field>
          <Field label="Replace" error={errors.to_replace}>
            <Input
              value={c.to_replace ?? ""}
              onChange={(e) => set({ to_replace: e.target.value })}
            />
          </Field>
          <Field label="With" error={errors.value}>
            <Input
              value={c.value ?? ""}
              onChange={(e) => set({ value: e.target.value })}
            />
          </Field>
        </>
      );

    case "stringTransform":
      return (
        <>
          <Field label="Column" error={errors.column}>
            <Input
              value={c.column ?? ""}
              onChange={(e) => set({ column: e.target.value })}
            />
          </Field>
          <Field label="Operation" error={errors.operation}>
            <Select
              value={c.operation ?? "lower"}
              onChange={(e) => set({ operation: e.target.value })}
            >
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
            <Input
              value={c.column_name ?? ""}
              onChange={(e) => set({ column_name: e.target.value })}
            />
          </Field>
          <Field
            label="Expression"
            hint="e.g. price * quantity"
            error={errors.expression}
          >
            <Input
              value={c.expression ?? ""}
              onChange={(e) => set({ expression: e.target.value })}
            />
          </Field>
        </>
      );

    case "groupByAggregate":
      return (
        <>
          <Field label="Group by columns" error={errors.group_by}>
            <CsvListInput
              value={c.group_by}
              onChange={(v) => set({ group_by: v })}
            />
          </Field>
          <Field
            label="Aggregations"
            hint="column -> agg (sum, mean, count, min, max)"
            error={errors.aggregations}
          >
            <KeyValueEditor
              value={c.aggregations}
              onChange={(v) => set({ aggregations: v })}
              keyLabel="column"
              valueLabel="agg"
            />
          </Field>
        </>
      );

    case "join":
      return (
        <>
          <Field
            label="Join on"
            hint="column name(s), comma-separated"
            error={errors.on}
          >
            <Input
              value={
                Array.isArray(c.on) ? c.on.join(", ") : (c.on ?? "")
              }
              onChange={(e) => {
                const parts = e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean);
                set({ on: parts.length > 1 ? parts : (parts[0] ?? "") });
              }}
            />
          </Field>
          <Field label="How" error={errors.how}>
            <Select
              value={c.how ?? "inner"}
              onChange={(e) => set({ how: e.target.value })}
            >
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
        <p className="text-xs text-muted-foreground">
          Stacks all incoming dataframes. No configuration required.
        </p>
      );

    case "csvOutput":
    case "excelOutput":
    case "parquetOutput":
      return (
        <Field
          label="Output path (optional)"
          hint="Leave empty to auto-generate"
          error={errors.path}
        >
          <Input
            value={c.path ?? ""}
            onChange={(e) => set({ path: e.target.value })}
          />
        </Field>
      );

    default:
      return (
        <p className="text-xs text-muted-foreground">
          No configuration for this node type.
        </p>
      );
  }
}

// Specialized key/value editor where the value is a constrained dtype select.
function DtypeEditor({
  value,
  onChange,
}: {
  value: Record<string, string> | undefined;
  onChange: (v: Record<string, string>) => void;
}) {
  const entries = Object.entries(value ?? {});
  const rows = [...entries, ["", "string"]] as [string, string][];

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
      {rows.map(([k, v], idx) => (
        <div key={idx} className="flex gap-1">
          <Input
            className="h-8"
            placeholder="column"
            value={k}
            onChange={(e) => update(idx, e.target.value, v)}
          />
          <Select
            className="h-8 w-28"
            value={v}
            onChange={(e) => update(idx, k, e.target.value)}
          >
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
