export type AppSettingSource = "default" | "env" | "override";

export interface AppSetting {
  key: string;
  label: string;
  description: string;
  /** The CIAREN_* env var this setting maps to; ignored while an override exists. */
  env_var: string;
  category: string;
  value_type: "integer" | "select" | "url";
  choices: string[] | null;
  min_value: number | null;
  max_value: number | null;
  /** The value is read once at startup; a change needs a server restart. */
  restart_required: boolean;
  /** Effective value and where it comes from (override beats env beats default). */
  value: number | string;
  source: AppSettingSource;
  default_value: number | string;
  /** What "Reset" falls back to: the env var if set, else the default. */
  env_value: number | string;
}
