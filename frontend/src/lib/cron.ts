// Helpers for the schedule cron builder: translate between a friendly
// frequency/time model and a standard 5-field cron expression, validate
// expressions early (the backend's croniter is authoritative), and render a
// human-readable description for the UI.
//
// Field order is the POSIX standard: minute hour day-of-month month day-of-week.

export type CronFrequency = "hourly" | "daily" | "weekly" | "monthly" | "custom";

export interface CronModel {
  frequency: CronFrequency;
  /** 0-59 */
  minute: number;
  /** 0-23 */
  hour: number;
  /** 0 (Sunday) – 6 (Saturday) */
  weekday: number;
  /** 1-31 */
  monthday: number;
  /** Raw expression, used when frequency is "custom". */
  raw: string;
}

export const WEEKDAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

export const FREQUENCY_LABELS: Record<CronFrequency, string> = {
  hourly: "Hourly",
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  custom: "Custom (cron)",
};

export const DEFAULT_CRON_MODEL: CronModel = {
  frequency: "daily",
  minute: 0,
  hour: 9,
  weekday: 1,
  monthday: 1,
  raw: "0 9 * * *",
};

/** Build a cron expression from the friendly model. */
export function buildCron(model: CronModel): string {
  const { frequency, minute, hour, weekday, monthday, raw } = model;
  switch (frequency) {
    case "hourly":
      return `${minute} * * * *`;
    case "daily":
      return `${minute} ${hour} * * *`;
    case "weekly":
      return `${minute} ${hour} * * ${weekday}`;
    case "monthly":
      return `${minute} ${hour} ${monthday} * *`;
    case "custom":
      return raw.trim();
  }
}

function isInt(token: string, min: number, max: number): boolean {
  if (!/^\d+$/.test(token)) return false;
  const n = Number(token);
  return n >= min && n <= max;
}

/**
 * Best-effort parse of an expression back into the friendly model so the
 * builder can pre-fill its controls when editing. Anything that doesn't match
 * one of the four presets falls back to "custom".
 */
export function parseCron(expr: string): CronModel {
  const base = { ...DEFAULT_CRON_MODEL, raw: expr.trim() };
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return { ...base, frequency: "custom" };

  const [min, hr, dom, mon, dow] = parts;
  if (mon !== "*") return { ...base, frequency: "custom" };

  // Hourly: "<min> * * * *"
  if (isInt(min, 0, 59) && hr === "*" && dom === "*" && dow === "*") {
    return { ...base, frequency: "hourly", minute: Number(min) };
  }
  // Daily: "<min> <hr> * * *"
  if (isInt(min, 0, 59) && isInt(hr, 0, 23) && dom === "*" && dow === "*") {
    return { ...base, frequency: "daily", minute: Number(min), hour: Number(hr) };
  }
  // Weekly: "<min> <hr> * * <dow>"
  if (isInt(min, 0, 59) && isInt(hr, 0, 23) && dom === "*" && isInt(dow, 0, 6)) {
    return {
      ...base,
      frequency: "weekly",
      minute: Number(min),
      hour: Number(hr),
      weekday: Number(dow),
    };
  }
  // Monthly: "<min> <hr> <dom> * *"
  if (isInt(min, 0, 59) && isInt(hr, 0, 23) && isInt(dom, 1, 31) && dow === "*") {
    return {
      ...base,
      frequency: "monthly",
      minute: Number(min),
      hour: Number(hr),
      monthday: Number(dom),
    };
  }
  return { ...base, frequency: "custom" };
}

/** A single cron field token (a number, *, range, step, or list). */
function isValidField(token: string, min: number, max: number): boolean {
  if (token === "*") return true;
  // Split comma lists and validate each member.
  return token.split(",").every((member) => {
    // Step syntax: "*/5" or "1-10/2".
    const [rangePart, stepPart] = member.split("/");
    if (stepPart !== undefined && !isInt(stepPart, 1, max)) return false;
    if (rangePart === "*") return true;
    // Range "a-b".
    if (rangePart.includes("-")) {
      const [a, b] = rangePart.split("-");
      return isInt(a, min, max) && isInt(b, min, max);
    }
    return isInt(rangePart, min, max);
  });
}

/**
 * Lightweight structural validation for early UX feedback. The backend
 * (croniter) remains the source of truth and rejects anything subtler.
 */
export function isValidCron(expr: string): boolean {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  const bounds: [number, number][] = [
    [0, 59], // minute
    [0, 23], // hour
    [1, 31], // day of month
    [1, 12], // month
    [0, 6], // day of week
  ];
  return parts.every((token, i) => isValidField(token, bounds[i][0], bounds[i][1]));
}

/** "9:05" style 24h clock label from minute/hour fields. */
function timeLabel(hour: number, minute: number): string {
  return `${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}`;
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}

/**
 * Human-readable summary of a cron expression for the schedule UI, e.g.
 * "Every day at 09:00" or "Every Monday at 14:30". Unknown shapes are
 * described generically so the user always sees something sensible.
 */
export function describeCron(expr: string): string {
  const model = parseCron(expr);
  switch (model.frequency) {
    case "hourly":
      return model.minute === 0
        ? "Every hour, on the hour"
        : `Every hour at ${model.minute} minutes past`;
    case "daily":
      return `Every day at ${timeLabel(model.hour, model.minute)}`;
    case "weekly":
      return `Every ${WEEKDAY_NAMES[model.weekday]} at ${timeLabel(model.hour, model.minute)}`;
    case "monthly":
      return `On the ${ordinal(model.monthday)} of each month at ${timeLabel(model.hour, model.minute)}`;
    case "custom":
      return isValidCron(expr) ? `Cron: ${expr.trim()}` : "Invalid cron expression";
  }
}
