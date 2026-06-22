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
import { useFlows } from "@/features/flows/hooks";
import { ApiError } from "@/lib/api";
import { buildCron, parseCron, isValidCron, DEFAULT_CRON_MODEL, type CronModel } from "@/lib/cron";
import { COMMON_TIMEZONES } from "@/stores/timezoneStore";
import type { Schedule, ScheduleCreate } from "@/lib/types";
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
  submitting: boolean;
  error: unknown;
  onSubmit: (flowId: string, body: ScheduleCreate) => void;
}

export function ScheduleFormDialog({
  open,
  onOpenChange,
  schedule,
  lockedFlowId,
  submitting,
  error,
  onSubmit,
}: ScheduleFormDialogProps) {
  const { data: flows } = useFlows();
  const isEdit = !!schedule;

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

  // Reset the form each time the dialog opens (create or a specific schedule).
  useEffect(() => {
    if (!open) return;
    setFlowId(schedule?.flow_id ?? lockedFlowId ?? "");
    setName(schedule?.name ?? "");
    setDescription(schedule?.description ?? "");
    setCronModel(schedule ? parseCron(schedule.cron) : DEFAULT_CRON_MODEL);
    setTimezone(schedule?.timezone ?? "UTC");
    setEngine(schedule?.engine ?? "");
    setEnabled(schedule?.enabled ?? true);
    setCatchUp(schedule?.catch_up ?? false);
    setMaxRetries(schedule?.max_retries ?? 0);
    setRetryDelay(schedule?.retry_delay_seconds ?? 60);
    setShowAdvanced(!!schedule && (schedule.catch_up || schedule.max_retries > 0));
  }, [open, schedule, lockedFlowId]);

  const cron = buildCron(cronModel);
  const cronOk = isValidCron(cron);
  const canSubmit = !!flowId && cronOk && !submitting;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(flowId, {
      cron,
      name: name.trim() || undefined,
      description: description.trim() || undefined,
      timezone,
      engine: engine || null,
      enabled,
      catch_up: catchUp,
      max_retries: maxRetries,
      retry_delay_seconds: retryDelay,
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
          {/* Flow */}
          <div className="flex flex-col gap-1.5">
            <Label>Flow</Label>
            {isEdit || lockedFlowId ? (
              <div className="flex items-center gap-2 rounded-md border border-input bg-muted/40 px-3 py-2 text-sm">
                <Workflow className="h-4 w-4 text-brand-600" />
                {lockedFlowName ?? "Selected flow"}
              </div>
            ) : (
              <SearchableSelect
                value={flowId}
                onChange={setFlowId}
                allLabel="Select a flow…"
                placeholder="Search flows…"
                options={(flows ?? [])
                  .filter((f) => !f.is_disabled)
                  .map((f) => ({ value: f.id, label: f.name }))}
              />
            )}
          </div>

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

          {/* Enabled */}
          <label className="flex items-center justify-between rounded-md border border-input px-3 py-2.5">
            <span className="flex flex-col">
              <span className="text-sm font-medium">Enabled</span>
              <span className="text-[11px] text-muted-foreground">
                When off, the schedule is saved but never fires automatically.
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

          {error instanceof ApiError && (
            <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {error.message}
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
