import { useTimezoneStore } from "@/stores/timezoneStore";
import { formatDateTime } from "./format";

/** Returns a timezone-aware formatter bound to the user's saved preference. */
export function useFormatDateTime(): (iso: string | null | undefined) => string {
  const tz = useTimezoneStore((s) => s.timezone);
  return (iso) => formatDateTime(iso, tz || undefined);
}
