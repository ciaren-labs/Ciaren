import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Loader2, Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ParameterValueFields } from "@/components/parameters/ParameterValueFields";
import { buildRunValues, defaultText } from "@/lib/parameters";
import { friendlyErrorMessage } from "@/lib/errors";
import { ENGINES, type Engine, type Flow, type ParameterValues } from "@/lib/types";
import { cn } from "@/lib/utils";

interface QuickRunDialogProps {
  /** The flow to run; null closes the dialog. */
  flow: Flow | null;
  onOpenChange: (open: boolean) => void;
  onRun: (args: { engine: Engine; parameters?: ParameterValues }) => void;
  isPending: boolean;
  error: unknown;
}

/**
 * Run a flow straight from the list. Beyond picking an engine, this collects
 * values for any parameters the flow declares — the same capability the editor's
 * Run button has — so a parameterized flow can't be launched from the list
 * without its required inputs (which the backend would otherwise reject) and its
 * defaults stay overridable.
 */
export function QuickRunDialog({ flow, onOpenChange, onRun, isPending, error }: QuickRunDialogProps) {
  const specs = useMemo(() => flow?.graph_json?.parameters ?? [], [flow]);
  const [engine, setEngine] = useState<Engine>("pandas");
  const [texts, setTexts] = useState<Record<string, string>>({});

  // Seed engine + parameter values whenever a (different) flow opens. Keyed on
  // the flow id and its parameter names, not array identity, so a background
  // flows refetch that re-creates the specs can't clobber in-progress edits.
  const specKey = specs.map((s) => s.name).join(",");
  useEffect(() => {
    if (!flow) return;
    setEngine(flow.graph_json?.engine ?? "pandas");
    const seed: Record<string, string> = {};
    for (const spec of specs) seed[spec.name] = defaultText(spec);
    setTexts(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow?.id, specKey]);

  const { errors, values } = useMemo(() => buildRunValues(specs, texts), [specs, texts]);
  // A required parameter left blank makes values null → block the run.
  const canRun = !isPending && (specs.length === 0 || values !== null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canRun) return;
    onRun({
      engine,
      parameters: specs.length > 0 && values ? values : undefined,
    });
  };

  return (
    <Dialog open={flow !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-brand-600" />
            Run "{flow?.name}"
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Engine</Label>
            <div className="flex items-center gap-2 overflow-hidden rounded-md border border-input text-sm">
              {ENGINES.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => setEngine(e)}
                  className={cn(
                    "flex-1 py-2 transition-colors",
                    engine === e
                      ? "bg-brand-600 font-medium text-white"
                      : "bg-background text-muted-foreground hover:bg-muted",
                  )}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {specs.length > 0 && (
            <div className="flex flex-col gap-3 rounded-md border border-border p-3">
              <div>
                <p className="text-sm font-medium">Parameters</p>
                <p className="text-[11px] text-muted-foreground">
                  Values for this run. Leave blank to use a parameter's default.
                </p>
              </div>
              <ParameterValueFields
                specs={specs}
                texts={texts}
                errors={errors}
                onChange={(name, value) => setTexts((t) => ({ ...t, [name]: value }))}
              />
            </div>
          )}

          {error != null && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {friendlyErrorMessage(error, "The run couldn't be started.")}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canRun}>
              {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
