import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Cloud,
  Copy,
  Database,
  FolderOpen,
  HardDrive,
  Loader2,
  Plus,
  Snowflake,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
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

// ─── Provider metadata ────────────────────────────────────────────────────────

type ProviderMeta = {
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  description: string;
};

const PROVIDER_META: Record<string, ProviderMeta> = {
  postgresql: {
    icon: Database,
    iconBg: "bg-blue-100",
    iconColor: "text-blue-600",
    description: "Open-source relational database",
  },
  mysql: {
    icon: Database,
    iconBg: "bg-orange-100",
    iconColor: "text-orange-600",
    description: "Popular open-source database",
  },
  sqlite: {
    icon: HardDrive,
    iconBg: "bg-slate-100",
    iconColor: "text-slate-500",
    description: "Lightweight file-based database",
  },
  mssql: {
    icon: Database,
    iconBg: "bg-violet-100",
    iconColor: "text-violet-600",
    description: "Microsoft SQL Server",
  },
  duckdb: {
    icon: HardDrive,
    iconBg: "bg-yellow-100",
    iconColor: "text-yellow-700",
    description: "In-process analytics database",
  },
  snowflake: {
    icon: Snowflake,
    iconBg: "bg-sky-100",
    iconColor: "text-sky-600",
    description: "Cloud data warehouse",
  },
  mongodb: {
    icon: Database,
    iconBg: "bg-green-100",
    iconColor: "text-green-600",
    description: "Document-oriented NoSQL database",
  },
  s3: {
    icon: Cloud,
    iconBg: "bg-amber-100",
    iconColor: "text-amber-600",
    description: "AWS S3 or any S3-compatible store",
  },
  azure_blob: {
    icon: Cloud,
    iconBg: "bg-blue-100",
    iconColor: "text-blue-600",
    description: "Microsoft Azure Blob Storage",
  },
  gcs: {
    icon: Cloud,
    iconBg: "bg-red-100",
    iconColor: "text-red-500",
    description: "Google Cloud Storage",
  },
  local: {
    icon: FolderOpen,
    iconBg: "bg-slate-100",
    iconColor: "text-slate-500",
    description: "Local folder on the server",
  },
};

function getProviderMeta(name: string): ProviderMeta {
  return (
    PROVIDER_META[name] ?? {
      icon: Database,
      iconBg: "bg-slate-100",
      iconColor: "text-slate-500",
      description: "",
    }
  );
}

// ─── Constants ────────────────────────────────────────────────────────────────

const EMPTY: ConnectionCreate = {
  name: "",
  provider: "postgresql",
  host: "",
  port: null,
  database: "",
  username: "",
  password_env: "",
  options: null,
};

const FALLBACK_PROVIDERS: ProviderInfo[] = [
  mkProvider("postgresql", "PostgreSQL", "sql", "psycopg", "postgres", 5432, true, true, true),
  mkProvider("mysql", "MySQL / MariaDB", "sql", "pymysql", "mysql", 3306, true, true, true),
  mkProvider("sqlite", "SQLite", "sql", null, null, null, false, false, true),
  mkProvider("mssql", "SQL Server", "sql", "pyodbc", "mssql", 1433, true, true, true),
  mkProvider("duckdb", "DuckDB", "sql", "duckdb", "duckdb", null, false, false, true),
  mkProvider("snowflake", "Snowflake", "sql", "snowflake-connector-python", "snowflake", null, true, true, true),
  mkProvider("mongodb", "MongoDB", "mongo", "pymongo", "mongo", 27017, true, true, false),
  mkProvider("s3", "S3 / S3-Compatible", "storage", "boto3", "aws", null, false, false, false, true, true, true),
  mkProvider("azure_blob", "Azure Blob Storage", "storage", "azure-storage-blob", "azure", null, false, true, false, true, false, false),
  mkProvider("gcs", "Google Cloud Storage", "storage", "google-cloud-storage", "gcs", null, false, false, false, true, false, false),
];

