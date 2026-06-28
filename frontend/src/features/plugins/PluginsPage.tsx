import {
  AlertTriangle,
  Blocks,
  Check,
  Loader2,
  Lock,
  Power,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PluginInfo, PluginStatus } from "@/lib/types";
import {
  useDisablePlugin,
  useEnablePlugin,
  useGrantPlugin,
  usePluginDiagnostics,
  useRevokePlugin,
} from "./hooks";

// Short, friendly explanations for the permissions a plugin can request. Keeps
// the approval prompt understandable for non-experts.
const PERMISSION_HELP: Record<string, string> = {
  filesystem_read: "Read files on this machine",
  filesystem_write: "Write files on this machine",
  network: "Make network requests",
  credentials: "Use stored credentials",
  subprocess: "Run other programs",
  shell: "Run shell commands",
  docker: "Control Docker",
  local_model_load: "Load local model files",
  joblib_load: "Load joblib/pickle files (can run code)",
  database_access: "Connect to databases",
  cloud_access: "Access cloud storage",
  llm_access: "Call LLM services",
  telemetry: "Send usage telemetry",
};

const STATUS_META: Record<PluginStatus, { label: string; className: string }> = {
  loaded: {
    label: "Active",
    className: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  },
  disabled: {
    label: "Disabled",
    className: "border-slate-300 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  },
  needs_permissions: {
    label: "Needs approval",
    className: "border-amber-300 bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  },
};

export function PluginsPage() {
  const { data, isLoading } = usePluginDiagnostics();
  const plugins = [...(data?.loaded ?? []), ...(data?.gated ?? [])];
  const errors = data?.errors ?? [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Plugins</h1>
        <p className="text-sm text-muted-foreground">
          Extend FlowFrame with extra nodes, connectors, and exporters. Plugins run
          code on this machine — review what they ask for before approving. Drop a
          plugin into <code className="rounded bg-muted px-1 py-0.5 text-xs">~/.flowframe/plugins</code>{" "}
          or install one with{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">flowframe plugin install</code>.
        </p>
      </div>

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      ) : plugins.length === 0 && errors.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="flex flex-col gap-3">
          {plugins.map((p) => (
            <PluginCard key={p.id} plugin={p} />
          ))}
          {errors.length > 0 && <ErrorsPanel errors={errors} />}
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-border p-10 text-center">
      <Blocks className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
      <p className="text-sm font-medium">No plugins installed</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        FlowFrame works great on its own. Plugins add new nodes, connectors, and
        exporters. Install one with{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">flowframe plugin install &lt;file&gt;.ffplugin</code>,
        then it appears here.
      </p>
    </div>
  );
}

function StatusBadge({ status }: { status: PluginStatus }) {
  const meta = STATUS_META[status];
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[11px] font-medium", meta.className)}>
      {meta.label}
    </span>
  );
}

function PluginCard({ plugin }: { plugin: PluginInfo }) {
  const enable = useEnablePlugin();
  const disable = useDisablePlugin();
  const grant = useGrantPlugin();
  const revoke = useRevokePlugin();
  const busy =
    enable.isPending || disable.isPending || grant.isPending || revoke.isPending;

  // A loaded plugin's declared permissions are in force (its code is running), so
  // show them as active rather than "not granted". For a plugin still pending
  // approval, show exactly what the user has granted so far.
  const isLoaded = plugin.status === "loaded";
  const granted = new Set(isLoaded ? plugin.permissions : plugin.granted_permissions);
  // Revoking only means something when the user previously consented to a gated
  // plugin's permissions (drop-in plugins). Entry-point packages aren't gated, so
  // "Disable" is the way to stop them instead.
  const canRevoke = plugin.granted_permissions.length > 0;
  const tintByStatus = {
    loaded: "#10b981",
    needs_permissions: "#f59e0b",
    disabled: "#94a3b8",
  }[plugin.status];

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start gap-3">
        <div
          className="shrink-0 rounded-lg p-2.5"
          style={{ backgroundColor: `${tintByStatus}1a` }}
        >
          <Blocks className="h-5 w-5" style={{ color: tintByStatus }} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{plugin.name}</span>
            <span className="text-xs text-muted-foreground">v{plugin.version}</span>
            <StatusBadge status={plugin.status} />
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {plugin.publisher && <>by {plugin.publisher} · </>}
            <span className="font-mono">{plugin.id}</span> · {plugin.source}
          </p>
          {plugin.description && (
            <p className="mt-1.5 text-sm text-muted-foreground">{plugin.description}</p>
          )}

          {plugin.capabilities.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {plugin.capabilities.map((c) => (
                <span key={c} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                  {c}
                </span>
              ))}
            </div>
          )}

          {plugin.permissions.length > 0 && (
            <PermissionList permissions={plugin.permissions} granted={granted} />
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {plugin.status === "needs_permissions" && (
            <Button
              size="sm"
              disabled={busy}
              onClick={() => grant.mutate({ id: plugin.id })}
              title="Grant the requested permissions and load the plugin"
            >
              {grant.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />
              )}
              Approve
            </Button>
          )}
          {plugin.status === "disabled" && (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => enable.mutate(plugin.id)}>
              <Power className="mr-1.5 h-3.5 w-3.5" /> Enable
            </Button>
          )}
          {plugin.status !== "disabled" && canRevoke && (
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => revoke.mutate({ id: plugin.id, permissions: plugin.granted_permissions })}
              title="Withdraw the permissions you granted; the plugin stops loading until you approve again"
            >
              <ShieldX className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" /> Revoke
            </Button>
          )}
          {plugin.status !== "disabled" && (
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => disable.mutate(plugin.id)}
              title="Stop loading this plugin"
            >
              <Power className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" /> Disable
            </Button>
          )}
        </div>
      </div>

      {plugin.status === "needs_permissions" && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            This plugin's code is <strong>not loaded</strong> until you approve the
            permissions above.
          </span>
        </div>
      )}
    </div>
  );
}

function PermissionList({
  permissions,
  granted,
}: {
  permissions: string[];
  granted: Set<string>;
}) {
  return (
    <div className="mt-2.5">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Permissions
      </p>
      <ul className="flex flex-col gap-1">
        {permissions.map((perm) => {
          const isGranted = granted.has(perm);
          return (
            <li key={perm} className="flex items-center gap-2 text-xs">
              {isGranted ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
              ) : (
                <Lock className="h-3.5 w-3.5 shrink-0 text-amber-600" />
              )}
              <span className="font-medium">{perm}</span>
              <span className="text-muted-foreground">— {PERMISSION_HELP[perm] ?? "Custom permission"}</span>
              {!isGranted && <span className="text-amber-600">(not granted)</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ErrorsPanel({ errors }: { errors: { source: string; error: string }[] }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
        <AlertTriangle className="h-4 w-4" /> Plugins that failed to load
      </div>
      <ul className="flex flex-col gap-1.5">
        {errors.map((e, i) => (
          <li key={i} className="text-xs text-red-700 dark:text-red-300">
            <span className="font-mono font-medium">{e.source}</span>: {e.error}
          </li>
        ))}
      </ul>
    </div>
  );
}
