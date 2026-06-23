// Small helper inputs used inside node config forms. These work on plain
// values and call onChange — the parent form wires them to the editor store.
import { useState } from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { InfoHint } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface FieldProps {
  label: string;
  error?: string;
  children: React.ReactNode;
  hint?: string;
  /** Longer explanation shown in a hover tooltip next to the label. */
  help?: string;
}

export function Field({ label, error, children, hint, help }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5">
        <Label>{label}</Label>
        {help && <InfoHint text={help} />}
      </div>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
      {error && <p className="text-[11px] font-medium text-destructive">{error}</p>}
    </div>
  );
}

/** Merge known columns with any already-selected values not in the schema. */
function withSelected(columns: string[], extra: string[]): string[] {
  const seen = new Set(columns);
  return [...columns, ...extra.filter((c) => c && !seen.has(c))];
}

/** Shown when a column picker has no schema yet (node not connected to a source). */
export function ConnectHint() {
  return (
    <p className="text-[11px] text-muted-foreground">
      Connect an upstream input to pick columns from its schema. You can also type
      names manually.
    </p>
  );
}

interface CsvListInputProps {
  value: string[] | undefined;
  onChange: (v: string[]) => void;
  placeholder?: string;
}

/** Comma-separated list editor that maps to a string[] (free-text fallback). */
export function CsvListInput({ value, onChange, placeholder }: CsvListInputProps) {
  return (
    <Input
      value={(value ?? []).join(", ")}
      placeholder={placeholder ?? "col_a, col_b"}
      onChange={(e) =>
        onChange(
          e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        )
      }
    />
  );
}

interface ColumnSelectProps {
  value: string | undefined;
  columns: string[];
  onChange: (v: string) => void;
  placeholder?: string;
}

/** Single-column picker. Falls back to a free-text input when no schema yet. */
export function ColumnSelect({ value, columns, onChange, placeholder }: ColumnSelectProps) {
  if (columns.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <Input
          value={value ?? ""}
          placeholder={placeholder ?? "column name"}
          onChange={(e) => onChange(e.target.value)}
        />
        <ConnectHint />
      </div>
    );
  }
  const options = withSelected(columns, value ? [value] : []);
  return (
    <Select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select a column…</option>
      {options.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </Select>
  );
}

interface ColumnMultiSelectProps {
  value: string[] | undefined;
  columns: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}

/** Multi-column picker rendered as toggle chips, with free-text fallback. */
export function ColumnMultiSelect({
  value,
  columns,
  onChange,
  placeholder,
}: ColumnMultiSelectProps) {
  // Tolerate a scalar (or missing) value so a malformed config — e.g. a join
  // key saved as a bare string — can't crash the whole editor with a blank page.
  const selected = Array.isArray(value) ? value : value != null ? [String(value)] : [];
  if (columns.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <CsvListInput value={selected} onChange={onChange} placeholder={placeholder} />
        <ConnectHint />
      </div>
    );
  }
  const options = withSelected(columns, selected);
  const toggle = (c: string) =>
    selected.includes(c)
      ? onChange(selected.filter((x) => x !== c))
      : onChange([...selected, c]);

  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((c) => {
        const on = selected.includes(c);
        return (
          <button
            key={c}
            type="button"
            onClick={() => toggle(c)}
            className={cn(
              "rounded-full border px-2.5 py-0.5 text-xs font-medium transition-all",
              on
                ? "border-primary bg-primary text-primary-foreground shadow-sm"
                : "border-border bg-background text-slate-600 hover:border-primary/50 hover:bg-muted",
            )}
          >
            {c}
          </button>
        );
      })}
    </div>
  );
}

interface ColumnKeyedEditorProps {
  value: Record<string, string> | undefined;
  /** Known upstream columns (this editor is only used when non-empty). */
  columns: string[];
  onChange: (v: Record<string, string>) => void;
  /** Renders the value cell for a row (e.g. a dtype or aggregation select). */
  renderValue: (val: string, onValueChange: (v: string) => void) => React.ReactNode;
  /** Value assigned to a newly-added column. */
  defaultValue: string;
}

