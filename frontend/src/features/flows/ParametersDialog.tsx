import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Plus, Trash2, Variable } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  emptyRow,
  specToRow,
  validateRows,
  type ParamRow,
} from "@/lib/parameters";
import { PARAMETER_TYPES, type ParameterSpec, type ParameterType } from "@/lib/types/shared";

interface ParametersDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: ParameterSpec[];
  onChange: (specs: ParameterSpec[]) => void;
}

/**
 * Declare the parameters a flow exposes. Node configs reference them with
 * `{{ name }}`; values are supplied at run / schedule time. Edits are buffered
 * and only applied to the flow on Save.
 */
export function ParametersDialog({ open, onOpenChange, value, onChange }: ParametersDialogProps) {
  const [rows, setRows] = useState<ParamRow[]>([]);

  useEffect(() => {
    if (open) setRows(value.map(specToRow));
  }, [open, value]);

  const { errors, specs } = useMemo(() => validateRows(rows), [rows]);

  const update = (i: number, patch: Partial<ParamRow>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const add = () => setRows((rs) => [...rs, emptyRow()]);
  const remove = (i: number) => setRows((rs) => rs.filter((_, idx) => idx !== i));

  const save = () => {
    if (specs === null) return;
    onChange(specs);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Variable className="h-4 w-4 text-brand-600" /> Flow parameters
          </DialogTitle>
        </DialogHeader>

        <p className="text-xs text-muted-foreground">
          Reference a parameter in any node field with{" "}
          <code className="rounded bg-muted px-1 py-0.5">{"{{ name }}"}</code>. Supply values when you
          run or schedule the flow; defaults are used otherwise.
        </p>

        <div className="flex flex-col gap-3">
          {rows.length === 0 && (
            <p className="rounded-md border border-dashed border-border py-6 text-center text-sm text-muted-foreground">
              No parameters yet. Add one to make this flow reusable.
            </p>
          )}

          {rows.map((row, i) => (
            <div key={i} className="rounded-md border border-border p-3">
              <div className="flex flex-wrap items-end gap-2">
                <div className="flex min-w-[8rem] flex-1 flex-col gap-1">
                  <Label className="text-[11px]">Name</Label>
                  <Input
                    value={row.name}
                    onChange={(e) => update(i, { name: e.target.value })}
                    placeholder="input_path"
                    aria-label={`parameter-name-${i}`}
                  />
                </div>
                <div className="flex w-28 flex-col gap-1">
                  <Label className="text-[11px]">Type</Label>
                  <select
                    value={row.type}
                    onChange={(e) => update(i, { type: e.target.value as ParameterType })}
                    aria-label={`parameter-type-${i}`}
                    className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {PARAMETER_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex w-32 flex-col gap-1">
                  <Label className="text-[11px]">Default</Label>
                  {row.type === "boolean" ? (
                    <select
                      value={row.defaultText}
                      onChange={(e) => update(i, { defaultText: e.target.value })}
                      aria-label={`parameter-default-${i}`}
                      className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option value="">required</option>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <Input
                      value={row.defaultText}
                      onChange={(e) => update(i, { defaultText: e.target.value })}
                      placeholder="required"
                      aria-label={`parameter-default-${i}`}
                    />
                  )}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => remove(i)}
                  aria-label={`remove-parameter-${i}`}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </div>
              <div className="mt-2 flex flex-col gap-1">
                <Label className="text-[11px]">Description (optional)</Label>
                <Input
                  value={row.description}
                  onChange={(e) => update(i, { description: e.target.value })}
                  placeholder="What this parameter controls"
                  aria-label={`parameter-description-${i}`}
                />
              </div>
              {errors.has(i) && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-destructive">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {errors.get(i)}
                </p>
              )}
            </div>
          ))}

          <Button type="button" variant="outline" onClick={add} className="self-start">
            <Plus className="h-4 w-4" /> Add parameter
          </Button>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={save} disabled={specs === null}>
            Save parameters
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
