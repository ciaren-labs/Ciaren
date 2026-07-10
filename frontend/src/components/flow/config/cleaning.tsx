import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { EXPRESSION_TEMPLATES } from "@/lib/nodeDocs";
import {
  dtypes,
  fillStrategies,
  filterOperators,
  FILTER_OPERATOR_LABELS,
  stringOperations,
} from "@/lib/validators";
import {
  ColumnKeyedEditor,
  ColumnMultiSelect,
  ColumnSelect,
  DateFormatPicker,
  Field,
  KeyValueEditor,
  TagInput,
} from "../configFields";
import { VALUELESS_OPERATORS, type NodeConfigRenderProps } from "./shared";

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

/** Config fields for the row/column-cleaning node family, or `undefined` if
 *  `type` isn't one. */
export function renderCleaningConfig(
  type: string,
  { c, errors, set, columns }: NodeConfigRenderProps,
): ReactNode | undefined {
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

    default:
      return undefined;
  }
}
