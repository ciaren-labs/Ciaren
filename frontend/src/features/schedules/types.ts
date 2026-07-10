import type { ParameterValues, RunStatus } from "@/lib/types/shared";

/** A minimal run reference for the recent-run history strip on the schedules list. */
export interface ScheduleRunBrief {
  id: string;
  status: RunStatus;
  created_at: string;
}

export interface Schedule {
  id: string;
  flow_id: string;
  name: string | null;
  description: string | null;
  cron: string;
  timezone: string;
  /** null = fall back to the server's default engine when the run fires. */
  engine: string | null;
  is_enabled: boolean;
  catch_up: boolean;
  max_retries: number;
  retry_delay_seconds: number;
  /** Per-run timeout for runs this schedule fires (seconds). 0 = no limit;
   *  null = fall back to the server's RUN_TIMEOUT_SECONDS. */
  run_timeout_seconds: number | null;
  // Runtime / observability state.
  next_run_at: string | null;
  last_fired_at: string | null;
  last_run_id: string | null;
  last_status: RunStatus | null;
  consecutive_failures: number;
  retry_count: number;
  /** Set when the scheduler auto-disabled a chronically failing schedule. */
  disabled_reason: string | null;
  /** Most recent runs this schedule fired (newest first). Absent from responses
   * served by a backend older than the field, so treat as optional at runtime. */
  recent_runs?: ScheduleRunBrief[];
  /** Flow-parameter overrides applied to every run this schedule fires. */
  parameters: ParameterValues | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreate {
  cron: string;
  name?: string;
  description?: string;
  timezone?: string;
  engine?: string | null;
  is_enabled?: boolean;
  catch_up?: boolean;
  max_retries?: number;
  retry_delay_seconds?: number;
  /** Per-run timeout in seconds (0 = no limit); omit/null for the server default. */
  run_timeout_seconds?: number | null;
  parameters?: ParameterValues | null;
}

export interface ScheduleUpdate {
  cron?: string;
  name?: string;
  description?: string;
  timezone?: string;
  engine?: string | null;
  is_enabled?: boolean;
  catch_up?: boolean;
  max_retries?: number;
  retry_delay_seconds?: number;
  /** Per-run timeout in seconds (0 = no limit); omit/null for the server default. */
  run_timeout_seconds?: number | null;
  parameters?: ParameterValues | null;
}
