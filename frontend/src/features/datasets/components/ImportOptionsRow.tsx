import { cn } from "@/lib/utils";

/** Optional dialect overrides for uploads. Everything is auto-detected by
 *  default (European CSVs with `;`, Latin-1, decimal commas just work); this
 *  row exists for the cases detection can't decide — e.g. picking an Excel
 *  sheet — and to make the behavior transparent. */
export function ImportOptionsRow({
  options,
  onChange,
}: {
  options: { delimiter: string; encoding: string; decimal: string; sheet: string };
  onChange: (v: { delimiter: string; encoding: string; decimal: string; sheet: string }) => void;
}) {
  const set = (patch: Partial<typeof options>) => onChange({ ...options, ...patch });
  const selectCls =
    "h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring";
  return (
    <details className="rounded-lg border border-border bg-muted/30 px-3 py-2">
      <summary className="cursor-pointer select-none text-xs font-medium text-muted-foreground">
        Import options — auto-detected by default (CSV separator, encoding, decimals)
      </summary>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Separator
          <select
            className={selectCls}
            value={options.delimiter}
            onChange={(e) => set({ delimiter: e.target.value })}
          >
            <option value="">Auto</option>
            <option value=",">Comma (,)</option>
            <option value=";">Semicolon (;)</option>
            <option value={"\t"}>Tab</option>
            <option value="|">Pipe (|)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Encoding
          <select
            className={selectCls}
            value={options.encoding}
            onChange={(e) => set({ encoding: e.target.value })}
          >
            <option value="">Auto</option>
            <option value="utf-8">UTF-8</option>
            <option value="utf-8-sig">UTF-8 (BOM)</option>
            <option value="latin-1">Latin-1</option>
            <option value="cp1252">Windows-1252</option>
            <option value="utf-16">UTF-16</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Decimal mark
          <select
            className={selectCls}
            value={options.decimal}
            onChange={(e) => set({ decimal: e.target.value })}
          >
            <option value="">Auto</option>
            <option value=".">Point (.)</option>
            <option value=",">Comma (,)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Excel sheet (name or 0-based index)
          <input
            className={cn(selectCls, "w-48")}
            placeholder="First sheet"
            value={options.sheet}
            onChange={(e) => set({ sheet: e.target.value })}
          />
        </label>
      </div>
    </details>
  );
}
