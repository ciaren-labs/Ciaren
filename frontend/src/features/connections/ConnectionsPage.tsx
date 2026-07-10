import { useState } from "react";
import { Database, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/PageState";
import { ApiError } from "@/lib/api/client";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import type { Connection, ProviderInfo } from "@/features/connections/types";
import { useConnectionProviders, useConnections, useDeleteConnection, useTestConnection } from "./hooks";
import { ConnectionDialog } from "./components/ConnectionDialog";
import { ProviderIconBadge } from "./components/providerMeta";
import { TestButton } from "./components/TestButton";

// ─── Constants ────────────────────────────────────────────────────────────────

function mkProvider(
  name: string,
  label: string,
  kind: "sql" | "mongo" | "storage" | "mlflow" | "api",
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

const FALLBACK_PROVIDERS: ProviderInfo[] = [
  mkProvider("postgresql", "PostgreSQL", "sql", "psycopg", "postgres", 5432, true, true, true),
  mkProvider("mysql", "MySQL / MariaDB", "sql", "pymysql", "mysql", 3306, true, true, true),
  mkProvider("sqlite", "SQLite", "sql", null, null, null, false, false, true),
  mkProvider("mssql", "SQL Server", "sql", "pyodbc", "mssql", 1433, true, true, true),
  mkProvider("duckdb", "DuckDB", "sql", "duckdb", "duckdb", null, false, false, true),
  mkProvider("snowflake", "Snowflake", "sql", "snowflake-connector-python", "snowflake", null, true, true, true),
  mkProvider("mongodb", "MongoDB", "mongo", "pymongo", "mongo", 27017, true, true, false),
  mkProvider("local", "Local Folder", "storage", null, null, null, false, false, false, true, false, false),
  mkProvider("s3", "AWS S3", "storage", "boto3", "s3", null, false, true, false, true, true, true),
  mkProvider("azure_blob", "Azure Blob Storage", "storage", "azure-storage-blob", "azure", null, false, true, false, true, false, true),
  mkProvider("gcs", "Google Cloud Storage", "storage", "google-cloud-storage", "gcs", null, false, false, false, true, false, false),
  mkProvider("rest_api", "REST API", "api", null, null, null, true, true, true),
  mkProvider("mlflow", "MLflow Tracking", "mlflow", "mlflow", "ml", null, false, false, false),
];

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
          <span className="flex items-center gap-1">
            {connection.last_tested_at ? (
              <>
                {connection.last_test_status && (
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full ${
                      connection.last_test_status === "ok" ? "bg-emerald-500" : "bg-destructive"
                    }`}
                    title={connection.last_test_error ?? undefined}
                  />
                )}
                <span>Tested {fmtDate(connection.last_tested_at)}</span>
                {connection.last_test_status && connection.last_test_status !== "ok" && (
                  <span className="text-destructive">· {connection.last_test_status}</span>
                )}
              </>
            ) : (
              "Never tested"
            )}
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
