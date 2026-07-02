import { useEffect, useState } from "react";
import { AlertCircle, ChevronDown, Workflow } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { CronBuilder } from "@/components/schedules/CronBuilder";
import { ParameterValueFields } from "@/components/parameters/ParameterValueFields";
import { useFlows } from "@/features/flows/hooks";
import { useProjects } from "@/features/projects/hooks";
import { friendlyErrorMessage } from "@/lib/errors";
import { buildCron, parseCron, isValidCron, DEFAULT_CRON_MODEL, type CronModel } from "@/lib/cron";
import { buildRunValues, defaultText } from "@/lib/parameters";
import { COMMON_TIMEZONES } from "@/stores/timezoneStore";
import type { ParameterSpec, Schedule, ScheduleCreate } from "@/lib/types";
import { cn } from "@/lib/utils";

const ENGINES = [
  { value: "", label: "Server default" },
  { value: "pandas", label: "pandas" },
  { value: "polars", label: "polars" },
] as const;

const TZ_OPTIONS = COMMON_TIMEZONES.filter((tz) => tz.value !== "");

interface ScheduleFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Present → edit mode (the flow can't be changed after creation). */
  schedule?: Schedule | null;
  /** Pre-select (and lock) a flow when creating from the flows page. */
  lockedFlowId?: string;
  /** Live parameter specs to use instead of the saved flow's (editor context),
   *  so just-declared (and unsaved) parameters still get override fields. */
  parameterSpecs?: ParameterSpec[];
  submitting: boolean;
  error: unknown;
  onSubmit: (flowId: string, body: ScheduleCreate) => void;
}

