// Schema-driven config form: renders the small field dialect plugins declare
// (app/plugin_api ConfigFieldSpec) so a plugin node or connector gets a real
// form without a hand-written per-type component. Shared by the node sidebar
// (column/column_list resolve against the incoming wire) and the connection
// dialog (which passes no columns).

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { ConfigField } from "@/lib/types";
import { ColumnMultiSelect, ColumnSelect, CsvListInput, Field } from "./configFields";

interface SchemaConfigFieldsProps {
  fields: ConfigField[];
  config: Record<string, unknown>;
  /** Columns on the incoming wire, for column/column_list fields. */
  columns?: string[];
  errors?: Record<string, string>;
  onChange: (key: string, value: unknown) => void;
}

function fieldValue(field: ConfigField, config: Record<string, unknown>): unknown {
  const raw = config[field.key];
  return raw === undefined ? field.default : raw;
}

export function SchemaConfigFields({
  fields,
  config,
  columns = [],
  errors = {},
  onChange,
}: SchemaConfigFieldsProps) {
  return (
    <>
      {fields.map((field) => (
        <SchemaField
          key={field.key}
          field={field}
          value={fieldValue(field, config)}
          columns={columns}
          error={errors[field.key]}
          onChange={(v) => onChange(field.key, v)}
        />
      ))}
    </>
  );
}

function SchemaField({
  field,
  value,
  columns,
  error,
  onChange,
}: {
  field: ConfigField;
  value: unknown;
  columns: string[];
  error?: string;
  onChange: (value: unknown) => void;
}) {
  const label = (field.label || field.key) + (field.required ? " *" : "");
  const kind = field.type ?? "string";

  if (kind === "boolean") {
    // Booleans render as a bare checkbox row (no Field wrapper — matches the
    // hand-written forms' checkbox convention).
    return (
      <label className="flex items-center gap-2 text-xs text-slate-600">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        {field.label || field.key}
        {field.help && <span className="text-muted-foreground">— {field.help}</span>}
      </label>
    );
  }

  let control: React.ReactNode;
  switch (kind) {
    case "number":
    case "integer":
      control = (
        <Input
          type="number"
          value={value == null ? "" : String(value)}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step={kind === "integer" ? 1 : undefined}
          placeholder={field.placeholder}
          onChange={(e) => {
            if (e.target.value === "") return onChange(undefined);
            const n = Number(e.target.value);
            onChange(Number.isNaN(n) ? e.target.value : kind === "integer" ? Math.trunc(n) : n);
          }}
        />
      );
      break;
    case "select":
      control = (
        <Select value={value == null ? "" : String(value)} onChange={(e) => onChange(e.target.value)}>
          {!field.required && <option value="">—</option>}
          {(field.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </Select>
      );
      break;
    case "string_list":
      control = (
        <CsvListInput
          value={Array.isArray(value) ? (value as string[]) : []}
          onChange={(v) => onChange(v)}
          placeholder={field.placeholder}
        />
      );
      break;
    case "column":
      control = (
        <ColumnSelect
          value={typeof value === "string" ? value : ""}
          columns={columns}
          onChange={(v) => onChange(v)}
          placeholder={field.placeholder}
        />
      );
      break;
    case "column_list":
      control = (
        <ColumnMultiSelect
          value={Array.isArray(value) ? (value as string[]) : []}
          columns={columns}
          onChange={(v) => onChange(v)}
          placeholder={field.placeholder}
        />
      );
      break;
    default:
      control = (
        <Input
          type={field.secret ? "password" : "text"}
          value={value == null ? "" : String(value)}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }

  return (
    <Field label={label} error={error} help={field.help || undefined}>
      {control}
    </Field>
  );
}

/** Infer a field list from a node's default config, for plugin nodes that ship
 *  defaults but no config_schema — every key still gets an editable field. */
export function fieldsFromDefaults(defaults: Record<string, unknown>): ConfigField[] {
  return Object.entries(defaults).map(([key, v]) => {
    if (typeof v === "boolean") return { key, type: "boolean" as const, default: v };
    if (typeof v === "number") return { key, type: "number" as const, default: v };
    if (Array.isArray(v)) return { key, type: "string_list" as const, default: v };
    return { key, type: "string" as const, default: typeof v === "string" ? v : undefined };
  });
}
