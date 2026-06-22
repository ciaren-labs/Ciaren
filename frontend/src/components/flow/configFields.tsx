// Small helper inputs used inside node config forms. These work on plain
// values and call onChange — the parent form wires them to the editor store.
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
      <Input
        value={value ?? ""}
        placeholder={placeholder ?? "column name"}
        onChange={(e) => onChange(e.target.value)}
      />
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
  const selected = value ?? [];
  if (columns.length === 0) {
    return <CsvListInput value={value} onChange={onChange} placeholder={placeholder} />;
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
