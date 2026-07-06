import { AlertCircle, Clock } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  buildCron,
  describeCron,
  isValidCron,
  FREQUENCY_LABELS,
  WEEKDAY_NAMES,
  type CronFrequency,
  type CronModel,
} from "@/lib/cron";
import { cn } from "@/lib/utils";

const FREQUENCIES: CronFrequency[] = ["minutes", "hourly", "daily", "weekly", "monthly", "custom"];

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Friendly interval builder for a cron schedule. The parent owns the
 * {@link CronModel}; `buildCron(model)` yields the expression to submit.
 */
export function CronBuilder({
  model,
  onChange,
}: {
  model: CronModel;
  onChange: (model: CronModel) => void;
}) {
  const set = (patch: Partial<CronModel>) => onChange({ ...model, ...patch });

  // "HH:MM" <-> hour/minute for the native time picker.
  const timeValue = `${model.hour.toString().padStart(2, "0")}:${model.minute
    .toString()
    .padStart(2, "0")}`;
  const onTime = (v: string) => {
    const [h, m] = v.split(":").map((n) => Number(n));
    if (!Number.isNaN(h) && !Number.isNaN(m)) set({ hour: h, minute: m });
  };

  const cron = buildCron(model);
  const valid = isValidCron(cron);

  return (
    <div className="flex flex-col gap-3">
      {/* Frequency picker */}
      <div className="flex flex-col gap-1.5">
        <Label>Frequency</Label>
        <div className="flex flex-wrap gap-1.5">
          {FREQUENCIES.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => set({ frequency: f })}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm transition-colors",
                model.frequency === f
                  ? "border-brand-600 bg-brand-600 font-medium text-white"
                  : "border-input bg-background text-muted-foreground hover:bg-muted",
              )}
            >
              {FREQUENCY_LABELS[f]}
            </button>
          ))}
        </div>
      </div>

      {/* Frequency-specific controls */}
      {model.frequency === "minutes" && (
        <div className="flex flex-col gap-1.5">
          <Label>Every N minutes</Label>
          <Input
            type="number"
            min={1}
            max={59}
            value={model.intervalMinutes}
            onChange={(e) => set({ intervalMinutes: clamp(e.target.value, 1, 59) })}
            className="w-28"
          />
        </div>
      )}

      {model.frequency === "hourly" && (
        <div className="flex flex-col gap-1.5">
          <Label>Minute past the hour</Label>
          <Input
            type="number"
            min={0}
            max={59}
            value={model.minute}
            onChange={(e) => set({ minute: clamp(e.target.value, 0, 59) })}
            className="w-28"
          />
        </div>
      )}

      {model.frequency === "daily" && (
        <div className="flex flex-col gap-1.5">
          <Label>Time of day</Label>
          <Input type="time" value={timeValue} onChange={(e) => onTime(e.target.value)} className="w-36" />
        </div>
      )}

      {model.frequency === "weekly" && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Day of week</Label>
            <select
              className={SELECT_CLASS}
              value={model.weekday}
              onChange={(e) => set({ weekday: Number(e.target.value) })}
            >
              {WEEKDAY_NAMES.map((name, i) => (
                <option key={name} value={i}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Time of day</Label>
            <Input type="time" value={timeValue} onChange={(e) => onTime(e.target.value)} className="w-36" />
          </div>
        </div>
      )}

      {model.frequency === "monthly" && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Day of month</Label>
            <Input
              type="number"
              min={1}
              max={31}
              value={model.monthday}
              onChange={(e) => set({ monthday: clamp(e.target.value, 1, 31) })}
              className="w-28"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Time of day</Label>
            <Input type="time" value={timeValue} onChange={(e) => onTime(e.target.value)} className="w-36" />
          </div>
        </div>
      )}

      {model.frequency === "custom" && (
        <div className="flex flex-col gap-1.5">
          <Label>Cron expression</Label>
          <Input
            value={model.raw}
            onChange={(e) => set({ raw: e.target.value })}
            placeholder="*/15 * * * *"
            className="font-mono"
          />
          <p className="text-[11px] text-muted-foreground">
            Standard 5-field cron: minute hour day-of-month month day-of-week.
          </p>
        </div>
      )}

      {/* Live summary */}
      <div
        className={cn(
          "flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
          valid
            ? "border-border bg-muted/40 text-foreground"
            : "border-destructive/30 bg-destructive/10 text-destructive",
        )}
      >
        {valid ? (
          <Clock className="h-4 w-4 shrink-0 text-brand-600" />
        ) : (
          <AlertCircle className="h-4 w-4 shrink-0" />
        )}
        <span>{describeCron(cron)}</span>
        {valid && (
          <code className="ml-auto rounded bg-background px-1.5 py-0.5 text-[11px] text-muted-foreground">
            {cron}
          </code>
        )}
      </div>
    </div>
  );
}

function clamp(raw: string, min: number, max: number): number {
  const n = Number(raw);
  if (Number.isNaN(n)) return min;
  return Math.min(max, Math.max(min, Math.trunc(n)));
}
