import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buildRunValues, defaultText, isRequired } from "@/lib/parameters";
import type { ParameterSpec, ParameterValues } from "@/lib/types";

interface RunParametersDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  specs: ParameterSpec[];
  submitting?: boolean;
  /** Verb shown on the submit button ("Run" or "Save"). */
  submitLabel?: string;
  /** Pre-fill overrides (e.g. a schedule's saved values) instead of defaults. */
  initialValues?: ParameterValues | null;
  onSubmit: (values: ParameterValues) => void;
}

/**
 * Collect parameter values before running (or scheduling) a parameterized flow.
 * Fields pre-fill with each parameter's default (or a supplied override set);
 * a blank field with a default falls back to that default, while a blank
 * required field blocks submission.
 */
export function RunParametersDialog({
  open,
  onOpenChange,
  specs,
  submitting = false,
  submitLabel = "Run",
  initialValues = null,
  onSubmit,
}: RunParametersDialogProps) {
  const [texts, setTexts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    const seed: Record<string, string> = {};
    for (const spec of specs) {
      const override = initialValues?.[spec.name];
      seed[spec.name] =
        override !== undefined && override !== null ? String(override) : defaultText(spec);
    }
    setTexts(seed);
  }, [open, specs, initialValues]);

  const { errors, values } = useMemo(() => buildRunValues(specs, texts), [specs, texts]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (values === null || submitting) return;
    onSubmit(values);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Run with parameters</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          {specs.map((spec) => (
            <div key={spec.name} className="flex flex-col gap-1.5">
              <Label className="flex items-center gap-1.5">
                <code className="rounded bg-muted px-1 py-0.5 text-xs">{spec.name}</code>
                <span className="text-[11px] font-normal text-muted-foreground">{spec.type}</span>
                {isRequired(spec) && <span className="text-[11px] text-destructive">required</span>}
              </Label>
              {spec.type === "boolean" ? (
                <select
                  value={texts[spec.name] ?? ""}
                  onChange={(e) => setTexts((t) => ({ ...t, [spec.name]: e.target.value }))}
                  aria-label={`value-${spec.name}`}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {!isRequired(spec) ? null : <option value="">choose…</option>}
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : (
                <Input
                  value={texts[spec.name] ?? ""}
                  onChange={(e) => setTexts((t) => ({ ...t, [spec.name]: e.target.value }))}
                  placeholder={isRequired(spec) ? "required" : "default"}
                  aria-label={`value-${spec.name}`}
                />
              )}
              {spec.description && (
                <p className="text-[11px] text-muted-foreground">{spec.description}</p>
              )}
              {errors.has(spec.name) && (
                <p className="flex items-center gap-1.5 text-xs text-destructive">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {errors.get(spec.name)}
                </p>
              )}
            </div>
          ))}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={values === null || submitting}>
              <Play className="h-4 w-4" /> {submitting ? "Working…" : submitLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