export function ScheduleFormDialog({
  open,
  onOpenChange,
  schedule,
  lockedFlowId,
  parameterSpecs,
  submitting,
  error,
  onSubmit,
}: ScheduleFormDialogProps) {
  const { data: flows } = useFlows();
  const { data: projects } = useProjects();
  const isEdit = !!schedule;

  const [projectId, setProjectId] = useState("");
  const [flowId, setFlowId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cronModel, setCronModel] = useState<CronModel>(DEFAULT_CRON_MODEL);
  const [timezone, setTimezone] = useState("UTC");
  const [engine, setEngine] = useState<string>("");
  const [enabled, setEnabled] = useState(true);
  const [catchUp, setCatchUp] = useState(false);
  const [maxRetries, setMaxRetries] = useState(0);
  const [retryDelay, setRetryDelay] = useState(60);
  const [showAdvanced, setShowAdvanced] = useState(false);
  // Override values for the selected flow's parameters (raw text per name).
  const [paramTexts, setParamTexts] = useState<Record<string, string>>({});

  // Parameter specs that drive the overrides section. Prefer live editor specs
  // (so unsaved, just-declared parameters appear); otherwise read the saved flow.
  const selectedFlow = (flows ?? []).find((f) => f.id === flowId);
  const paramSpecs = parameterSpecs ?? selectedFlow?.graph_json?.parameters ?? [];

  // Reset the form each time the dialog opens (create or a specific schedule).
  useEffect(() => {
    if (!open) return;
    // The project selector is only shown for fresh creation (flow not locked),
    // so it always starts empty; flow is pre-set when editing/locked.
    setProjectId("");
    setFlowId(schedule?.flow_id ?? lockedFlowId ?? "");
    setName(schedule?.name ?? "");
    setDescription(schedule?.description ?? "");
    setCronModel(schedule ? parseCron(schedule.cron) : DEFAULT_CRON_MODEL);
    setTimezone(schedule?.timezone ?? "UTC");
    setEngine(schedule?.engine ?? "");
    setEnabled(schedule?.is_enabled ?? true);
    setCatchUp(schedule?.catch_up ?? false);
    setMaxRetries(schedule?.max_retries ?? 0);
    setRetryDelay(schedule?.retry_delay_seconds ?? 60);
    setShowAdvanced(!!schedule && (schedule.catch_up || schedule.max_retries > 0));
  }, [open, schedule, lockedFlowId]);

  // Seed parameter overrides from the schedule's saved values (edit) or the
  // flow's declared defaults. Re-runs when the flow or its parameter set changes,
  // but a steady spec list (e.g. a background flows refetch) won't clobber edits.
  const specKey = paramSpecs.map((s) => s.name).join(",");
  useEffect(() => {
    if (!open) return;
    const seed: Record<string, string> = {};
    for (const spec of paramSpecs) {
      const override = schedule?.parameters?.[spec.name];
      seed[spec.name] =
        override !== undefined && override !== null ? String(override) : defaultText(spec);
    }
    setParamTexts(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, flowId, schedule?.id, specKey]);

  const { errors: paramErrors, values: paramValues } = buildRunValues(paramSpecs, paramTexts);

  const cron = buildCron(cronModel);
  const cronOk = isValidCron(cron);
  const canSubmit =
    !!flowId && cronOk && !submitting && (paramSpecs.length === 0 || paramValues !== null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(flowId, {
      cron,
      name: name.trim() || undefined,
      description: description.trim() || undefined,
      timezone,
      engine: engine || null,
      is_enabled: enabled,
      catch_up: catchUp,
      max_retries: maxRetries,
      retry_delay_seconds: retryDelay,
      // Send overrides only when the flow has parameters; an empty set clears
      // them (null) so fired runs fall back to the declared defaults.
      parameters:
        paramSpecs.length === 0
          ? undefined
          : paramValues && Object.keys(paramValues).length > 0
            ? paramValues
            : null,
    });
  };

  const lockedFlowName =
    isEdit || lockedFlowId
      ? (flows ?? []).find((f) => f.id === (schedule?.flow_id ?? lockedFlowId))?.name
      : undefined;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit schedule" : "New schedule"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          {/* Project + Flow (project first; flow list is scoped to it) */}
          {isEdit || lockedFlowId ? (
            <div className="flex flex-col gap-1.5">
              <Label>Flow</Label>
              <div className="flex items-center gap-2 rounded-md border border-input bg-muted/40 px-3 py-2 text-sm">
                <Workflow className="h-4 w-4 text-brand-600" />
                {lockedFlowName ?? "Selected flow"}
              </div>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label>Project</Label>
                <SearchableSelect
                  value={projectId}
                  onChange={(v) => {
                    setProjectId(v);
                    setFlowId(""); // reset flow when the project changes
                  }}
                  allLabel="All projects"
                  placeholder="Search projects…"
                  options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Flow</Label>
                <SearchableSelect
                  value={flowId}
                  onChange={setFlowId}
                  allLabel="Select a flow…"
                  placeholder="Search flows…"
                  options={(flows ?? [])
                    .filter((f) => !f.is_disabled)
                    .filter((f) => !projectId || f.project_id === projectId)
                    .map((f) => ({ value: f.id, label: f.name }))}
                />
                {projectId && (flows ?? []).filter((f) => !f.is_disabled && f.project_id === projectId).length === 0 && (
                  <p className="text-[11px] text-muted-foreground">No runnable flows in this project.</p>
                )}
              </div>
            </>
          )}

          {/* Name */}
          <div className="flex flex-col gap-1.5">
            <Label>Name (optional)</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nightly refresh"
            />
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <Label>Description (optional)</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this schedule is for"
            />
          </div>

          {/* Interval builder */}
          <CronBuilder model={cronModel} onChange={setCronModel} />

          {/* Timezone */}
          <div className="flex flex-col gap-1.5">
            <Label>Timezone</Label>
            <SearchableSelect
              value={timezone}
              onChange={(v) => setTimezone(v || "UTC")}
              allLabel="UTC"
              placeholder="Search timezone…"
              options={TZ_OPTIONS.map((tz) => ({ value: tz.value, label: tz.label }))}
            />
            <p className="text-[11px] text-muted-foreground">
              The interval is interpreted in this timezone (DST-aware). The first run is computed
              when you save.
            </p>
          </div>

          {/* Engine */}
          <div className="flex flex-col gap-1.5">
            <Label>Engine</Label>
            <div className="flex items-center gap-2 overflow-hidden rounded-md border border-input text-sm">
              {ENGINES.map((e) => (
                <button
                  key={e.value || "default"}
                  type="button"
                  onClick={() => setEngine(e.value)}
                  className={cn(
                    "flex-1 py-2 transition-colors",
                    engine === e.value
                      ? "bg-brand-600 font-medium text-white"
                      : "bg-background text-muted-foreground hover:bg-muted",
                  )}
                >
                  {e.label}
                </button>
              ))}
            </div>
          </div>

          {/* Parameter overrides (only when the selected flow declares parameters) */}
          {paramSpecs.length > 0 && (
            <div className="flex flex-col gap-3 rounded-md border border-border p-3">
              <div>
                <p className="text-sm font-medium">Parameter values</p>
                <p className="text-[11px] text-muted-foreground">
                  Applied to every run this schedule fires. Leave blank to use a parameter's default.
                </p>
              </div>
              <ParameterValueFields
                specs={paramSpecs}
                texts={paramTexts}
                errors={paramErrors}
                onChange={(name, value) => setParamTexts((t) => ({ ...t, [name]: value }))}
              />
            </div>
          )}

          {/* Enabled */}
          <label className="flex items-center justify-between rounded-md border border-input px-3 py-2.5">
            <span className="flex flex-col">
              <span className="text-sm font-medium">Enabled</span>
              <span className="text-[11px] text-muted-foreground">
                Fires automatically at the scheduled times. Turn off to save it as paused.
              </span>
            </span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 accent-brand-600"
            />
          </label>

          {/* Advanced */}
          <div className="rounded-md border border-border">
            <button
              type="button"
              onClick={() => setShowAdvanced((s) => !s)}
              className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              Advanced options
              <ChevronDown
                className={cn("h-4 w-4 transition-transform", showAdvanced && "rotate-180")}
              />
            </button>
            {showAdvanced && (
              <div className="flex flex-col gap-3 border-t border-border p-3">
                <label className="flex items-center justify-between">
                  <span className="flex flex-col">
                    <span className="text-sm font-medium">Catch up missed runs</span>
                    <span className="text-[11px] text-muted-foreground">
                      Fire once for a slot missed while the server was down.
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    checked={catchUp}
                    onChange={(e) => setCatchUp(e.target.checked)}
                    className="h-4 w-4 accent-brand-600"
                  />
                </label>

                <div className="flex flex-wrap gap-3">
                  <div className="flex flex-col gap-1.5">
                    <Label>Max retries</Label>
                    <Input
                      type="number"
                      min={0}
                      max={10}
                      value={maxRetries}
                      onChange={(e) =>
                        setMaxRetries(Math.min(10, Math.max(0, Number(e.target.value) || 0)))
                      }
                      className="w-28"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label>Retry delay (s)</Label>
                    <Input
                      type="number"
                      min={1}
                      value={retryDelay}
                      onChange={(e) => setRetryDelay(Math.max(1, Number(e.target.value) || 1))}
                      className="w-32"
                    />
                  </div>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  On failure, retry with exponential backoff seeded by the delay (capped at 1h)
                  before falling back to the next slot.
                </p>
              </div>
            )}
          </div>

          {error != null && (
            <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {friendlyErrorMessage(error)}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {submitting ? "Saving…" : isEdit ? "Save changes" : "Create schedule"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
