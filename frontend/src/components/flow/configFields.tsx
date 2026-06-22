// Small helper inputs used inside node config forms. These work on plain
// values and call onChange — the parent form wires them to react-hook-form.
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface FieldProps {
  label: string;
  error?: string;
  children: React.ReactNode;
  hint?: string;
}

export function Field({ label, error, children, hint }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
      {error && <p className="text-[11px] text-destructive">{error}</p>}
    </div>
  );
}

interface CsvListInputProps {
  value: string[] | undefined;
  onChange: (v: string[]) => void;
  placeholder?: string;
}

/** Comma-separated list editor that maps to a string[]. */
export function CsvListInput({
  value,
  onChange,
  placeholder,
}: CsvListInputProps) {
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

interface KeyValueEditorProps {
  value: Record<string, string> | undefined;
  onChange: (v: Record<string, string>) => void;
  keyLabel?: string;
  valueLabel?: string;
}

/** Edits a Record<string,string> as rows of key/value pairs. */
export function KeyValueEditor({
  value,
  onChange,
  keyLabel = "key",
  valueLabel = "value",
}: KeyValueEditorProps) {
  const entries = Object.entries(value ?? {});
  const rows = [...entries, ["", ""]] as [string, string][];

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
