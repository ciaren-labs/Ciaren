import { useEffect, useMemo, useState } from "react";
import { Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ParameterValueFields } from "@/components/parameters/ParameterValueFields";
import { buildRunValues, defaultText } from "@/lib/parameters";
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
          <ParameterValueFields
            specs={specs}
            texts={texts}
            errors={errors}
            onChange={(name, value) => setTexts((t) => ({ ...t, [name]: value }))}
          />

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
