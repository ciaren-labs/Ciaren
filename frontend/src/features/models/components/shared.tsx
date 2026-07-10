import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Copy, GitBranch, Loader2 } from "lucide-react";
import type { MlLineage } from "@/features/models/types";

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      }}
      title={`Copy ${label}`}
      className="inline-flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
      {label}
    </button>
  );
}

export function LineageChips({
  lineage,
  flowName,
}: {
  lineage: MlLineage;
  flowName?: Map<string, string>;
}) {
  if (!lineage.flow_id && !lineage.run_id) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const label = lineage.flow_id ? flowName?.get(lineage.flow_id) ?? "Flow" : null;
  return (
    <span className="flex items-center gap-1.5 whitespace-nowrap">
      {lineage.flow_id && (
        <Link
          to={`/flows/${lineage.flow_id}`}
          title={label ?? undefined}
          className="inline-flex max-w-[160px] items-center gap-1 truncate rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 transition-colors hover:bg-brand-100"
        >
          <GitBranch className="h-3 w-3 shrink-0" /> <span className="truncate">{label}</span>
        </Link>
      )}
      {lineage.run_id && (
        <Link
          to={`/runs/${lineage.run_id}`}
          className="inline-flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent"
        >
          Run
        </Link>
      )}
    </span>
  );
}

export function Loading() {
  return (
    <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading…
    </p>
  );
}

export function ErrorBox({ what }: { what: string }) {
  return (
    <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
      Could not load {what}. Check that the MLflow tracking store is reachable (Connections → Local MLflow).
    </div>
  );
}

export function EmptyBox({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-4 rounded-lg border border-dashed border-border p-10 text-center">
      <p className="text-sm font-medium">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{body}</p>}
    </div>
  );
}
