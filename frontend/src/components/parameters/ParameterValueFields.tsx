import { AlertCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isRequired } from "@/lib/parameters";
import type { ParameterSpec } from "@/lib/types/shared";

interface ParameterValueFieldsProps {
  specs: ParameterSpec[];
  /** Raw text per parameter name (controlled by the parent). */
  texts: Record<string, string>;
  onChange: (name: string, value: string) => void;
  /** Per-parameter validation message (name → message). */
  errors?: Map<string, string>;
}

/**
 * Render an editable value field per parameter spec — shared by the run-now
 * dialog and the schedule form so both collect overrides identically.
 */
export function ParameterValueFields({ specs, texts, onChange, errors }: ParameterValueFieldsProps) {
  return (
    <>
      {specs.map((spec) => {
        const required = isRequired(spec);
        return (
          <div key={spec.name} className="flex flex-col gap-1.5">
            <Label className="flex items-center gap-1.5">
              <code className="rounded bg-muted px-1 py-0.5 text-xs">{spec.name}</code>
              <span className="text-[11px] font-normal text-muted-foreground">{spec.type}</span>
              {required && <span className="text-[11px] text-destructive">required</span>}
            </Label>
            {spec.type === "boolean" ? (
              <select
                value={texts[spec.name] ?? ""}
                onChange={(e) => onChange(spec.name, e.target.value)}
                aria-label={`value-${spec.name}`}
                className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {required && <option value="">choose…</option>}
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            ) : (
              <Input
                value={texts[spec.name] ?? ""}
                onChange={(e) => onChange(spec.name, e.target.value)}
                placeholder={required ? "required" : "default"}
                aria-label={`value-${spec.name}`}
              />
            )}
            {spec.description && (
              <p className="text-[11px] text-muted-foreground">{spec.description}</p>
            )}
            {errors?.has(spec.name) && (
              <p className="flex items-center gap-1.5 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {errors.get(spec.name)}
              </p>
            )}
          </div>
        );
      })}
    </>
  );
}
