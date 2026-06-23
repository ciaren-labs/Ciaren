import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Cable,
  Check,
  Cloud,
  Copy,
  Database,
  FolderOpen,
  HardDrive,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Snowflake,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  siDuckdb,
  siGooglecloudstorage,
  siMongodb,
  siMysql,
  siPostgresql,
  siSnowflake,
  siSqlite,
  type SimpleIcon,
} from "simple-icons";
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
  useUpdateConnection,
} from "./hooks";

// ─── Brand icon metadata ──────────────────────────────────────────────────────

type ProviderMeta = {
  /** simple-icons SVG object. null = use lucideIcon instead. */
  brandIcon: SimpleIcon | null;
  /** Hex color (without #) for both the brand icon fill and the bg tint.
   *  Overrides brandIcon.hex when the brand color has poor contrast on white. */
  color: string;
  lucideIcon: LucideIcon;
  description: string;
};

const PROVIDER_META: Record<string, ProviderMeta> = {
  postgresql: {
    brandIcon: siPostgresql,
    color: siPostgresql.hex,
    lucideIcon: Database,
    description: "Open-source relational database",
  },
  mysql: {
    brandIcon: siMysql,
    color: siMysql.hex,
    lucideIcon: Database,
    description: "Popular open-source database",
  },
  sqlite: {
    brandIcon: siSqlite,
    color: siSqlite.hex,
    lucideIcon: HardDrive,
    description: "Lightweight file-based database",
  },
  mssql: {
    brandIcon: null,
    color: "7c3aed",
    lucideIcon: Database,
    description: "Microsoft SQL Server",
  },
  duckdb: {
    brandIcon: siDuckdb,
    // FFF000 (pure yellow) is invisible on white; use a darker amber instead.
    color: "c8a000",
    lucideIcon: HardDrive,
    description: "In-process analytics database",
  },
  snowflake: {
    brandIcon: siSnowflake,
    color: siSnowflake.hex,
    lucideIcon: Snowflake,
    description: "Cloud data warehouse",
  },
  mongodb: {
    brandIcon: siMongodb,
    color: siMongodb.hex,
    lucideIcon: Database,
    description: "Document-oriented NoSQL database",
  },
  // Amazon/Microsoft don't have public simple-icons due to trademark policy.
  // Use Lucide icons with brand-appropriate colors instead.
  s3: {
    brandIcon: null,
    color: "FF9900",
    lucideIcon: Cloud,
    description: "AWS S3 or any S3-compatible store",
  },
  azure_blob: {
    brandIcon: null,
    color: "0078D4",
    lucideIcon: Cloud,
    description: "Microsoft Azure Blob Storage",
  },
  gcs: {
    brandIcon: siGooglecloudstorage,
    // AECBFA is too light; use Google's primary blue.
    color: "4285F4",
    lucideIcon: Cloud,
    description: "Google Cloud Storage",
  },
  local: {
    brandIcon: null,
    color: "64748b",
    lucideIcon: FolderOpen,
    description: "Local folder on the server",
  },
};

function getProviderMeta(name: string): ProviderMeta {
  return (
    PROVIDER_META[name] ?? {
      brandIcon: null,
      color: "64748b",
      lucideIcon: Database,
      description: "",
    }
  );
}

/** Colored icon badge — shared between the picker cards and the connection list. */
function ProviderIconBadge({
  name,
  size = "md",
}: {
  name: string;
  size?: "sm" | "md" | "lg";
}) {
  const meta = getProviderMeta(name);
  const fill = `#${meta.color}`;
  const bg = `${fill}18`; // ~10% opacity tint
  const iconCls = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-9 w-9" : "h-5 w-5";
  const padCls = size === "sm" ? "p-1.5" : size === "lg" ? "p-3.5" : "p-2";

  return (
    <div
      className={cn("shrink-0", size === "lg" ? "rounded-2xl" : "rounded-lg", padCls)}
      style={{ backgroundColor: bg }}
    >
      {meta.brandIcon ? (
        <svg
          role="img"
          viewBox="0 0 24 24"
          className={iconCls}
          style={{ fill }}
          aria-label={meta.brandIcon.title}
        >
          <path d={meta.brandIcon.path} />
        </svg>
      ) : (
        <meta.lucideIcon className={iconCls} style={{ color: fill }} />
      )}
    </div>
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
  mkProvider("s3", "AWS S3", "storage", "boto3", "s3", null, false, false, false, true, true, true),
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
  const [editingConnection, setEditingConnection] = useState<Connection | null>(null);

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
            <ConnectionCard key={c.id} connection={c} providers={providers} onEdit={setEditingConnection} />
          ))}
        </div>
      )}

      <ConnectionDialog open={dialogOpen} onOpenChange={setDialogOpen} providers={providers} />
      <ConnectionDialog
        open={editingConnection !== null}
        onOpenChange={(o) => { if (!o) setEditingConnection(null); }}
        providers={providers}
        connection={editingConnection ?? undefined}
      />
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

