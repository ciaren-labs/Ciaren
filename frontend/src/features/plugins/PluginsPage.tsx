import { useRef, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Blocks,
  Check,
  ChevronRight,
  Download,
  KeyRound,
  Loader2,
  Lock,
  Power,
  RefreshCw,
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorState, LoadingState } from "@/components/ui/PageState";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { getCategoryLabel } from "@/lib/nodeCatalog";
import { getCategoryTheme } from "@/lib/nodeVisuals";
import type { MarketplaceEntry, PluginInfo, PluginStatus } from "@/lib/types";
import { ApiError } from "@/lib/api";
import {
  useActivateLicense,
  useDisablePlugin,
  useEnablePlugin,
  useGrantPlugin,
  useInstallFromMarketplace,
  useInstallPlugin,
  useMarketplace,
  usePluginDiagnostics,
  usePluginLicense,
  useRemoveLicense,
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

const STATUS_META: Record<PluginStatus, { label: string; className: string; help: string }> = {
  loaded: {
    label: "Active",
    className: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    help: "This plugin's code is loaded and its nodes are available in the editor.",
  },
  disabled: {
    label: "Disabled",
    className: "border-slate-300 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    help: "You turned this plugin off — its code is not loaded and its nodes are hidden.",
  },
  needs_permissions: {
    label: "Needs approval",
    className: "border-amber-300 bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    help: "Discovered but not running: its code stays un-imported until you approve it.",
  },
  needs_license: {
    label: "License required",
    className: "border-violet-300 bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
    help: "Approved, but it has no valid license — activate a license token to load it.",
  },
};

const STATUS_TINT: Record<PluginStatus, string> = {
  loaded: "#10b981",
  needs_permissions: "#f59e0b",
  needs_license: "#8b5cf6",
  disabled: "#94a3b8",
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
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("cursor-help rounded-full border px-2 py-0.5 text-[11px] font-medium", meta.className)}>
          {meta.label}
        </span>
      </TooltipTrigger>
      <TooltipContent>{meta.help}</TooltipContent>
    </Tooltip>
  );
}

// How a package verified at install time. Surfaces the provenance of an installed
// plugin so a trusted/signed package is visibly distinct from an unsigned drop-in.
const SIGNATURE_META: Record<string, { label: string; icon: typeof Shield; className: string; help: string }> = {
  trusted: {
    label: "Trusted",
    icon: ShieldCheck,
    className: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    help: "Signed, and the signature verified against a publisher key you trust. The package hasn't been altered since it was signed.",
  },
  untrusted: {
    label: "Untrusted key",
    icon: ShieldAlert,
    className: "border-amber-300 bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    help: "Signed, but by a key that isn't in your trusted keys — the publisher's identity couldn't be verified. Treat it like any code you downloaded from the internet.",
  },
  unsigned: {
    label: "Unsigned",
    icon: Shield,
    className: "border-slate-300 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    help: "The package carries no signature, so there is no way to verify who published it or that it wasn't modified.",
  },
  invalid: {
    label: "Invalid signature",
    icon: ShieldX,
    className: "border-red-300 bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
    help: "The signature does not match the package contents — it may have been tampered with. Don't run it unless you know why.",
  },
};

function SignatureBadge({ signature, official }: { signature: string; official?: boolean }) {
  // First-party refinement of "trusted": signed by a publisher key that ships
  // pinned inside the app (like a Microsoft-published VS Code extension), not
  // merely a key the user added to their trusted set.
  if (official && signature === "trusted") {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex cursor-help items-center gap-1 rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 dark:bg-sky-950 dark:text-sky-300">
            <BadgeCheck className="h-3 w-3" /> Official
          </span>
        </TooltipTrigger>
        <TooltipContent>
          Published by the Ciaren team: the signature verified against a publisher key built
          into the app itself, so it can't be spoofed by a catalog or a config change.
        </TooltipContent>
      </Tooltip>
    );
  }
  const meta = SIGNATURE_META[signature];
  if (!meta) return null; // "" — unknown provenance (e.g. a hand-dropped directory)
  const Icon = meta.icon;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-flex cursor-help items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            meta.className,
          )}
        >
          <Icon className="h-3 w-3" /> {meta.label}
        </span>
      </TooltipTrigger>
      <TooltipContent>How this package verified when it was installed: {meta.help}</TooltipContent>
    </Tooltip>
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

