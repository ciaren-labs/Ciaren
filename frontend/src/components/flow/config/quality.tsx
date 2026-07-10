import { useState, type ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { FILTER_OPERATOR_LABELS, filterOperators } from "@/lib/validators";
import { ColumnMultiSelect, ColumnSelect, CsvListInput, Field } from "../configFields";
import { VALUELESS_OPERATORS, type NodeConfigRenderProps } from "./shared";

function quoteFilterValue(raw: string, operator: string): string {
  const value = raw.trim();
  if (operator === "in") {
    const items = value
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .map((v) => (/^-?\d+(\.\d+)?$/.test(v) ? v : `'${v.replace(/'/g, "\\'")}'`));
    return `[${items.join(", ")}]`;
  }
  if (/^-?\d+(\.\d+)?$/.test(value) || value === "True" || value === "False") return value;
  return `'${value.replace(/'/g, "\\'")}'`;
}

function buildFilterCondition(column: string, operator: string, value: string, value2: string): string {
  if (!column) return "";
  if (operator === "isnull") return `${column}.isnull()`;
  if (operator === "notnull") return `${column}.notnull()`;
  if (operator === "contains") return `${column}.str.contains(${quoteFilterValue(value, operator)})`;
  if (operator === "startswith") return `${column}.str.startswith(${quoteFilterValue(value, operator)})`;
  if (operator === "endswith") return `${column}.str.endswith(${quoteFilterValue(value, operator)})`;
  if (operator === "in") return `${column}.isin(${quoteFilterValue(value, operator)})`;
  if (operator === "between") {
    return `(${column} >= ${quoteFilterValue(value, operator)} and ${column} <= ${quoteFilterValue(value2, operator)})`;
  }
  return `${column} ${operator} ${quoteFilterValue(value, operator)}`;
}

function FilterExpressionEditor({
  value,
  columns,
  error,
  onChange,
}: {
  value: string;
  columns: string[];
  error?: string;
  onChange: (expression: string) => void;
}) {
  const [column, setColumn] = useState(columns[0] ?? "");
  const [operator, setOperator] = useState<string>("==");
  const [conditionValue, setConditionValue] = useState("");
  const [conditionValue2, setConditionValue2] = useState("");
  const needsValue = !VALUELESS_OPERATORS.has(operator);
  const condition = buildFilterCondition(column, operator, conditionValue, conditionValue2);
  const canInsert =
    !!column &&
    (!needsValue || !!conditionValue.trim()) &&
    (operator !== "between" || !!conditionValue2.trim());
  const insert = (connector: "and" | "or" | null) => {
    if (!canInsert) return;
    const current = value.trim();
    onChange(current && connector ? `${current} ${connector} ${condition}` : condition);
  };

  return (
    <div className="flex flex-col gap-3">
      <Field
        label="Build condition"
        help="Compose a condition, then append it to the expression with AND or OR."
      >
        <div className="grid grid-cols-2 gap-2">
          <ColumnSelect value={column} columns={columns} onChange={setColumn} />
          <Select value={operator} onChange={(e) => setOperator(e.target.value)}>
            {filterOperators.map((op) => (
              <option key={op} value={op}>
                {FILTER_OPERATOR_LABELS[op] ?? op}
              </option>
            ))}
          </Select>
        </div>
        {needsValue && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Input
              value={conditionValue}
              placeholder={operator === "in" ? "paid, pending" : "value"}
              onChange={(e) => setConditionValue(e.target.value)}
            />
            {operator === "between" ? (
              <Input value={conditionValue2} placeholder="upper bound" onChange={(e) => setConditionValue2(e.target.value)} />
            ) : (
              <div />
            )}
          </div>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          <button
            type="button"
            disabled={!canInsert}
            onClick={() => insert(null)}
            className="rounded-md border border-border px-2 py-1 text-[11px] font-medium disabled:opacity-50"
          >
            Use condition
          </button>
          <button
            type="button"
            disabled={!canInsert || !value.trim()}
            onClick={() => insert("and")}
            className="rounded-md border border-border px-2 py-1 text-[11px] font-medium disabled:opacity-50"
          >
            AND
          </button>
          <button
            type="button"
            disabled={!canInsert || !value.trim()}
            onClick={() => insert("or")}
            className="rounded-md border border-border px-2 py-1 text-[11px] font-medium disabled:opacity-50"
          >
            OR
          </button>
        </div>
      </Field>
      <Field
        label="Expression"
        error={error}
        help="A boolean expression that must be true to keep a row. You can still edit it directly."
      >
        <textarea
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          rows={3}
          value={value}
          placeholder="amount > 100 and status == 'paid'"
          onChange={(e) => onChange(e.target.value)}
        />
      </Field>
    </div>
  );
}

/** Config fields for the Data Quality assertion nodes plus Filter by expression,
 *  or `undefined` if `type` isn't one. */
export function renderQualityConfig(
  type: string,
  { c, errors, set, columns }: NodeConfigRenderProps,
): ReactNode | undefined {
  switch (type) {
    case "assertNotNull":
      return (
        <>
          <Field
            label="Columns (optional)"
            error={errors.columns}
            hint="Empty = all columns"
            help="Assert that none of these columns contain null values."
          >
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="On violation" error={errors.mode} help="Error stops the run; warn records the result and continues.">
            <Select value={c.mode ?? "error"} onChange={(e) => set({ mode: e.target.value })}>
              <option value="error">Error (stop run)</option>
              <option value="warn">Warn (continue)</option>
            </Select>
          </Field>
        </>
      );

    case "assertUnique":
      return (
        <>
          <Field
            label="Columns (optional)"
            error={errors.columns}
            hint="Empty = all columns"
            help="Assert that this combination of columns has no duplicate rows."
          >
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="On violation" error={errors.mode} help="Error stops the run; warn records the result and continues.">
            <Select value={c.mode ?? "error"} onChange={(e) => set({ mode: e.target.value })}>
              <option value="error">Error (stop run)</option>
              <option value="warn">Warn (continue)</option>
            </Select>
          </Field>
        </>
      );

    case "assertValueRange":
      return (
        <>
          <Field label="Column" error={errors.column} help="The numeric column to check.">
            <ColumnSelect value={c.column ?? ""} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Min" error={errors.min} hint="Optional">
              <Input
                type="number"
                value={c.min ?? ""}
                placeholder="none"
                onChange={(e) => set({ min: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </Field>
            <Field label="Max" error={errors.max} hint="Optional">
              <Input
                type="number"
                value={c.max ?? ""}
                placeholder="none"
                onChange={(e) => set({ max: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </Field>
          </div>
          <Field label="Bounds" error={errors.inclusive} help="Inclusive includes the boundary values; exclusive excludes them.">
            <Select
              value={String(c.inclusive ?? true)}
              onChange={(e) => set({ inclusive: e.target.value === "true" })}
            >
              <option value="true">Inclusive [min, max]</option>
              <option value="false">Exclusive (min, max)</option>
            </Select>
          </Field>
          <Field label="On violation" error={errors.mode} help="Error stops the run; warn records the result and continues.">
            <Select value={c.mode ?? "error"} onChange={(e) => set({ mode: e.target.value })}>
              <option value="error">Error (stop run)</option>
              <option value="warn">Warn (continue)</option>
            </Select>
          </Field>
        </>
      );

    case "assertExpression":
      return (
        <>
          <Field
            label="Expression"
            error={errors.expression}
            help="A boolean pandas-eval expression that must be true for every row. Example: price > cost"
          >
            <textarea
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              rows={3}
              value={(c.expression as string) ?? ""}
              placeholder="e.g. amount > 0"
              onChange={(e) => set({ expression: e.target.value })}
            />
          </Field>
          <Field label="On violation" error={errors.mode} help="Error stops the run; warn records the result and continues.">
            <Select value={c.mode ?? "error"} onChange={(e) => set({ mode: e.target.value })}>
              <option value="error">Error (stop run)</option>
              <option value="warn">Warn (continue)</option>
            </Select>
          </Field>
        </>
      );

    case "assertRowCount":
      return (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Min rows" error={errors.min_rows} hint="Optional">
              <Input
                type="number"
                min={0}
                value={c.min_rows ?? ""}
                placeholder="none"
                onChange={(e) => set({ min_rows: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </Field>
            <Field label="Max rows" error={errors.max_rows} hint="Optional">
              <Input
                type="number"
                min={0}
                value={c.max_rows ?? ""}
                placeholder="none"
                onChange={(e) => set({ max_rows: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </Field>
          </div>
          <Field label="On violation" error={errors.mode} help="Error stops the run; warn records the result and continues.">
            <Select value={c.mode ?? "error"} onChange={(e) => set({ mode: e.target.value })}>
              <option value="error">Error (stop run)</option>
              <option value="warn">Warn (continue)</option>
            </Select>
          </Field>
        </>
      );

    case "assertValuesInSet":
      return (
        <>
          <Field label="Column" error={errors.column} help="The column whose values are checked.">
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field
            label="Allowed values"
            error={errors.allowed}
            hint="Comma-separated"
            help="Rows whose value isn't in this set are violations."
          >
            <CsvListInput value={c.allowed} onChange={(v) => set({ allowed: v })} placeholder="paid, pending, failed" />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={c.allow_null !== false}
              onChange={(e) => set({ allow_null: e.target.checked })}
            />
            Allow null / empty values
          </label>
          <Field label="On violation" error={errors.mode} help="Error stops the run; warn records the result and continues.">
            <Select value={c.mode ?? "error"} onChange={(e) => set({ mode: e.target.value })}>
              <option value="error">Error (stop run)</option>
              <option value="warn">Warn (continue)</option>
            </Select>
          </Field>
        </>
      );

    case "filterExpression":
      return (
        <FilterExpressionEditor
          value={(c.expression as string) ?? ""}
          columns={columns}
          error={errors.expression}
          onChange={(expression) => set({ expression })}
        />
      );

    default:
      return undefined;
  }
}
