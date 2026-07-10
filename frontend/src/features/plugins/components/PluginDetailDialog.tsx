import { useState } from "react";
import { Blocks, Check, KeyRound, Loader2, Lock, Power, ShieldAlert, ShieldCheck, ShieldX, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { PluginInfo } from "@/features/plugins/types";
import {
  useDisablePlugin,
  useEnablePlugin,
  useGrantPlugin,
  usePluginLicense,
  useRemoveLicense,
  useRevokePlugin,
  useUninstallPlugin,
} from "../hooks";
import { ContributionChips, NodePlacement } from "./chips";
import { LicenseBadge, SignatureBadge, StatusBadge, STATUS_TINT } from "./statusMeta";

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

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 text-xs">
      <dt className="w-28 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-all font-medium">{children}</dd>
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

export function PluginDetailDialog({
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