function TestButton({
  onTest,
  isPending,
  result,
  error,
  size = "default",
  disabled = false,
  className,
}: {
  onTest: () => void;
  isPending: boolean;
  result?: { ok: boolean; message: string };
  error?: unknown;
  size?: "sm" | "default";
  disabled?: boolean;
  className?: string;
}) {
  const [visibleResult, setVisibleResult] = useState<{ ok: boolean; message: string } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    clearTimeout(timerRef.current);
    // Derive a displayable result from either the happy-path data or a thrown error.
    const derived: { ok: boolean; message: string } | undefined =
      result ??
      (error
        ? { ok: false, message: (error as { message?: string }).message ?? "Test failed" }
        : undefined);
    if (derived) {
      setVisibleResult(derived);
      timerRef.current = setTimeout(() => setVisibleResult(null), 5000);
    } else {
      setVisibleResult(null);
    }
    return () => clearTimeout(timerRef.current);
  }, [result, error]);

  if (isPending) {
    return (
      <Button size={size} variant="outline" disabled className={className}>
        <Loader2 className={cn("animate-spin", size === "sm" ? "h-3 w-3" : "mr-1.5 h-3.5 w-3.5")} />
        {size !== "sm" && "Testing…"}
      </Button>
    );
  }

  if (visibleResult) {
    return (
      <Button
        size={size}
        variant="outline"
        onClick={onTest}
        title={visibleResult.message}
        className={cn(
          "transition-all duration-300",
          visibleResult.ok
            ? "border-emerald-400 bg-emerald-50 text-emerald-700 hover:bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400"
            : "border-red-400 bg-red-50 text-red-700 hover:bg-red-50 dark:bg-red-950 dark:text-red-400",
          className,
        )}
      >
        {visibleResult.ok ? (
          <Check className={cn(size === "sm" ? "h-3 w-3" : "mr-1.5 h-3.5 w-3.5")} />
        ) : (
          <AlertTriangle className={cn(size === "sm" ? "h-3 w-3" : "mr-1.5 h-3.5 w-3.5")} />
        )}
        {size === "sm"
          ? visibleResult.ok ? "OK" : "Error"
          : visibleResult.ok ? "Connected!" : "Failed"}
      </Button>
    );
  }

  return (
    <Button size={size} variant="outline" onClick={onTest} disabled={disabled} className={className}>
      {size !== "sm" && <Cable className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />}
      {size === "sm" ? "Test" : "Test connection"}
    </Button>
  );
}

function ConnectionCard({
  connection,
  providers,
  onEdit,
}: {
  connection: Connection;
  providers: ProviderInfo[];
  onEdit: (c: Connection) => void;
}) {
  const test = useTestConnection();
  const del = useDeleteConnection();
  const provider = providers.find((p) => p.name === connection.provider);
  const target = connectionTarget(connection);
  const isBuiltIn = connection.provider === "local";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      <ProviderIconBadge name={connection.provider} size="sm" />
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
      <TestButton
        size="sm"
        onTest={() => test.mutate(connection.id)}
        isPending={test.isPending}
        result={test.data}
        error={test.error}
      />
      <Button size="sm" variant="ghost" onClick={() => onEdit(connection)} title="Edit connection">
        <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
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

// ─── Provider picker cards ────────────────────────────────────────────────────

function ProviderCard({
  provider,
  onSelect,
}: {
  provider: ProviderInfo;
  onSelect: () => void;
}) {
  const meta = getProviderMeta(provider.name);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-border transition-all",
        provider.available && "hover:border-primary/50 hover:shadow-sm",
      )}
    >
      <button
        type="button"
        onClick={provider.available ? onSelect : undefined}
        className={cn(
          "flex w-full flex-col items-center gap-3 px-3 pb-4 pt-5 text-center transition-colors",
          provider.available ? "cursor-pointer hover:bg-muted/40" : "cursor-not-allowed opacity-40",
        )}
      >
        <ProviderIconBadge name={provider.name} size="lg" />
        <div>
          <p className="text-sm font-semibold leading-snug">{provider.label}</p>
          <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
            {meta.description}
          </p>
        </div>
      </button>

      {/* Install hint — outside the disabled button so the copy action still works */}
      {!provider.available && provider.extra && (
        <InstallHint command={`pip install flowframe[${provider.extra}]`} />
      )}
    </div>
  );
}

