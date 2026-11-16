// Small presentation helpers shared across pages.

/** A compact absolute timestamp, e.g. "Jun 21, 2026, 14:32". */
export function formatDateTime(
  iso: string | null | undefined,
  timezone?: string,
): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const opts: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  };
  // Only set timeZone when explicitly provided — omitting it uses the browser's local timezone.
  if (timezone) opts.timeZone = timezone;
  return d.toLocaleString(undefined, opts);
}

/** Human-friendly elapsed time between two ISO timestamps, e.g. "1.2s". */
export function formatDuration(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  // Round total seconds first so a rounded-up 60s carries into the next minute:
  // 119,500 ms is "2m 0s", never "1m 60s".
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

/** Compact integer count, e.g. 12_500 -> "12.5k". */
export function formatCount(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}
