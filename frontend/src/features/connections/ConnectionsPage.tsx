import { useMemo, useState } from "react";
import { AlertTriangle, Check, Copy, Database, Loader2, Plus, Trash2, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import type { Connection, ConnectionCreate, ProviderInfo } from "@/lib/types";
import {
  useConnectionProviders,
  useConnections,
  useCreateConnection,
  useDeleteConnection,
  useTestConnection,
  useTestConnectionConfig,
} from "./hooks";

const EMPTY: ConnectionCreate = {
  name: "",
  provider: "postgresql",
  host: "",
  port: null,
  database: "",
  username: "",
  password_env: "",
};

// Used when the /providers endpoint can't be reached (e.g. the backend hasn't
// been restarted with the connectors build) so the dropdown is never empty.
// Real driver-availability is overlaid once the endpoint responds.
const FALLBACK_PROVIDERS: ProviderInfo[] = [
  mkProvider("postgresql", "PostgreSQL", "sql", "psycopg", "postgres", 5432, true, true, true),
  mkProvider("mysql", "MySQL / MariaDB", "sql", "pymysql", "mysql", 3306, true, true, true),
  mkProvider("sqlite", "SQLite", "sql", null, null, null, false, false, true),
  mkProvider("mssql", "SQL Server", "sql", "pyodbc", "mssql", 1433, true, true, true),
  mkProvider("mongodb", "MongoDB", "mongo", "pymongo", "mongo", 27017, true, true, false),
];

function mkProvider(
  name: string,
  label: string,
  kind: "sql" | "mongo",
  driver_module: string | null,
  extra: string | null,
  default_port: number | null,
  needs_host: boolean,
  needs_auth: boolean,
  supports_query: boolean,
): ProviderInfo {
  return {
    name,
    label,
    kind,
    available: true, // optimistic until the server reports real availability
    driver_module,
    extra,
    default_port,
    needs_host,
    needs_auth,
    supports_query,
  };
}

export function ConnectionsPage() {
  const { data: connections = [], isLoading } = useConnections();
  const { data: fetchedProviders = [] } = useConnectionProviders();
  // Fall back to the built-in list if the endpoint isn't reachable yet.
  const providers = fetchedProviders.length ? fetchedProviders : FALLBACK_PROVIDERS;
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Connections</h1>
          <p className="text-sm text-muted-foreground">
            Reusable database connections for SQL source &amp; sink nodes. Passwords
            are read from environment variables — never stored.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" /> Add connection
        </Button>
      </div>

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      ) : connections.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-10 text-center">
          <Database className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No connections yet. Add one to read from or write to a database.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {connections.map((c) => (
            <ConnectionCard key={c.id} connection={c} providers={providers} />
          ))}
        </div>
      )}

      <ConnectionDialog open={dialogOpen} onOpenChange={setDialogOpen} providers={providers} />
    </div>
  );
}

function ConnectionCard({
  connection,
  providers,
}: {
  connection: Connection;
  providers: ProviderInfo[];
}) {
  const test = useTestConnection();
  const del = useDeleteConnection();
  const provider = providers.find((p) => p.name === connection.provider);
  const target =
    connection.provider === "sqlite"
      ? connection.database
      : `${connection.host ?? ""}${connection.port ? `:${connection.port}` : ""}/${connection.database ?? ""}`;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      <Database className="h-5 w-5 text-brand-600" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{connection.name}</span>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
            {provider?.label ?? connection.provider}
          </span>
        </div>
        <p className="truncate text-xs text-muted-foreground">{target}</p>
      </div>
      {test.data && (
        <span
          className={`flex items-center gap-1 text-xs ${test.data.ok ? "text-success" : "text-destructive"}`}
          title={test.data.message}
        >
          {test.data.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
          {test.data.ok ? "OK" : "Failed"}
        </span>
      )}
      <Button
        size="sm"
        variant="outline"
        onClick={() => test.mutate(connection.id)}
        disabled={test.isPending}
      >
        {test.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Test"}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => {
          if (confirm(`Delete connection "${connection.name}"?`)) del.mutate(connection.id);
        }}
      >
        <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
      </Button>
    </div>
  );
}