/**
 * Edits a Record<column, value> where the key is chosen from a real column
 * dropdown (no free typing). Each row has a remove button; the add control only
 * offers columns not yet used. Used by Change Type, Group-By and Rename when the
 * upstream schema is known.
 */
export function ColumnKeyedEditor({
  value,
  columns,
  onChange,
  renderValue,
  defaultValue,
}: ColumnKeyedEditorProps) {
  const entries = Object.entries(value ?? {});
  const used = new Set(entries.map(([k]) => k));

  const commit = (next: [string, string][]) => {
    const obj: Record<string, string> = {};
    for (const [k, v] of next) if (k) obj[k] = v;
    onChange(obj);
  };
  const updateKey = (idx: number, key: string) =>
    commit(entries.map((e, i) => (i === idx ? [key, e[1]] : e)));
  const updateVal = (idx: number, val: string) =>
    commit(entries.map((e, i) => (i === idx ? [e[0], val] : e)));
  const removeRow = (idx: number) => commit(entries.filter((_, i) => i !== idx));
  const addRow = (key: string) => key && commit([...entries, [key, defaultValue]]);

  const available = columns.filter((c) => !used.has(c));

  return (
    <div className="flex flex-col gap-1.5">
      {entries.map(([k, v], idx) => {
        const options = withSelected(columns.filter((c) => c === k || !used.has(c)), [k]);
        return (
          <div key={idx} className="flex items-center gap-1">
            <Select
              className="h-8 flex-1"
              value={k}
              onChange={(e) => updateKey(idx, e.target.value)}
            >
              {options.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
            {renderValue(v, (nv) => updateVal(idx, nv))}
            <button
              type="button"
              onClick={() => removeRow(idx)}
              aria-label={`Remove ${k}`}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
      {available.length > 0 && (
        <Select className="h-8" value="" onChange={(e) => addRow(e.target.value)}>
          <option value="">+ Add column…</option>
          {available.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      )}
    </div>
  );
}

interface KeyValueEditorProps {
  value: Record<string, string> | undefined;
  onChange: (v: Record<string, string>) => void;
  keyLabel?: string;
  valueLabel?: string;
  /** Column suggestions offered for the key field via a datalist. */
  keySuggestions?: string[];
}

/** Edits a Record<string,string> as rows of key/value pairs. */
export function KeyValueEditor({
  value,
  onChange,
  keyLabel = "key",
  valueLabel = "value",
  keySuggestions,
}: KeyValueEditorProps) {
  const entries = Object.entries(value ?? {});
  const rows = [...entries, ["", ""]] as [string, string][];
  const listId = keySuggestions?.length ? `cols-${keyLabel}` : undefined;

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
          {keySuggestions!.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      )}
      {rows.map(([k, v], idx) => (
        <div key={idx} className="flex gap-1">
          <Input
            className="h-8"
            list={listId}
            placeholder={keyLabel}
            value={k}
            onChange={(e) => update(idx, e.target.value, v)}
          />
          <Input
            className="h-8"
            placeholder={valueLabel}
            value={v}
            onChange={(e) => update(idx, k, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
}

// ---- Delimiter picker -------------------------------------------------------

const DELIMITER_PRESETS = [
  { label: "Comma", value: "," },
  { label: "Tab", value: "\t" },
  { label: "Pipe", value: "|" },
  { label: "Semicolon", value: ";" },
  { label: "Space", value: " " },
] as const;

interface DelimiterPickerProps {
  value: string | undefined;
  onChange: (v: string) => void;
}

/** Preset delimiter buttons + free-text fallback for splitColumn. */
export function DelimiterPicker({ value, onChange }: DelimiterPickerProps) {
  const displayVal = value === "\t" ? "\\t" : (value ?? "");
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap gap-1">
        {DELIMITER_PRESETS.map((p) => {
          const on = value === p.value;
          return (
            <button
              key={p.label}
              type="button"
              onClick={() => onChange(p.value)}
              className={cn(
                "rounded border px-2 py-0.5 text-xs font-medium transition-colors",
                on
                  ? "border-primary bg-primary text-primary-foreground shadow-sm"
                  : "border-border bg-background text-slate-600 hover:border-primary/50 hover:bg-muted",
              )}
            >
              {p.label}
            </button>
          );
        })}
      </div>
      <Input
        value={displayVal}
        placeholder="or type a custom delimiter…"
        onChange={(e) => {
          const v = e.target.value;
          onChange(v === "\\t" ? "\t" : v);
        }}
      />
    </div>
  );
}

// ---- Date format picker -----------------------------------------------------

const DATE_FORMAT_PRESETS = [
  { label: "YYYY-MM-DD", value: "%Y-%m-%d" },
  { label: "DD/MM/YYYY", value: "%d/%m/%Y" },
  { label: "MM/DD/YYYY", value: "%m/%d/%Y" },
  { label: "YYYY-MM-DD HH:MM:SS", value: "%Y-%m-%d %H:%M:%S" },
  { label: "DD-MMM-YYYY", value: "%d-%b-%Y" },
] as const;

interface DateFormatPickerProps {
  value: string | undefined;
  onChange: (v: string) => void;
}

/** Common strptime format presets + free-text override for date parsing. */
export function DateFormatPicker({ value, onChange }: DateFormatPickerProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap gap-1">
        {DATE_FORMAT_PRESETS.map((p) => {
          const on = value === p.value;
          return (
            <button
              key={p.label}
              type="button"
              onClick={() => onChange(p.value)}
              className={cn(
                "rounded border px-2 py-0.5 font-mono text-[11px] font-medium transition-colors",
                on
                  ? "border-primary bg-primary text-primary-foreground shadow-sm"
                  : "border-border bg-background text-slate-600 hover:border-primary/50 hover:bg-muted",
              )}
            >
              {p.label}
            </button>
          );
        })}
      </div>
      <Input
        value={value ?? ""}
        placeholder="or type a custom format…"
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

// ---- Tag (chip) input -------------------------------------------------------

interface TagInputProps {
  /** Stored as a comma-separated string (matches filterRows "in" wire format). */
  value: string | undefined;
  onChange: (v: string) => void;
  placeholder?: string;
}

/**
 * Chip-based tag input for the filterRows "in" operator.
 * Press Enter or comma to confirm a tag; Backspace on empty removes the last one.
 */
export function TagInput({ value, onChange, placeholder }: TagInputProps) {
  const [draft, setDraft] = useState("");
  const tags = (value ?? "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  const commit = (next: string[]) => onChange(next.join(", "));

  const addTag = (raw: string) => {
    const tag = raw.trim();
    if (!tag || tags.includes(tag)) {
      setDraft("");
      return;
    }
    commit([...tags, tag]);
    setDraft("");
  };

  const removeTag = (tag: string) => commit(tags.filter((t) => t !== tag));

  return (
    <div className="flex flex-col gap-1">
      <div
        className="flex min-h-[36px] flex-wrap items-center gap-1 rounded-md border border-input bg-background px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring"
        onClick={(e) => (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus()}
      >
        {tags.map((t) => (
          <span
            key={t}
            className="flex items-center gap-0.5 rounded-full bg-primary/10 px-2 py-0 text-[11px] font-medium text-primary"
          >
            {t}
            <button
              type="button"
              onClick={() => removeTag(t)}
              className="ml-0.5 text-primary/60 hover:text-primary"
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-[80px] flex-1 bg-transparent text-xs outline-none"
          value={draft}
          placeholder={tags.length === 0 ? (placeholder ?? "type and press Enter…") : "add more…"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              addTag(draft);
            } else if (e.key === "Backspace" && !draft && tags.length > 0) {
              removeTag(tags[tags.length - 1]);
            }
          }}
          onBlur={() => {
            if (draft.trim()) addTag(draft);
          }}
        />
      </div>
      {tags.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          {tags.length} value{tags.length !== 1 ? "s" : ""} — rows matching any of these are kept
        </p>
      )}
    </div>
  );
}
