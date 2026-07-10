import type { ConfigSchema } from "@/lib/types/shared";

export interface Connection {
  id: string;
  name: string;
  provider: string;
  /** Derived from provider: "sql" | "mongo" | "storage" */
  connection_type: string;
  host: string | null;
  port: number | null;
  database: string | null;
  username: string | null;
  /** NAME of an env var holding the password — never the secret itself. */
  password_env: string | null;
  options: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  /** When the connection was last tested (any test, pass or fail). */
  last_tested_at: string | null;
  /** Outcome of the last test, or null if never tested. Editing a connectivity
   *  field (host/port/database/credentials/options) clears it server-side. */
  last_test_status: "ok" | "failed" | "error" | null;
  /** Failure detail from the last test (secrets redacted), or null. */
  last_test_error: string | null;
}

export interface ConnectionCreate {
  name: string;
  provider: string;
  host?: string | null;
  port?: number | null;
  database?: string | null;
  username?: string | null;
  password_env?: string | null;
  options?: Record<string, unknown> | null;
}

export type ConnectionUpdate = Partial<ConnectionCreate>;

export interface ProviderInfo {
  name: string;
  label: string;
  /** Core kinds are closed; a plugin connector may declare its own (e.g. "api"). */
  kind: "sql" | "mongo" | "storage" | "mlflow" | (string & {});
  available: boolean;
  driver_module: string | null;
  extra: string | null;
  default_port: number | null;
  needs_host: boolean;
  needs_auth: boolean;
  supports_query: boolean;
  needs_bucket: boolean;
  needs_region: boolean;
  needs_endpoint: boolean;
  /** Present (true) only for plugin-contributed connectors. */
  plugin?: boolean;
  plugin_id?: string;
  /** Extra connector-specific form fields, stored in the connection's options. */
  config_schema?: ConfigSchema;
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
}

export interface TableInfo {
  name: string;
  schema_name: string | null;
  qualified: string;
}

/** Whether this host has a usable OS keychain (headless servers don't). */
export interface KeyringAvailability {
  available: boolean;
  backend: string | null;
  detail: string | null;
}

/** A keychain entry's presence and its `keyring:NAME` reference — never its value. */
export interface KeyringSecretStatus {
  name: string;
  exists: boolean;
  reference: string;
}

export interface KeyringSecretWrite {
  name: string;
  value: string;
  overwrite?: boolean;
}