function ConnectionDialog({
  open,
  onOpenChange,
  providers,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  providers: ProviderInfo[];
}) {
  const create = useCreateConnection();
  const testConfig = useTestConnectionConfig();
  const [form, setForm] = useState<ConnectionCreate>(EMPTY);
  const set = (patch: Partial<ConnectionCreate>) => {
    testConfig.reset(); // a config change invalidates the last test result
    setForm((f) => ({ ...f, ...patch }));
  };

  const payload = (): ConnectionCreate => ({ ...form, port: form.port ? Number(form.port) : null });

  const provider = useMemo(
    () => providers.find((p) => p.name === form.provider),
    [providers, form.provider],
  );
  const isSqlite = form.provider === "sqlite";

  const submit = async () => {
    try {
      await create.mutateAsync(payload());
      setForm(EMPTY);
      testConfig.reset();
      onOpenChange(false);
    } catch {
      /* error shown below */
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add connection</DialogTitle>
          <DialogDescription>
            The password is read at runtime from the named environment variable and is
            never stored by FlowFrame.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <Field label="Name">
            <Input value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="warehouse" />
          </Field>

          <Field label="Provider">
            <Select
              value={form.provider}
              onChange={(e) => {
                const p = providers.find((x) => x.name === e.target.value);
                set({ provider: e.target.value, port: p?.default_port ?? null });
              }}
            >
              {providers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.label}
                  {p.available ? "" : " — driver not installed"}
                </option>
              ))}
            </Select>
            {provider && !provider.available && (
              <DriverHint
                label={provider.label}
                command={`pip install flowframe[${provider.extra}]`}
              />
            )}
          </Field>

          {isSqlite ? (
            <Field label="Database file path">
              <Input
                value={form.database ?? ""}
                onChange={(e) => set({ database: e.target.value })}
                placeholder="/data/warehouse.db"
              />
            </Field>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Host">
                  <Input value={form.host ?? ""} onChange={(e) => set({ host: e.target.value })} placeholder="localhost" />
                </Field>
                <Field label="Port">
                  <Input
                    type="number"
                    value={form.port ?? ""}
                    onChange={(e) => set({ port: e.target.value ? Number(e.target.value) : null })}
                  />
                </Field>
              </div>
              <Field label="Database">
                <Input value={form.database ?? ""} onChange={(e) => set({ database: e.target.value })} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Username">
                  <Input value={form.username ?? ""} onChange={(e) => set({ username: e.target.value })} />
                </Field>
                <Field label="Password env var" hint="e.g. PG_PASSWORD">
                  <Input
                    value={form.password_env ?? ""}
                    onChange={(e) => set({ password_env: e.target.value })}
                    placeholder="PG_PASSWORD"
                  />
                </Field>
              </div>
            </>
          )}

          {testConfig.data && (
            <p
              className={`flex items-center gap-1.5 text-xs ${testConfig.data.ok ? "text-success" : "text-destructive"}`}
            >
              {testConfig.data.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
              {testConfig.data.message}
            </p>
          )}
          {create.isError && (
            <p className="text-xs text-destructive">
              {(create.error as ApiError)?.message ?? "Could not create connection."}
            </p>
          )}

          <div className="mt-2 flex items-center justify-end gap-2">
            <Button
              variant="outline"
              className="mr-auto"
              onClick={() => testConfig.mutate(payload())}
              disabled={testConfig.isPending || !form.provider}
            >
              {testConfig.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Test connection
            </Button>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={create.isPending || !form.name}>
              {create.isPending ? "Saving…" : "Save connection"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DriverHint({ label, command }: { label: string; command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="mt-1 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-700">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span className="shrink-0">The {label} driver isn't installed:</span>
      <code className="min-w-0 flex-1 truncate font-mono text-amber-900" title={command}>
        {command}
      </code>
      <button
        type="button"
        onClick={copy}
        title="Copy install command"
        className="shrink-0 rounded p-1 text-amber-700 transition-colors hover:bg-amber-100"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
