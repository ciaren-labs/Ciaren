import { BadgeCheck, KeyRound, Shield, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { PluginStatus } from "@/features/plugins/types";
import { usePluginLicense } from "../hooks";

export const STATUS_META: Record<PluginStatus, { label: string; className: string; help: string }> = {
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

export const STATUS_TINT: Record<PluginStatus, string> = {
  loaded: "#10b981",
  needs_permissions: "#f59e0b",
  needs_license: "#8b5cf6",
  disabled: "#94a3b8",
};

export function StatusBadge({ status }: { status: PluginStatus }) {
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

export function SignatureBadge({ signature, official }: { signature: string; official?: boolean }) {
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
export function LicenseBadge({ id }: { id: string }) {
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
