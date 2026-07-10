import { useState } from "react";
import { AlertTriangle, BadgeCheck, Check, Download, Loader2, RefreshCw, Shield, ShieldCheck, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";
import type { MarketplaceEntry } from "@/features/plugins/types";
import { useInstallFromMarketplace, useMarketplace } from "../hooks";
import { NodePlacement } from "./chips";

export function MarketplaceSection() {
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