function mkProvider(
  name: string,
  label: string,
  kind: "sql" | "mongo" | "storage",
  driver_module: string | null,
  extra: string | null,
  default_port: number | null,
  needs_host: boolean,
  needs_auth: boolean,
  supports_query: boolean,
  needs_bucket = false,
  needs_region = false,
  needs_endpoint = false,
): ProviderInfo {
  return {
    name,
    label,
    kind,
    available: true,
    driver_module,
    extra,
    default_port,
    needs_host,
    needs_auth,
    supports_query,
    needs_bucket,
    needs_region,
    needs_endpoint,
  };
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ConnectionsPage() {
  const { data: connections = [], isLoading } = useConnections();
  const { data: fetchedProviders = [] } = useConnectionProviders();
  const providers = fetchedProviders.length ? fetchedProviders : FALLBACK_PROVIDERS;
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Connections</h1>
          <p className="text-sm text-muted-foreground">
            Reusable connections for database and cloud storage nodes. Passwords and
            secret keys are read from environment variables — never stored.
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
            No connections yet. Add one to read from or write to a database or cloud storage.
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

// ─── Connection list card ─────────────────────────────────────────────────────

function connectionTarget(connection: Connection): string {
  if (connection.connection_type === "storage") {
    return connection.database ? `bucket: ${connection.database}` : connection.provider;
  }
  if (connection.provider === "sqlite" || connection.provider === "duckdb") {
    return connection.database ?? connection.provider;
  }
  return `${connection.host ?? ""}${connection.port ? `:${connection.port}` : ""}/${connection.database ?? ""}`;
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
  const meta = getProviderMeta(connection.provider);
  const Icon = meta.icon;
  const target = connectionTarget(connection);
  const isBuiltIn = connection.provider === "local";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      <div className={cn("rounded-lg p-1.5", meta.iconBg)}>
        <Icon className={cn("h-4 w-4", meta.iconColor)} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{connection.name}</span>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
            {provider?.label ?? connection.provider}
          </span>
          {isBuiltIn && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
              built-in
            </span>
          )}
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
      {!isBuiltIn && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            if (confirm(`Delete connection "${connection.name}"?`)) del.mutate(connection.id);
          }}
        >
          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      )}
    </div>
  );
}

// ─── Provider picker card ─────────────────────────────────────────────────────

function ProviderCard({
  provider,
  onSelect,
}: {
  provider: ProviderInfo;
  onSelect: () => void;
}) {
  const meta = getProviderMeta(provider.name);
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={!provider.available}
      className={cn(
        "group relative flex flex-col gap-2.5 rounded-xl border border-border p-3.5 text-left transition-all",
        provider.available
          ? "cursor-pointer hover:border-primary/60 hover:bg-muted/40 hover:shadow-sm"
          : "cursor-not-allowed opacity-40",
      )}
    >
      <div className={cn("w-fit rounded-lg p-2", meta.iconBg)}>
        <Icon className={cn("h-5 w-5", meta.iconColor)} />
      </div>
      <div>
        <p className="text-xs font-semibold leading-snug">{provider.label}</p>
        <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">{meta.description}</p>
      </div>
      {!provider.available && (
        <span className="absolute right-2 top-2 rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-700">
          driver missing
        </span>
      )}
    </button>
  );
}

function ProviderSection({
  label,
  providers,
  onSelect,
}: {
  label: string;
  providers: ProviderInfo[];
  onSelect: (p: ProviderInfo) => void;
}) {
  if (providers.length === 0) return null;
  return (
    <div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <div className="grid grid-cols-3 gap-2">
        {providers.map((p) => (
          <ProviderCard key={p.name} provider={p} onSelect={() => onSelect(p)} />
        ))}
      </div>
    </div>
  );
}

// ─── Add-connection dialog ────────────────────────────────────────────────────

