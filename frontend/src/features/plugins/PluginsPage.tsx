import { useRef, useState } from "react";
import {
  AlertTriangle,
  Blocks,
  Check,
  Download,
  KeyRound,
  Loader2,
  Lock,
  Power,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Store,
  Trash2,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState, LoadingState } from "@/components/ui/PageState";
import { cn } from "@/lib/utils";
import { getCategoryLabel } from "@/lib/nodeCatalog";
import { getCategoryTheme } from "@/lib/nodeVisuals";
import type { MarketplaceEntry, PluginInfo, PluginStatus } from "@/lib/types";
import { ApiError } from "@/lib/api";
import {
  useDisablePlugin,
  useEnablePlugin,
  useGrantPlugin,
  useInstallFromMarketplace,
  useInstallPlugin,
  useMarketplace,
  usePluginDiagnostics,
  usePluginLicense,
  useRevokePlugin,
  useUninstallPlugin,
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
  const { data, isPending, isError, error, refetch } = usePluginDiagnostics();
  const plugins = [...(data?.loaded ?? []), ...(data?.gated ?? [])];
  const errors = data?.errors ?? [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Plugins</h1>
          <p className="text-sm text-muted-foreground">
            Extend Ciaren with extra nodes, connectors, and exporters. Install a{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">.ciarenplugin</code> file below, drop one into{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">~/.ciaren/plugins</code>, or use{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">ciaren plugin install</code>.
          </p>
        </div>
        <InstallButton />
      </div>

      <TrustWarning />

      {isPending ? (
        <LoadingState label="Loading plugins…" />
      ) : isError ? (
        <ErrorState error={error} title="Couldn't load plugins" onRetry={() => refetch()} />
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

      <MarketplaceSection />
    </div>
  );
}

function InstallButton() {
  const inputRef = useRef<HTMLInputElement>(null);
  const install = useInstallPlugin();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const onPick = (file: File | undefined) => {
    if (!file) return;
    setMessage(null);
    install.mutate(file, {
      onSuccess: (res) =>
        setMessage({ ok: true, text: `Installed ${res.plugin.name} (${res.outcome}).` }),
      onError: (err) =>
        setMessage({ ok: false, text: err instanceof ApiError ? err.message : "Install failed." }),
    });
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <input
        ref={inputRef}
        type="file"
        accept=".ciarenplugin"
        className="hidden"
        onChange={(e) => {
          onPick(e.target.files?.[0]);
          e.target.value = ""; // allow re-picking the same file
        }}
      />
      <Button size="sm" disabled={install.isPending} onClick={() => inputRef.current?.click()}>
        {install.isPending ? (
          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
        ) : (
          <Upload className="mr-1.5 h-3.5 w-3.5" />
        )}
        Install plugin
      </Button>
      {message && (
        <span className={cn("text-xs", message.ok ? "text-emerald-600" : "text-red-600")}>
          {message.text}
        </span>
      )}
    </div>
  );
}

function TrustWarning() {
  return (
    <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="text-sm">
        <p className="font-semibold">Only install plugins you trust.</p>
        <p className="mt-1 leading-relaxed">
          A plugin is ordinary Python that runs on this machine with your account's
          access — it is <strong>not sandboxed</strong>. A malicious or buggy plugin
          could read or delete your files, use your saved credentials, or make network
          requests. Permissions shown below are a heads-up, not a security boundary.
          Install only plugins from sources you trust and whose code you can review.
          Ciaren cannot vet third-party plugins and is not responsible for what they do.
        </p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-border p-10 text-center">
      <Blocks className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
      <p className="text-sm font-medium">No plugins installed</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Ciaren works great on its own. Plugins add new nodes, connectors, and
        exporters. Install one with{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">ciaren plugin install &lt;file&gt;.ciarenplugin</code>,
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

// How a package verified at install time. Surfaces the provenance of an installed
// plugin so a trusted/signed package is visibly distinct from an unsigned drop-in.
const SIGNATURE_META: Record<string, { label: string; icon: typeof Shield; className: string }> = {
  trusted: {
    label: "Trusted",
    icon: ShieldCheck,
    className: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  },
  untrusted: {
    label: "Untrusted key",
    icon: ShieldAlert,
    className: "border-amber-300 bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  },
  unsigned: {
    label: "Unsigned",
    icon: Shield,
    className: "border-slate-300 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  },
  invalid: {
    label: "Invalid signature",
    icon: ShieldX,
    className: "border-red-300 bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  },
};

function SignatureBadge({ signature }: { signature: string }) {
  const meta = SIGNATURE_META[signature];
  if (!meta) return null; // "" — unknown provenance (e.g. a hand-dropped directory)
  const Icon = meta.icon;
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", meta.className)}
      title="How this package verified when it was installed"
    >
      <Icon className="h-3 w-3" /> {meta.label}
    </span>
  );
}

// Shows a license badge only when a license provider actually answers for this
// plugin (premium plugins). Community plugins report "no license provider" with
// no license_type, so nothing renders — keeping the common case clean.
function LicenseBadge({ id }: { id: string }) {
  const { data } = usePluginLicense(id);
  if (!data || !data.license_type) return null;
  const className = data.valid
    ? "border-violet-300 bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300"
    : "border-red-300 bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300";
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", className)}
      title={data.reason ?? undefined}
    >
      <KeyRound className="h-3 w-3" />
      {data.valid ? `Licensed · ${data.license_type}` : "License invalid"}
    </span>
  );
}

function PluginCard({ plugin }: { plugin: PluginInfo }) {
  const enable = useEnablePlugin();
  const disable = useDisablePlugin();
  const grant = useGrantPlugin();
  const revoke = useRevokePlugin();
  const uninstall = useUninstallPlugin();
  const [confirmUninstall, setConfirmUninstall] = useState(false);
  const busy =
    enable.isPending ||
    disable.isPending ||
    grant.isPending ||
    revoke.isPending ||
    uninstall.isPending;

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
            <SignatureBadge signature={plugin.signature} />
            <LicenseBadge id={plugin.id} />
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

          <NodePlacement nodes={plugin.nodes} nodeCategories={plugin.node_categories} />

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
          {plugin.uninstallable && (
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => setConfirmUninstall(true)}
              title="Delete this plugin's files and remove it"
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5 text-destructive" /> Uninstall
            </Button>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmUninstall}
        onOpenChange={setConfirmUninstall}
        title={`Uninstall ${plugin.name}?`}
        variant="destructive"
        confirmLabel="Uninstall"
        isPending={uninstall.isPending}
        description={
          <>
            This deletes the plugin's installed files and its contributed nodes leave
            the palette. Your flows that use those nodes will no longer run until the
            plugin is reinstalled. This can't be undone.
          </>
        }
        onConfirm={() =>
          uninstall.mutate(plugin.id, { onSuccess: () => setConfirmUninstall(false) })
        }
      />

      {plugin.status === "needs_permissions" && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {plugin.permissions.length > 0 ? (
              <>
                This plugin's code is <strong>not loaded</strong> until you approve the
                permissions above. Approving runs its code on this machine with your
                access — it is not sandboxed.
              </>
            ) : (
              <>
                This plugin declares no permissions, but approving still{" "}
                <strong>runs its code</strong> on this machine with your access (it is
                not sandboxed). Its code is <strong>not loaded</strong> until you approve.
              </>
            )}
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

function MarketplaceSection() {
  const { data, isLoading } = useMarketplace();
  if (isLoading || !data) return null;

  return (
    <div className="mt-10">
      <div className="mb-3 flex items-center gap-2">
        <Store className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Explore plugins</h2>
      </div>

      {!data.configured ? (
        <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
          No catalog is configured. Point{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">CIAREN_MARKETPLACE_INDEX</code> at a{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">marketplace.json</code> file to browse plugins
          here. Add entries with{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">ciaren plugin index add</code>.
        </div>
      ) : data.plugins.length === 0 ? (
        <p className="text-sm text-muted-foreground">The catalog is empty.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {data.plugins.map((e) => (
            <MarketplaceCard key={e.id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}

function MarketplaceCard({ entry }: { entry: MarketplaceEntry }) {
  const install = useInstallFromMarketplace();
  const [error, setError] = useState<string | null>(null);

  const onInstall = () => {
    setError(null);
    install.mutate(entry.id, {
      onError: (err) => setError(err instanceof ApiError ? err.message : "Install failed."),
    });
  };

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start gap-3">
        <div className="shrink-0 rounded-lg bg-muted p-2.5">
          <Store className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{entry.name}</span>
            <span className="text-xs text-muted-foreground">v{entry.version}</span>
            {entry.license_required && (
              <span className="rounded-full border border-violet-300 bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                License required
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {entry.publisher && <>by {entry.publisher} · </>}
            <span className="font-mono">{entry.id}</span>
          </p>
          {entry.description && (
            <p className="mt-1.5 text-sm text-muted-foreground">{entry.description}</p>
          )}
          {entry.permissions.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              Requests: <span className="font-medium">{entry.permissions.join(", ")}</span>
            </p>
          )}
          <NodePlacement nodes={entry.nodes} nodeCategories={entry.node_categories} />
          {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        </div>

        <div className="shrink-0">
          {entry.installed ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <Check className="h-3 w-3" /> Installed
            </span>
          ) : entry.installable ? (
            <Button size="sm" disabled={install.isPending} onClick={onInstall}>
              {install.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="mr-1.5 h-3.5 w-3.5" />
              )}
              Install
            </Button>
          ) : (
            <span className="text-[11px] text-muted-foreground" title="Download the .ciarenplugin and install it manually">
              Manual install
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function NodePlacement({
  nodes,
  nodeCategories,
}: {
  nodes: string[];
  nodeCategories: Record<string, string>;
}) {
  if (nodes.length === 0) return null;
  return (
    <div className="mt-2.5">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Appears as node
      </p>
      <div className="flex flex-wrap gap-1">
        {nodes.map((node) => {
          const category = nodeCategories[node] ?? "plugins";
          const theme = getCategoryTheme(category);
          return (
            <span
              key={node}
              className="inline-flex items-center overflow-hidden rounded-md border border-border bg-background text-[10px] shadow-sm"
            >
              <span className="px-1.5 py-0.5 font-mono text-slate-700">{node}</span>
              <span className={cn("border-l border-border px-1.5 py-0.5 font-medium", theme.text)}>
                {getCategoryLabel(category)}
              </span>
            </span>
          );
        })}
      </div>
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
