import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  aggFunctions,
  binMethods,
  conditionOperators,
  conditionValueless,
  dateDiffUnits,
  dateParts,
  joinHows,
  JOIN_HOW_LABELS,
  outlierActions,
  outlierMethods,
  OUTLIER_METHOD_LABELS,
  pivotAggFunctions,
  rollingFunctions,
  ROLLING_FUNCTION_LABELS,
  rowDiffMethods,
  ROW_DIFF_METHOD_LABELS,
  splitModes,
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
} from "../configFields";
import type { NodeConfigRenderProps } from "./shared";

/** Config fields for the reshape/aggregate node family (group-by, join,
 *  pivot/unpivot, window functions, row math, …), or `undefined` if `type`
 *  isn't one. */
export function renderReshapeConfig(
  type: string,
  { c, errors, set, columns }: NodeConfigRenderProps,
): ReactNode | undefined {
  switch (type) {
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
          <Field
            label="Random seed"
            error={errors.seed}
            help="Required: the same seed reproduces the exact same sample every run."
          >
            <Input type="number" value={c.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
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
          <Field
            label="Custom labels (optional)"
            error={errors.labels}
            hint="Comma-separated"
            help="One label per bin, in order. Empty = default numeric bin labels."
          >
            <CsvListInput value={c.labels} onChange={(v) => set({ labels: v })} placeholder="Bronze, Silver, Gold" />
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
              {pivotAggFunctions.map((a) => (
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

    case "combineColumns":
      return (
        <>
          <Field label="Columns to combine" error={errors.columns} help="Joined left-to-right in this order.">
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="New column" error={errors.new_column}>
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="full_name" />
          </Field>
          <Field label="Separator" error={errors.separator} help="Text inserted between values (default a single space).">
            <Input value={c.separator ?? " "} onChange={(e) => set({ separator: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={c.keep_original !== false}
              onChange={(e) => set({ keep_original: e.target.checked })}
            />
            Keep the original columns
          </label>
        </>
      );

    case "coalesceColumns":
      return (
        <>
          <Field
            label="Columns (in priority order)"
            error={errors.columns}
            help="The first non-null value across these columns is kept."
          >
            <ColumnMultiSelect value={c.columns} columns={columns} onChange={(v) => set({ columns: v })} />
          </Field>
          <Field label="New column" error={errors.new_column}>
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="value" />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={c.keep_original !== false}
              onChange={(e) => set({ keep_original: e.target.checked })}
            />
            Keep the original columns
          </label>
        </>
      );

    case "explodeRows":
      return (
        <>
          <Field label="Column" error={errors.column} help="The column to expand into multiple rows.">
            <ColumnSelect value={c.column} columns={columns} onChange={(v) => set({ column: v })} />
          </Field>
          <Field
            label="Delimiter (optional)"
            error={errors.delimiter}
            help="Split text on this delimiter, then explode. Leave empty to explode an existing list column."
          >
            <Input value={c.delimiter ?? ""} onChange={(e) => set({ delimiter: e.target.value })} placeholder="," />
          </Field>
        </>
      );

    case "rollingAggregate":
      return (
        <>
          <Field label="Target column" error={errors.target} help="The numeric column to aggregate.">
            <ColumnSelect value={c.target} columns={columns} onChange={(v) => set({ target: v })} />
          </Field>
          <Field label="Function" error={errors.function}>
            <Select value={c.function ?? "mean"} onChange={(e) => set({ function: e.target.value })}>
              {rollingFunctions.map((f) => (
                <option key={f} value={f}>
                  {ROLLING_FUNCTION_LABELS[f] ?? f}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Window (rows)" error={errors.window} help="Number of rows in each moving window.">
            <Input type="number" min={1} value={c.window ?? 3} onChange={(e) => set({ window: Number(e.target.value) })} />
          </Field>
          <Field
            label="Min periods (optional)"
            error={errors.min_periods}
            hint="Empty = full window"
            help="Fewer rows than the window yield null unless this is set."
          >
            <Input
              type="number"
              min={1}
              value={c.min_periods ?? ""}
              placeholder="full window"
              onChange={(e) => set({ min_periods: e.target.value === "" ? null : Number(e.target.value) })}
            />
          </Field>
          <Field label="Order by" error={errors.order_by} help="Rows are ordered by these columns within each window (e.g. a date).">
            <ColumnMultiSelect value={c.order_by} columns={columns} onChange={(v) => set({ order_by: v })} />
          </Field>
          <Field label="Partition by (optional)" error={errors.partition_by} hint="Empty = whole table" help="Restart the window within each group.">
            <ColumnMultiSelect value={c.partition_by} columns={columns} onChange={(v) => set({ partition_by: v })} />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input type="checkbox" checked={!!c.descending} onChange={(e) => set({ descending: e.target.checked })} />
            Order descending
          </label>
          <Field label="New column" error={errors.new_column}>
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="rolling_mean" />
          </Field>
        </>
      );

    case "rowDifference":
      return (
        <>
          <Field label="Target column" error={errors.target} help="The numeric column to compare across rows.">
            <ColumnSelect value={c.target} columns={columns} onChange={(v) => set({ target: v })} />
          </Field>
          <Field label="Method" error={errors.method}>
            <Select value={c.method ?? "diff"} onChange={(e) => set({ method: e.target.value })}>
              {rowDiffMethods.map((m) => (
                <option key={m} value={m}>
                  {ROW_DIFF_METHOD_LABELS[m] ?? m}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Periods" error={errors.periods} help="How many rows back to compare against (default 1).">
            <Input type="number" min={1} value={c.periods ?? 1} onChange={(e) => set({ periods: Number(e.target.value) })} />
          </Field>
          <Field label="Order by" error={errors.order_by} help="Rows are ordered by these columns first (e.g. a date).">
            <ColumnMultiSelect value={c.order_by} columns={columns} onChange={(v) => set({ order_by: v })} />
          </Field>
          <Field label="Partition by (optional)" error={errors.partition_by} hint="Empty = whole table" help="Compare only within each group.">
            <ColumnMultiSelect value={c.partition_by} columns={columns} onChange={(v) => set({ partition_by: v })} />
          </Field>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input type="checkbox" checked={!!c.descending} onChange={(e) => set({ descending: e.target.checked })} />
            Order descending
          </label>
          <Field label="New column" error={errors.new_column}>
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="delta" />
          </Field>
        </>
      );

    case "dateDifference":
      return (
        <>
          <Field label="Start date column" error={errors.start_column}>
            <ColumnSelect value={c.start_column} columns={columns} onChange={(v) => set({ start_column: v })} />
          </Field>
          <Field label="End date column" error={errors.end_column} help="The result is end − start.">
            <ColumnSelect value={c.end_column} columns={columns} onChange={(v) => set({ end_column: v })} />
          </Field>
          <Field label="Unit" error={errors.unit}>
            <Select value={c.unit ?? "days"} onChange={(e) => set({ unit: e.target.value })}>
              {dateDiffUnits.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="New column" error={errors.new_column}>
            <Input value={c.new_column ?? ""} onChange={(e) => set({ new_column: e.target.value })} placeholder="days_between" />
          </Field>
        </>
      );

    default:
      return undefined;
  }
}