type DialogStep = "pick" | "configure";

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
  const [step, setStep] = useState<DialogStep>("pick");
  const [form, setForm] = useState<ConnectionCreate>(EMPTY);

  const set = (patch: Partial<ConnectionCreate>) => {
    testConfig.reset();
    setForm((f) => ({ ...f, ...patch }));
  };

  const setOption = (key: string, value: string) =>
    set({ options: { ...(form.options ?? {}), [key]: value || undefined } });

  const provider = useMemo(
    () => providers.find((p) => p.name === form.provider),
    [providers, form.provider],
  );
  const isStorage = provider?.kind === "storage";
  const isSqlite = form.provider === "sqlite" || form.provider === "duckdb";

  // Exclude local — it's auto-seeded from DATA_DIR, not user-created.
  const selectableProviders = providers.filter((p) => p.name !== "local");
  const dbProviders = selectableProviders.filter((p) => p.kind === "sql" || p.kind === "mongo");
  const storageProviders = selectableProviders.filter((p) => p.kind === "storage");

  const selectProvider = (p: ProviderInfo) => {
    testConfig.reset();
    setForm({
      ...EMPTY,
      name: form.name, // preserve any name the user typed
      provider: p.name,
      port: p.default_port ?? null,
    });
    setStep("configure");
  };

  const goBack = () => {
    testConfig.reset();
    setStep("pick");
  };

  const payload = (): ConnectionCreate => ({ ...form, port: form.port ? Number(form.port) : null });

  const submit = async () => {
    try {
      await create.mutateAsync(payload());
      onOpenChange(false);
    } catch {
      /* error shown below */
    }
  };

  // Reset fully when dialog closes.
  useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setStep("pick");
        setForm(EMPTY);
        testConfig.reset();
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const meta = getProviderMeta(form.provider);
  const ProviderIcon = meta.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("transition-none", step === "pick" ? "sm:max-w-2xl" : "sm:max-w-lg")}>
        {step === "pick" ? (
          <>
            <DialogHeader>
              <DialogTitle>Add connection</DialogTitle>
              <DialogDescription>
                Choose the type of database or storage you want to connect to.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-5 pt-1">
              <ProviderSection label="Databases" providers={dbProviders} onSelect={selectProvider} />
              <ProviderSection label="Cloud Storage" providers={storageProviders} onSelect={selectProvider} />
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={goBack}
                  className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  title="Choose a different connector"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <div>
                  <DialogTitle>Configure connection</DialogTitle>
                  <DialogDescription>
                    {isStorage
                      ? "Secret keys are read at runtime from env vars and never stored."
                      : "Passwords are read at runtime from env vars and never stored."}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            {/* Selected provider chip */}
            <div className="flex items-center gap-2.5 rounded-lg border border-border bg-muted/30 px-3 py-2">
              <div className={cn("rounded-md p-1.5", meta.iconBg)}>
                <ProviderIcon className={cn("h-4 w-4", meta.iconColor)} />
              </div>
              <div className="flex-1">
                <p className="text-xs font-semibold">{provider?.label}</p>
                <p className="text-[10px] text-muted-foreground">{meta.description}</p>
              </div>
              <button
                type="button"
                onClick={goBack}
                className="text-[11px] font-medium text-primary hover:underline"
              >
                Change
              </button>
            </div>

            {provider && !provider.available && provider.extra && (
              <DriverHint
                label={provider.label}
                command={`pip install flowframe[${provider.extra}]`}
              />
            )}

            <div className="flex flex-col gap-3">
              <Field label="Connection name">
                <Input
                  value={form.name}
                  onChange={(e) => set({ name: e.target.value })}
                  placeholder={isStorage ? "my-s3-bucket" : "warehouse"}
                  autoFocus
                />
              </Field>

              {isStorage ? (
                <StorageFields form={form} provider={provider!} set={set} setOption={setOption} />
              ) : isSqlite ? (
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
                      <Input
                        value={form.host ?? ""}
                        onChange={(e) => set({ host: e.target.value })}
                        placeholder="localhost"
                      />
                    </Field>
                    <Field label="Port">
                      <Input
                        type="number"
                        value={form.port ?? ""}
                        onChange={(e) =>
                          set({ port: e.target.value ? Number(e.target.value) : null })
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Database">
                    <Input
                      value={form.database ?? ""}
                      onChange={(e) => set({ database: e.target.value })}
                    />
                  </Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Username">
                      <Input
                        value={form.username ?? ""}
                        onChange={(e) => set({ username: e.target.value })}
                      />
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
                  className={cn(
                    "flex items-center gap-1.5 text-xs",
                    testConfig.data.ok ? "text-success" : "text-destructive",
                  )}
                >
                  {testConfig.data.ok ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <X className="h-3.5 w-3.5" />
                  )}
                  {testConfig.data.message}
                </p>
              )}
              {create.isError && (
                <p className="text-xs text-destructive">
                  {(create.error as ApiError)?.message ?? "Could not create connection."}
                </p>
              )}

              <div className="mt-1 flex items-center justify-end gap-2">
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
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Storage-specific fields ──────────────────────────────────────────────────

function StorageFields({
  form,
  provider,
  set,
  setOption,
}: {
  form: ConnectionCreate;
  provider: ProviderInfo;
  set: (patch: Partial<ConnectionCreate>) => void;
  setOption: (key: string, value: string) => void;
}) {
  const opts = (form.options ?? {}) as Record<string, string>;

  if (provider.name === "s3") {
    return (
      <>
        <Field label="Bucket" hint="e.g. my-data-bucket">
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
            placeholder="my-data-bucket"
          />
        </Field>
        <Field
          label="Access Key ID"
          hint="Leave empty to use an IAM role or AWS_ACCESS_KEY_ID env var"
        >
          <Input
            value={form.username ?? ""}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="AKIAIOSFODNN7EXAMPLE"
          />
        </Field>
        <Field
          label="Secret Access Key env var"
          hint="Name of the env var holding the secret key (optional if using IAM)"
        >
          <Input
            value={form.password_env ?? ""}
            onChange={(e) => set({ password_env: e.target.value })}
            placeholder="AWS_SECRET_ACCESS_KEY"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Region" hint="e.g. us-east-1 (optional)">
            <Input
              value={opts.region ?? ""}
              onChange={(e) => setOption("region", e.target.value)}
              placeholder="us-east-1"
            />
          </Field>
          <Field label="Endpoint URL" hint="For MinIO, R2, etc. (optional)">
            <Input
              value={form.host ?? ""}
              onChange={(e) => set({ host: e.target.value })}
              placeholder="http://localhost:9000"
            />
          </Field>
        </div>
      </>
    );
  }

  if (provider.name === "azure_blob") {
    return (
      <>
        <Field label="Container">
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
            placeholder="my-container"
          />
        </Field>
        <Field label="Storage account name">
          <Input
            value={form.username ?? ""}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="mystorageaccount"
          />
        </Field>
        <Field label="Account key env var" hint="Name of the env var holding the account key">
          <Input
            value={form.password_env ?? ""}
            onChange={(e) => set({ password_env: e.target.value })}
            placeholder="AZURE_STORAGE_ACCOUNT_KEY"
          />
        </Field>
      </>
    );
  }

  if (provider.name === "gcs") {
    return (
      <>
        <Field label="Bucket">
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
            placeholder="my-gcs-bucket"
          />
        </Field>
        <Field label="Project ID" hint="Optional — uses the project from the service account if omitted">
          <Input
            value={opts.project_id ?? ""}
            onChange={(e) => setOption("project_id", e.target.value)}
            placeholder="my-gcp-project"
          />
        </Field>
        <Field
          label="Service account key env var"
          hint="Env var holding the path to a service account JSON file. Leave empty for Application Default Credentials."
        >
          <Input
            value={form.password_env ?? ""}
            onChange={(e) => set({ password_env: e.target.value })}
            placeholder="GOOGLE_APPLICATION_CREDENTIALS"
          />
        </Field>
      </>
    );
  }

  return null;
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function DriverHint({ label, command }: { label: string; command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-700">
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
