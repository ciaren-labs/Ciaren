import { useState } from "react";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import type { ConnectionCreate } from "@/features/connections/types";
import { Field } from "./Field";
import { SecretRefField } from "./SecretRefField";

const API_AUTH_STYLES = [
  { value: "none", label: "No authentication" },
  { value: "api_key", label: "API key header" },
  { value: "bearer", label: "Bearer token" },
  { value: "basic", label: "Basic (username + password)" },
];

/** Parse a "key: value" line-based textarea into a mapping (empty → undefined). */
function parseKeyValueLines(text: string): Record<string, string> | undefined {
  const entries = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const idx = line.indexOf(":");
      return idx === -1 ? [line, ""] : [line.slice(0, idx).trim(), line.slice(idx + 1).trim()];
    })
    .filter(([k]) => k);
  return entries.length ? Object.fromEntries(entries) : undefined;
}

function keyValueLines(value: unknown): string {
  if (!value || typeof value !== "object") return "";
  return Object.entries(value as Record<string, string>)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}

/** The core REST API connector form — modeled on commercial API connectors:
 *  base URL + auth method up front, endpoints-as-tables, and an advanced
 *  section for headers, params, parsing, and pagination. */
export function ApiFields({
  form,
  set,
  setOptionValue,
}: {
  form: ConnectionCreate;
  set: (patch: Partial<ConnectionCreate>) => void;
  setOptionValue: (key: string, value: unknown) => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const opts = (form.options ?? {}) as Record<string, unknown>;
  const authStyle = String(opts.auth_style ?? "none");
  const endpoints = Array.isArray(opts.endpoints) ? (opts.endpoints as string[]) : [];

  return (
    <>
      <Field label="Base URL" hint="Endpoint paths are resolved against this URL">
        <Input
          value={form.host ?? ""}
          onChange={(e) => set({ host: e.target.value })}
          placeholder="https://api.example.com/v1"
        />
      </Field>

      <Field label="Authentication">
        <Select value={authStyle} onChange={(e) => setOptionValue("auth_style", e.target.value)}>
          {API_AUTH_STYLES.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </Select>
      </Field>

      {authStyle === "api_key" && (
        <Field label="API key header" hint='The header the key is sent in (default "X-API-Key")'>
          <Input
            value={String(opts.api_key_header ?? "")}
            onChange={(e) => setOptionValue("api_key_header", e.target.value)}
            placeholder="X-API-Key"
          />
        </Field>
      )}
      {authStyle === "basic" && (
        <Field label="Username">
          <Input value={form.username ?? ""} onChange={(e) => set({ username: e.target.value })} />
        </Field>
      )}
      {authStyle !== "none" && (
        <SecretRefField
          label="Secret"
          hint={
            (authStyle === "basic"
              ? "The password — the value is never stored. "
              : "The token / API key — the value is never stored. ") +
            "Env var name, keyring:NAME, or file:/path"
          }
          placeholder="MY_API_TOKEN"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={form.name}
        />
      )}

      <Field
        label="Endpoints"
        hint="Comma-separated relative paths — each one appears as a table in SQL Input"
      >
        <Input
          value={endpoints.join(", ")}
          onChange={(e) =>
            setOptionValue(
              "endpoints",
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
          placeholder="users, orders, invoices"
        />
      </Field>

      <button
        type="button"
        onClick={() => setShowAdvanced((s) => !s)}
        className="self-start text-[11px] font-medium text-primary hover:underline"
      >
        {showAdvanced ? "Hide advanced options" : "Advanced options (headers, parsing, pagination)"}
      </button>

      {showAdvanced && (
        <>
          <Field label="Custom headers" hint="One per line, e.g. X-Tenant: acme">
            <textarea
              className="min-h-[64px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs shadow-sm"
              value={keyValueLines(opts.headers)}
              onChange={(e) => setOptionValue("headers", parseKeyValueLines(e.target.value))}
              placeholder={"X-Tenant: acme\nAccept-Language: en"}
            />
          </Field>
          <Field label="Default query params" hint="Appended to every request — one per line, e.g. limit: 500">
            <textarea
              className="min-h-[48px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs shadow-sm"
              value={keyValueLines(opts.query_params)}
              onChange={(e) => setOptionValue("query_params", parseKeyValueLines(e.target.value))}
              placeholder="active: true"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Response format">
              <Select
                value={String(opts.response_format ?? "auto")}
                onChange={(e) => setOptionValue("response_format", e.target.value)}
              >
                <option value="auto">Auto-detect</option>
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
              </Select>
            </Field>
            <Field label="Records path" hint='Dot path to the rows, e.g. "data.items"'>
              <Input
                value={String(opts.records_path ?? "")}
                onChange={(e) => setOptionValue("records_path", e.target.value)}
                placeholder="data.items"
              />
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Page param" hint="Enables page-number pagination">
              <Input
                value={String(opts.page_param ?? "")}
                onChange={(e) => setOptionValue("page_param", e.target.value)}
                placeholder="page"
              />
            </Field>
            <Field label="Page size param">
              <Input
                value={String(opts.page_size_param ?? "")}
                onChange={(e) => setOptionValue("page_size_param", e.target.value)}
                placeholder="per_page"
              />
            </Field>
            <Field label="Start page" hint="First page number (0 for 0-indexed APIs)">
              <Input
                type="number"
                min={0}
                value={opts.start_page == null ? "" : Number(opts.start_page)}
                onChange={(e) =>
                  setOptionValue("start_page", e.target.value ? Number(e.target.value) : undefined)
                }
                placeholder="1"
              />
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Page size">
              <Input
                type="number"
                min={1}
                value={opts.page_size == null ? "" : Number(opts.page_size)}
                onChange={(e) =>
                  setOptionValue("page_size", e.target.value ? Number(e.target.value) : undefined)
                }
                placeholder="100"
              />
            </Field>
            <Field label="Max pages">
              <Input
                type="number"
                min={1}
                value={opts.max_pages == null ? "" : Number(opts.max_pages)}
                onChange={(e) =>
                  setOptionValue("max_pages", e.target.value ? Number(e.target.value) : undefined)
                }
                placeholder="100"
              />
            </Field>
            <Field label="Timeout (s)">
              <Input
                type="number"
                min={1}
                value={opts.timeout_seconds == null ? "" : Number(opts.timeout_seconds)}
                onChange={(e) =>
                  setOptionValue("timeout_seconds", e.target.value ? Number(e.target.value) : undefined)
                }
                placeholder="30"
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={opts.verify_tls !== false}
              onChange={(e) => setOptionValue("verify_tls", e.target.checked ? undefined : false)}
            />
            Verify TLS certificates
          </label>
        </>
      )}
    </>
  );
}
