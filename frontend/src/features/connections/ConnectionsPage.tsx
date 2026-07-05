import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Cable,
  Check,
  Cloud,
  Copy,
  Database,
  FlaskConical,
  FolderOpen,
  Globe,
  HardDrive,
  KeyRound,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Snowflake,
  Trash2,
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
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/PageState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { ApiError } from "@/lib/api";
import { SchemaConfigFields } from "@/components/flow/SchemaConfigFields";
import type { Connection, ConnectionCreate, ProviderInfo } from "@/lib/types";
import {
  useConnectionProviders,
  useConnections,
  useCreateConnection,
  useDeleteConnection,
  useKeyringAvailability,
  useStoreKeyringSecret,
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
  rest_api: {
    brandIcon: null,
    color: "0EA5E9",
    lucideIcon: Globe,
    description: "Any REST / HTTP API returning JSON or CSV",
  },
  mlflow: {
    brandIcon: null,
    color: "0194E2",
    lucideIcon: FlaskConical,
    description: "MLflow experiment & model tracking",
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
  mkProvider("local", "Local Folder", "storage", null, null, null, false, false, false, true, false, false),
  mkProvider("s3", "AWS S3", "storage", "boto3", "s3", null, false, false, false, true, true, true),
  mkProvider("azure_blob", "Azure Blob Storage", "storage", "azure-storage-blob", "azure", null, false, true, false, true, false, false),
  mkProvider("gcs", "Google Cloud Storage", "storage", "google-cloud-storage", "gcs", null, false, false, false, true, false, false),
  mkProvider("mlflow", "MLflow Tracking", "mlflow", "mlflow", "ml", null, false, false, false),
];

function mkProvider(
  name: string,
  label: string,
  kind: "sql" | "mongo" | "storage" | "mlflow",
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
  const { data: connections = [], isPending, isError, error, refetch } = useConnections();
  const { data: fetchedProviders = [] } = useConnectionProviders();
  const providers = fetchedProviders.length ? fetchedProviders : FALLBACK_PROVIDERS;
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingConnection, setEditingConnection] = useState<Connection | null>(null);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
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

      {isPending ? (
        <LoadingState label="Loading connections…" />
      ) : isError ? (
        <ErrorState error={error} title="Couldn't load connections" onRetry={() => refetch()} />
      ) : connections.length === 0 ? (
        <EmptyState
          icon={Database}
          title="Connect a database or cloud storage"
          description="Connections let SQL and storage nodes read from and write to your databases. Passwords stay in environment variables — never stored here."
          action={
            <Button onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4" /> Add connection
            </Button>
          }
        />
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
  if (connection.connection_type === "mlflow") {
    return connection.database ?? "mlflow";
  }
  if (connection.connection_type === "storage") {
    return connection.database ? `bucket: ${connection.database}` : connection.provider;
  }
  if (connection.provider === "sqlite" || connection.provider === "duckdb") {
    return connection.database ?? connection.provider;
  }
  if (connection.connection_type === "api") {
    return connection.host ?? connection.provider;
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
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

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
    const button = (
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
          !visibleResult.ok && className,
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
    // Failure isn't just a red button — surface the real backend error message
    // as visible, accessible text (same convention as the create/update form
    // errors below), not just a hover-only title attribute.
    if (!visibleResult.ok) {
      return (
        <div className={cn("flex flex-col items-start gap-1", className)}>
          {button}
          <p role="alert" className="max-w-xs text-xs text-destructive">
            {visibleResult.message}
          </p>
        </div>
      );
    }
    return button;
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
  const fmtDate = useFormatDateTime();
  const provider = providers.find((p) => p.name === connection.provider);
  const target = connectionTarget(connection);
  // Only the auto-seeded defaults are built-in; user-created connections are deletable.
  const isBuiltIn =
    (connection.provider === "local" && connection.name === "Local Storage") ||
    (connection.provider === "mlflow" && connection.name === "Local MLflow");

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
        <div className="mt-0.5 flex flex-col gap-0.5 text-[11px] text-muted-foreground/80">
          <span>Added {fmtDate(connection.created_at)}</span>
          <span>
            {connection.last_tested_at
              ? `Tested ${fmtDate(connection.last_tested_at)}`
              : "Never tested"}
          </span>
        </div>
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
            if (!confirm(`Delete connection "${connection.name}"?`)) return;
            del.mutate(
              { id: connection.id },
              {
                onError: (err) => {
                  // Still referenced by flows → surface which ones and offer a
                  // force delete (those flows fail at run time until repointed).
                  if (
                    err instanceof ApiError &&
                    err.status === 409 &&
                    confirm(`${err.message}\n\nDelete it anyway?`)
                  ) {
                    del.mutate({ id: connection.id, force: true });
                  }
                },
              },
            );
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
            {meta.description || (provider.plugin ? `Contributed by ${provider.plugin_id}` : "")}
          </p>
          {provider.plugin && (
            <span className="mt-1.5 inline-block rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-primary">
              Plugin
            </span>
          )}
        </div>
      </button>

      {/* Install hint — outside the disabled button so the copy action still works */}
      {!provider.available && provider.extra && (
        <InstallHint command={`pip install ciaren[${provider.extra}]`} />
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
      <div className="grid grid-cols-4 gap-2">
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

  // Schema-driven plugin fields can hold any JSON value (booleans, numbers, lists).
  const setOptionValue = (key: string, value: unknown) =>
    set({ options: { ...(form.options ?? {}), [key]: value === "" ? undefined : value } });

  const provider = useMemo(
    () => providers.find((p) => p.name === form.provider),
    [providers, form.provider],
  );
  const isStorage = provider?.kind === "storage";
  const isMlflow = provider?.kind === "mlflow";
  const isApi = provider?.kind === "api" && !provider?.plugin;
  const isSqlite = form.provider === "sqlite" || form.provider === "duckdb";

  const selectableProviders = providers;
  const dbProviders = selectableProviders.filter((p) => !p.plugin && (p.kind === "sql" || p.kind === "mongo"));
  const apiProviders = selectableProviders.filter((p) => !p.plugin && p.kind === "api");
  const storageProviders = selectableProviders.filter((p) => !p.plugin && p.kind === "storage");
  const trackingProviders = selectableProviders.filter((p) => !p.plugin && p.kind === "mlflow");
  const pluginProviders = selectableProviders.filter((p) => p.plugin);

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

  // Sync state whenever the dialog opens (or the connection being edited changes).
  // On close: do a delayed reset to defaults so the animation finishes cleanly;
  // the cleanup cancels it if the dialog reopens before the timeout fires.
  useEffect(() => {
    if (open) {
      setStep(isEdit ? "configure" : "pick");
      setForm(isEdit ? connectionToForm(connection!) : EMPTY);
      testConfig.reset();
    } else {
      const t = setTimeout(() => {
        setStep("pick");
        setForm(EMPTY);
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open, connection]); // eslint-disable-line react-hooks/exhaustive-deps

  const meta = getProviderMeta(form.provider);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn("transition-none", step === "pick" ? "sm:max-w-3xl" : "sm:max-w-lg")}
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
                  label="APIs"
                  providers={apiProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="Storage"
                  providers={storageProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="Experiment tracking"
                  providers={trackingProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="From plugins"
                  providers={pluginProviders}
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
                    {isMlflow
                      ? "Where Ciaren logs experiments and models. Used by all ML flows."
                      : isStorage
                        ? "Secret keys are read at runtime (env var, OS keychain, or secret file) and never stored."
                        : "Passwords are read at runtime (env var, OS keychain, or secret file) and never stored."}
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
                  <code className="font-mono">pip install ciaren[{provider.extra}]</code>
                </span>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <Field label="Connection name">
                <Input
                  value={form.name}
                  onChange={(e) => set({ name: e.target.value })}
                  placeholder={isStorage ? "my-s3-bucket" : isMlflow ? "Local MLflow" : "warehouse"}
                  autoFocus
                />
              </Field>

              {provider?.plugin ? (
                <PluginProviderFields
                  form={form}
                  provider={provider}
                  set={set}
                  setOptionValue={setOptionValue}
                />
              ) : isApi ? (
                <ApiFields form={form} set={set} setOptionValue={setOptionValue} />
              ) : isMlflow ? (
                <Field
                  label="Tracking URI"
                  hint="A local folder (./mlruns), sqlite:///path/mlflow.db, or a tracking server (http://host:5000)."
                >
                  <Input
                    value={form.database ?? ""}
                    onChange={(e) => set({ database: e.target.value })}
                    placeholder="./mlruns"
                  />
                </Field>
              ) : isStorage ? (
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
                  <Field label="Username">
                    <Input
                      value={form.username ?? ""}
                      onChange={(e) => set({ username: e.target.value })}
                    />
                  </Field>
                  <SecretRefField
                    label="Password secret"
                    hint="Env var name, keyring:NAME (OS keychain), or file:/path"
                    placeholder="PG_PASSWORD"
                    value={form.password_env ?? ""}
                    onChange={(v) => set({ password_env: v })}
                    suggestedName={form.name}
                  />
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
                    !testConfig.data?.ok
                  }
                  title={!testConfig.data?.ok ? "Test the connection first" : undefined}
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

// ─── REST API connector fields ────────────────────────────────────────────────

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
function ApiFields({
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
          <div className="grid grid-cols-2 gap-3">
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

// ─── Plugin connector config fields ───────────────────────────────────────────

/** Form for a plugin-contributed connector: the standard fields its provider
 *  flags ask for (host/port, database or bucket, username + password env var)
 *  plus the connector's own `config_schema` fields, which are stored in the
 *  connection's `options`. */
function PluginProviderFields({
  form,
  provider,
  set,
  setOptionValue,
}: {
  form: ConnectionCreate;
  provider: ProviderInfo;
  set: (patch: Partial<ConnectionCreate>) => void;
  setOptionValue: (key: string, value: unknown) => void;
}) {
  const schemaFields = provider.config_schema?.fields ?? [];
  const isStorageKind = provider.kind === "storage";
  return (
    <>
      {provider.needs_host && (
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
              onChange={(e) => set({ port: e.target.value ? Number(e.target.value) : null })}
            />
          </Field>
        </div>
      )}
      {(provider.needs_bucket || isStorageKind) && (
        <Field label={isStorageKind ? "Bucket / folder" : "Bucket"}>
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
          />
        </Field>
      )}
      {(provider.kind === "sql" || provider.kind === "mongo") && (
        <Field label="Database">
          <Input value={form.database ?? ""} onChange={(e) => set({ database: e.target.value })} />
        </Field>
      )}
      {provider.needs_auth && (
        <>
          <Field label="Username">
            <Input
              value={form.username ?? ""}
              onChange={(e) => set({ username: e.target.value })}
            />
          </Field>
          <SecretRefField
            label="Password secret"
            hint="Env var name, keyring:NAME (OS keychain), or file:/path"
            placeholder="MY_SECRET"
            value={form.password_env ?? ""}
            onChange={(v) => set({ password_env: v })}
            suggestedName={form.name}
          />
        </>
      )}
      <SchemaConfigFields
        fields={schemaFields}
        config={(form.options ?? {}) as Record<string, unknown>}
        onChange={setOptionValue}
      />
    </>
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

  if (provider.name === "local") {
    return (
      <Field
        label="Folder path"
        hint="Absolute path to a directory on the server — created automatically if it doesn't exist"
      >
        <Input
          value={form.database ?? ""}
          onChange={(e) => set({ database: e.target.value })}
          placeholder="/data/my-folder"
          autoFocus
        />
      </Field>
    );
  }

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
        <SecretRefField
          label="Secret Access Key"
          hint="Env var name, keyring:NAME, or file:/path holding the secret key (optional if using IAM)"
          placeholder="AWS_SECRET_ACCESS_KEY"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={`${form.name || "s3"}-secret-key`}
        />
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
        <SecretRefField
          label="Account key"
          hint="Env var name, keyring:NAME, or file:/path holding the account key"
          placeholder="AZURE_STORAGE_ACCOUNT_KEY"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={`${form.name || "azure"}-account-key`}
        />
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
        {/* GCS holds a *path* to a JSON credentials file, not a secret value,
            so the keychain-save affordance doesn't apply here. */}
        <SecretRefField
          label="Service account key"
          hint="Env var name (or file: ref) holding the path to a service account JSON file. Leave empty for Application Default Credentials."
          placeholder="GOOGLE_APPLICATION_CREDENTIALS"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={form.name}
          allowKeychain={false}
        />
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

/** Turn a connection name into a valid keychain entry name (keyring: grammar). */
function keyringNameFrom(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^[-.]+|[-.]+$/g, "");
  return slug || "secret";
}

/**
 * A connection secret field: the input holds a *reference*
 * (env var name, keyring:NAME, or file:/path). When the host has a usable OS
 * keychain, it also offers "Save a secret to the system keychain" — the entered
 * value is written straight to the OS keychain (never persisted by Ciaren) and
 * the field is set to the resulting keyring:NAME reference.
 */
function SecretRefField({
  label,
  hint,
  placeholder,
  value,
  onChange,
  suggestedName,
  allowKeychain = true,
}: {
  label: string;
  hint?: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  suggestedName: string;
  allowKeychain?: boolean;
}) {
  const keyring = useKeyringAvailability();
  const store = useStoreKeyringSecret();
  const [open, setOpen] = useState(false);
  const [entryName, setEntryName] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function openPanel() {
    setEntryName(keyringNameFrom(suggestedName));
    setSecretValue("");
    setError(null);
    setSaved(null);
    setOpen(true);
  }

  async function save(overwrite = false): Promise<void> {
    setError(null);
    try {
      const res = await store.mutateAsync({ name: entryName, value: secretValue, overwrite });
      onChange(res.reference);
      setSaved(res.reference);
      setSecretValue("");
      setOpen(false);
      // Drop the plaintext value react-query keeps as the mutation's `variables`.
      store.reset();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && !overwrite) {
        if (confirm(`${e.message}\n\nOverwrite it?`)) return save(true);
        return;
      }
      setError(e instanceof ApiError ? e.message : "Could not save to the keychain.");
    }
  }

  function cancel() {
    setSecretValue(""); // don't leave the plaintext secret lingering in state
    setError(null);
    setOpen(false);
  }

  return (
    <Field label={label} hint={hint}>
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      {saved ? (
        <p className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600">
          <Check className="h-3 w-3" />
          Saved to the OS keychain as <code>{saved}</code>.
        </p>
      ) : (
        // Show the keychain option whenever it makes sense for this field
        // (GCS opts out — it holds a file path). When the OS keychain isn't
        // available it stays visible but disabled, with a hover explaining why,
        // rather than silently vanishing.
        allowKeychain &&
        keyring.data && (
          <>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="h-px flex-1 bg-border" />
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">or</span>
              <span className="h-px flex-1 bg-border" />
            </div>
            {keyring.data.available ? (
              <button
                type="button"
                onClick={openPanel}
                className="mt-1.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-primary/40 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:border-primary/60 hover:bg-primary/10"
              >
                <KeyRound className="h-3.5 w-3.5" />
                Store a value in the OS keychain
              </button>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="mt-1.5 block w-full cursor-not-allowed">
                    <button
                      type="button"
                      disabled
                      className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-border bg-muted/40 px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                      Store a value in the OS keychain
                    </button>
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-center">
                  {keyring.data.detail ?? "The OS keychain isn't available on this host."}
                </TooltipContent>
              </Tooltip>
            )}
          </>
        )
      )}

      {/* Centered modal — keeps the panel out of the form's two-column grid so it
          isn't cramped against the right edge, and reads as a first-class option. */}
      <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : cancel())}>
        <DialogContent className="max-w-sm gap-4">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4 text-primary" />
              Store a secret in the OS keychain
            </DialogTitle>
            <DialogDescription>
              The value is written to your operating system&rsquo;s keychain and never stored by
              Ciaren. The connection keeps only a <code>keyring:NAME</code> reference.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <Field label="Keychain name" hint="You'll reference it as keyring:NAME">
              <Input
                value={entryName}
                onChange={(e) => setEntryName(e.target.value)}
                placeholder="pg-main"
                autoFocus
              />
            </Field>
            <Field label="Secret value">
              <Input
                type="password"
                value={secretValue}
                onChange={(e) => setSecretValue(e.target.value)}
                placeholder="the password / token"
                autoComplete="new-password"
                maxLength={4096}
              />
            </Field>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={cancel}>
              Cancel
            </Button>
            <Button
              onClick={() => void save(false)}
              disabled={!entryName || !secretValue || store.isPending}
            >
              {store.isPending ? "Saving…" : "Save to keychain"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Field>
  );
}