// Compact, scannable row: identity + status at a glance, the primary action
// inline, everything else behind a click (the detail dialog).
function PluginCard({ plugin }: { plugin: PluginInfo }) {
  const [open, setOpen] = useState(false);
  const [licenseOpen, setLicenseOpen] = useState(false);
  const grant = useGrantPlugin();
  const enable = useEnablePlugin();
  const tint = STATUS_TINT[plugin.status];

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-label={`${plugin.name} details`}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setOpen(true);
          }
        }}
        className="cursor-pointer rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex items-center gap-3">
          <div className="shrink-0 rounded-lg p-2.5" style={{ backgroundColor: `${tint}1a` }}>
            <Blocks className="h-5 w-5" style={{ color: tint }} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{plugin.name}</span>
              {plugin.version && <span className="text-xs text-muted-foreground">v{plugin.version}</span>}
              <StatusBadge status={plugin.status} />
              <SignatureBadge signature={plugin.signature} official={plugin.official} />
              <LicenseBadge id={plugin.id} />
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {plugin.publisher && <>by {plugin.publisher} · </>}
              {plugin.description || <span className="font-mono">{plugin.id}</span>}
            </p>
          </div>
          {/* Inline actions must not bubble into the card's open-details click. */}
          <div
            className="flex shrink-0 items-center gap-2"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            {plugin.status === "needs_permissions" && (
              <Button
                size="sm"
                disabled={grant.isPending}
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
            {plugin.status === "needs_license" && (
              <Button size="sm" onClick={() => setLicenseOpen(true)} title="Paste a license token to load this plugin">
                <KeyRound className="mr-1.5 h-3.5 w-3.5" /> Add license
              </Button>
            )}
            {plugin.status === "disabled" && (
              <Button size="sm" variant="outline" disabled={enable.isPending} onClick={() => enable.mutate(plugin.id)}>
                <Power className="mr-1.5 h-3.5 w-3.5" /> Enable
              </Button>
            )}
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
        {plugin.status === "needs_permissions" && (
          <p className="mt-2 flex items-center gap-1.5 text-[12px] text-amber-700 dark:text-amber-300">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
            Not loaded until you approve — approving runs its code on this machine, unsandboxed.
          </p>
        )}
        {plugin.status === "needs_license" && (
          <p className="mt-2 flex items-center gap-1.5 text-[12px] text-violet-700 dark:text-violet-300">
            <KeyRound className="h-3.5 w-3.5 shrink-0" />
            {plugin.status_detail || "This plugin needs a valid license before it loads."}
          </p>
        )}
      </div>
      <PluginDetailDialog
        plugin={plugin}
        open={open}
        onOpenChange={setOpen}
        onAddLicense={() => {
          setOpen(false);
          setLicenseOpen(true);
        }}
      />
      <LicenseDialog plugin={plugin} open={licenseOpen} onOpenChange={setLicenseOpen} />
    </>
  );
}

