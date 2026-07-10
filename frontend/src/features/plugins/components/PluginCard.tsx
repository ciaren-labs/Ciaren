import { useState } from "react";
import { Blocks, ChevronRight, KeyRound, Loader2, Power, ShieldAlert, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PluginInfo } from "@/features/plugins/types";
import { useEnablePlugin, useGrantPlugin } from "../hooks";
import { LicenseDialog } from "./LicenseDialog";
import { PluginDetailDialog } from "./PluginDetailDialog";
import { LicenseBadge, SignatureBadge, StatusBadge, STATUS_TINT } from "./statusMeta";

// Compact, scannable row: identity + status at a glance, the primary action
// inline, everything else behind a click (the detail dialog).
export function PluginCard({ plugin }: { plugin: PluginInfo }) {
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
