import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProviderInfo } from "@/features/connections/types";
import { getProviderMeta, ProviderIconBadge } from "./providerMeta";

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

export function ProviderSection({
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