function InstallHint({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="flex items-center gap-1 border-t border-border/50 bg-muted/30 px-3 py-2">
      <code className="min-w-0 flex-1 truncate font-mono text-[10px] text-muted-foreground">
        {command}
      </code>
      <button
        type="button"
        onClick={copy}
        title="Copy install command"
        className="shrink-0 rounded p-1 transition-colors hover:bg-muted"
      >
        {copied ? (
          <Check className="h-3 w-3 text-success" />
        ) : (
          <Copy className="h-3 w-3 text-muted-foreground" />
        )}
      </button>
    </div>
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
      <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
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

// ─── Add / edit connection dialog ─────────────────────────────────────────────

function connectionToForm(c: Connection): ConnectionCreate {
  return {
    name: c.name,
    provider: c.provider,
    host: c.host,
    port: c.port,
    database: c.database,
    username: c.username,
    password_env: c.password_env,
    options: c.options as Record<string, unknown> | null | undefined,
  };
}

type DialogStep = "pick" | "configure";

function ConnectionDialog({
  open,
  onOpenChange,
  providers,
  connection,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  providers: ProviderInfo[];
  connection?: Connection;
}) {
  const isEdit = !!connection;
  const create = useCreateConnection();
  const update = useUpdateConnection();
  const testConfig = useTestConnectionConfig();
  // Same query key as ConnectionsPage — TanStack deduplicates, no extra request.
  // Having refetch here lets the picker recheck driver availability after install.
  const { refetch: recheckProviders, isFetching: isRechecking } = useConnectionProviders();
  const [step, setStep] = useState<DialogStep>(isEdit ? "configure" : "pick");
  const [form, setForm] = useState<ConnectionCreate>(isEdit ? connectionToForm(connection!) : EMPTY);

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

  // Exclude local — auto-seeded from DATA_DIR, not user-created.
  const selectableProviders = providers.filter((p) => p.name !== "local");
  const dbProviders = selectableProviders.filter((p) => p.kind === "sql" || p.kind === "mongo");
  const storageProviders = selectableProviders.filter((p) => p.kind === "storage");

  const selectProvider = (p: ProviderInfo) => {
    testConfig.reset();
    setForm({
      ...EMPTY,
      name: form.name,
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
      if (isEdit) {
        await update.mutateAsync({ id: connection!.id, body: payload() });
      } else {
        await create.mutateAsync(payload());
      }
      onOpenChange(false);
    } catch {
      /* error shown in UI */
    }
  };

  // Reset when dialog closes.
  useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setStep(isEdit ? "configure" : "pick");
        setForm(isEdit ? connectionToForm(connection!) : EMPTY);
        testConfig.reset();
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const meta = getProviderMeta(form.provider);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn("transition-none", step === "pick" ? "sm:max-w-2xl" : "sm:max-w-lg")}
      >
        {step === "pick" ? (
          <>
            <DialogHeader>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <DialogTitle>Add connection</DialogTitle>
                  <DialogDescription>
                    Choose the type of database or storage you want to connect to.
                  </DialogDescription>
                </div>
                <button
                  type="button"
                  onClick={() => recheckProviders()}
                  disabled={isRechecking}
                  title="Recheck which drivers are installed"
                  className="flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
                >
                  <RefreshCw className={cn("h-3 w-3", isRechecking && "animate-spin")} />
                  Recheck
                </button>
              </div>
            </DialogHeader>

            {/* Scrollable provider grid */}
            <div className="max-h-[70vh] overflow-y-auto pr-1">
              <div className="flex flex-col gap-5 pb-1 pt-1">
                <ProviderSection
                  label="Databases"
                  providers={dbProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="Cloud Storage"
                  providers={storageProviders}
                  onSelect={selectProvider}
                />
              </div>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-start gap-2">
                {!isEdit && (
                  <button
                    type="button"
                    onClick={goBack}
                    className="mt-0.5 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    title="Choose a different connector"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                )}
                <div>
                  <DialogTitle>{isEdit ? "Edit connection" : "Configure connection"}</DialogTitle>
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
              <ProviderIconBadge name={form.provider} size="sm" />
              <div className="flex-1">
                <p className="text-xs font-semibold">{provider?.label}</p>
                <p className="text-[10px] text-muted-foreground">{meta.description}</p>
              </div>
              {!isEdit && (
                <button
                  type="button"
                  onClick={goBack}
                  className="text-[11px] font-medium text-primary hover:underline"
                >
                  Change
                </button>
              )}
            </div>

            {provider && !provider.available && provider.extra && (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1">
                  Driver not installed.{" "}
                  <code className="font-mono">pip install flowframe[{provider.extra}]</code>
                </span>
              </div>
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

              {(isEdit ? update.isError : create.isError) && (
                <p className="text-xs text-destructive">
                  {((isEdit ? update.error : create.error) as ApiError)?.message ??
                    (isEdit ? "Could not update connection." : "Could not create connection.")}
                </p>
              )}

              <div className="mt-1 flex items-center justify-end gap-2">
                <TestButton
                  className="mr-auto"
                  onTest={() => testConfig.mutate(payload())}
                  isPending={testConfig.isPending}
                  result={testConfig.data}
                  error={testConfig.error}
                  disabled={!form.provider}
                />
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={submit}
                  disabled={
                    (isEdit ? update.isPending : create.isPending) ||
                    !form.name ||
                    (isEdit && !testConfig.data?.ok)
                  }
                  title={isEdit && !testConfig.data?.ok ? "Test the connection first" : undefined}
                >
                  {(isEdit ? update.isPending : create.isPending) ? "Saving…" : "Save connection"}
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Storage-specific config fields ──────────────────────────────────────────

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
        <Field
          label="Project ID"
          hint="Optional — uses the project from the service account if omitted"
        >
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
