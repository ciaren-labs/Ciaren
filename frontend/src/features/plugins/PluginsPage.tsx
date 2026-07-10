import { AlertTriangle, Blocks, ShieldAlert } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/ui/PageState";
import { usePluginDiagnostics } from "./hooks";
import { InstallButton } from "./components/InstallButton";
import { MarketplaceSection } from "./components/MarketplaceSection";
import { PluginCard } from "./components/PluginCard";

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
            <code className="rounded bg-muted px-1 py-0.5 text-xs">ciaren-plugin install</code>.
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
        <code className="rounded bg-muted px-1 py-0.5 text-xs">ciaren-plugin install &lt;file&gt;.ciarenplugin</code>,
        then it appears here.
      </p>
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