// Paste-a-token activation. The backend vets the token against the trusted
// issuer keys before caching it, so a bad paste can't clobber a working license.
function LicenseDialog({
  plugin,
  open,
  onOpenChange,
}: {
  plugin: PluginInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const activate = useActivateLicense();
  const [raw, setRaw] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onActivate = () => {
    setError(null);
    let token: unknown;
    try {
      token = JSON.parse(raw);
    } catch {
      setError("That doesn't look like a license token (invalid JSON).");
      return;
    }
    activate.mutate(
      { id: plugin.id, token },
      {
        onSuccess: (status) => {
          if (status.valid) {
            onOpenChange(false);
            setRaw("");
          } else {
            setError(status.reason ?? "The license did not validate.");
          }
        },
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : "Couldn't activate the license."),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="h-4 w-4" /> Activate license — {plugin.name}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Paste the license token you received after purchase (a small JSON document). It is
          stored only on this machine and keeps working offline within its grace period.
        </p>
        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          rows={7}
          spellCheck={false}
          placeholder='{"userId": "...", "pluginId": "...", "signature": "..."}'
          className="w-full rounded-md border border-border bg-background p-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button size="sm" disabled={activate.isPending || !raw.trim()} onClick={onActivate}>
            {activate.isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <KeyRound className="mr-1.5 h-3.5 w-3.5" />
            )}
            Activate
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 text-xs">
      <dt className="w-28 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-all font-medium">{children}</dd>
    </div>
  );
}

function PluginDetailDialog({
  plugin,
  open,
  onOpenChange,
  onAddLicense,
}: {
  plugin: PluginInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAddLicense: () => void;
}) {
  const enable = useEnablePlugin();
  const disable = useDisablePlugin();
  const grant = useGrantPlugin();
  const revoke = useRevokePlugin();
  const uninstall = useUninstallPlugin();
  const removeLicense = useRemoveLicense();
  const { data: license } = usePluginLicense(plugin.id);
  const [confirmUninstall, setConfirmUninstall] = useState(false);
  const busy =
    enable.isPending ||
    disable.isPending ||
    grant.isPending ||
    revoke.isPending ||
    removeLicense.isPending ||
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
  const tint = STATUS_TINT[plugin.status];

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto">
          <DialogHeader>
            <div className="flex items-start gap-3">
              <div className="shrink-0 rounded-lg p-2.5" style={{ backgroundColor: `${tint}1a` }}>
                <Blocks className="h-5 w-5" style={{ color: tint }} />
              </div>
              <div className="min-w-0 flex-1">
                <DialogTitle className="flex flex-wrap items-center gap-2">
                  {plugin.name}
                  {plugin.version && (
                    <span className="text-xs font-normal text-muted-foreground">v{plugin.version}</span>
                  )}
                </DialogTitle>
                <p className="mt-1 text-xs text-muted-foreground">
                  {plugin.publisher && <>by {plugin.publisher} · </>}
                  <span className="font-mono">{plugin.id}</span> · {plugin.source}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusBadge status={plugin.status} />
                  <SignatureBadge signature={plugin.signature} official={plugin.official} />
                  <LicenseBadge id={plugin.id} />
                </div>
              </div>
            </div>
          </DialogHeader>

          {plugin.description && (
            <p className="text-sm text-muted-foreground">{plugin.description}</p>
          )}

          {plugin.status === "needs_license" && (
            <div className="flex items-start gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-[12px] text-violet-800 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-200">
              <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{plugin.status_detail || "This plugin needs a valid license before it loads."}</span>
            </div>
          )}

          {plugin.status === "needs_permissions" && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
              <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                {plugin.permissions.length > 0 ? (
                  <>
                    This plugin's code is <strong>not loaded</strong> until you approve the
                    permissions below. Approving runs its code on this machine with your
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

          <div>
            {plugin.permissions.length > 0 && (
              <PermissionList permissions={plugin.permissions} granted={granted} />
            )}

            <NodePlacement nodes={plugin.nodes} nodeCategories={plugin.node_categories} />

            <ContributionChips label="Connectors" items={plugin.connectors ?? []} />
            <ContributionChips label="ML model types" items={plugin.model_types ?? []} />

            {plugin.capabilities.length > 0 && (
              <div className="mt-2.5">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Capabilities
                </p>
                <div className="flex flex-wrap gap-1">
                  {plugin.capabilities.map((c) => (
                    <span key={c} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <dl className="mt-4 flex flex-col gap-1.5 border-t border-border pt-3">
              {plugin.license && (
                <DetailRow label="License">
                  {plugin.license}
                  {license?.license_type && license.expires_at && <> · expires {license.expires_at}</>}
                </DetailRow>
              )}
              {plugin.trust && <DetailRow label="Trust tier">{plugin.trust}</DetailRow>}
              {plugin.ciaren_spec && <DetailRow label="Compatibility">Ciaren {plugin.ciaren_spec}</DetailRow>}
              {plugin.dependencies.length > 0 && (
                <DetailRow label="Dependencies">
                  <span className="font-mono">{plugin.dependencies.join(", ")}</span>
                </DetailRow>
              )}
              {plugin.entrypoint && (
                <DetailRow label="Entry point">
                  <span className="font-mono">{plugin.entrypoint}</span>
                </DetailRow>
              )}
              {plugin.install_path && (
                <DetailRow label="Installed at">
                  <span className="font-mono">{plugin.install_path}</span>
                </DetailRow>
              )}
            </dl>
          </div>

          <div className="mt-1 flex flex-wrap justify-end gap-2 border-t border-border pt-3">
            {plugin.uninstallable && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                className="mr-auto"
                onClick={() => {
                  // Close the detail view first so the confirm stands alone.
                  onOpenChange(false);
                  setConfirmUninstall(true);
                }}
                title="Delete this plugin's files and remove it"
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5 text-destructive" /> Uninstall
              </Button>
            )}
            {license?.license_type && license.valid && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => removeLicense.mutate(plugin.id)}
                title="Remove the license token from this machine (e.g. to move the seat elsewhere)"
              >
                <KeyRound className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" /> Remove license
              </Button>
            )}
            {plugin.status === "needs_license" && (
              <Button size="sm" disabled={busy} onClick={onAddLicense} title="Paste a license token to load this plugin">
                <KeyRound className="mr-1.5 h-3.5 w-3.5" /> Add license
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
            {plugin.status !== "disabled" ? (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => disable.mutate(plugin.id)}
                title="Stop loading this plugin"
              >
                <Power className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" /> Disable
              </Button>
            ) : (
              <Button size="sm" variant="outline" disabled={busy} onClick={() => enable.mutate(plugin.id)}>
                <Power className="mr-1.5 h-3.5 w-3.5" /> Enable
              </Button>
            )}
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
          </div>
        </DialogContent>
      </Dialog>

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
    </>
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

      {data.revoked_installed.length > 0 && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-300 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/60 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="text-sm">
            <p className="font-semibold">The catalog has revoked plugins you have installed.</p>
            <p className="mt-1 leading-relaxed">
              {data.revoked_installed.map((id) => (
                <code key={id} className="mr-1.5 rounded bg-red-100 px-1 py-0.5 font-mono text-xs dark:bg-red-900">
                  {id}
                </code>
              ))}
              — the publisher or catalog withdrew {data.revoked_installed.length === 1 ? "it" : "them"} (for
              example a malicious or broken release). Consider uninstalling from the list above.
            </p>
          </div>
        </div>
      )}

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

// The catalog's trust tier is *derived* by the backend (it verifies the local
// artifact's signature against the user's trusted keys) — never echoed from the
// publisher-controlled index, so this badge can't be spoofed by a catalog entry.
function CatalogTrustBadge({ trust }: { trust: string }) {
  const meta =
    trust === "official"
      ? {
          label: "Official",
          Icon: BadgeCheck,
          className: "border-sky-300 bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
          help: "Published by the Ciaren team: the signature verified against a publisher key built into the app itself, so it can't be spoofed by a catalog entry.",
        }
      : trust === "trusted"
        ? {
            label: "Trusted",
            Icon: ShieldCheck,
            className:
              "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
            help: "Ciaren verified this package's signature against a publisher key you trust.",
          }
        : {
            label: "Community",
            Icon: Shield,
            className: "border-slate-300 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
            help: "Not verified against a trusted publisher key. Anyone can publish a community plugin — review it before installing, like any code from the internet.",
          };
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-flex cursor-help items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            meta.className,
          )}
        >
          <meta.Icon className="h-3 w-3" />
          {meta.label}
        </span>
      </TooltipTrigger>
      <TooltipContent>{meta.help}</TooltipContent>
    </Tooltip>
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
            {entry.update_available && entry.installed_version ? (
              <span className="text-xs text-muted-foreground">
                v{entry.installed_version} → <span className="font-medium text-foreground">v{entry.version}</span>
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">v{entry.version}</span>
            )}
            <CatalogTrustBadge trust={entry.trust} />
            {entry.license_required && (
              <span className="rounded-full border border-violet-300 bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                License required
              </span>
            )}
            {entry.revoked && (
              <span
                className="rounded-full border border-red-300 bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700 dark:bg-red-950 dark:text-red-300"
                title="The catalog withdrew this plugin; it can no longer be installed from here."
              >
                Revoked
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {entry.publisher && <>by {entry.publisher} · </>}
            <span className="font-mono">{entry.id}</span>
            {entry.license && <> · {entry.license} license</>}
          </p>
          {entry.description && (
            <p className="mt-1.5 text-sm text-muted-foreground">{entry.description}</p>
          )}
          {entry.permissions.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              Requests: <span className="font-medium">{entry.permissions.join(", ")}</span>
            </p>
          )}
          {(entry.ciaren_spec || entry.dependencies.length > 0) && (
            <p className="mt-1 text-xs text-muted-foreground">
              {entry.ciaren_spec && (
                <>
                  Requires Ciaren <span className="font-mono">{entry.ciaren_spec}</span>
                </>
              )}
              {entry.ciaren_spec && entry.dependencies.length > 0 && <> · </>}
              {entry.dependencies.length > 0 && (
                <>
                  Installs: <span className="font-mono">{entry.dependencies.join(", ")}</span>
                </>
              )}
            </p>
          )}
          <NodePlacement nodes={entry.nodes} nodeCategories={entry.node_categories} />
          {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        </div>

        <div className="shrink-0">
          {entry.revoked ? (
            // The backend refuses installs of revoked entries; offer nothing here.
            entry.installed && (
              <span className="inline-flex items-center gap-1 rounded-full border border-red-300 bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
                Installed — revoked
              </span>
            )
          ) : entry.installed && entry.update_available && entry.installable ? (
            <Button size="sm" disabled={install.isPending} onClick={onInstall} title={`Update to v${entry.version}`}>
              {install.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              )}
              Update
            </Button>
          ) : entry.installed ? (
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

function ContributionChips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2.5">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="flex flex-wrap gap-1">
        {items.map((item) => (
          <span
            key={item}
            className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-slate-700 shadow-sm"
          >
            {item}
          </span>
        ))}
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
