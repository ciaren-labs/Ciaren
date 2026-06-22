import { AlertCircle, CheckCircle2, Loader2, MinusCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type Status = "pending" | "running" | "success" | "failed" | "skipped";

const META: Record<
  Status,
  { label: string; className: string; icon: typeof CheckCircle2; spin?: boolean }
> = {
  pending: {
    label: "Pending",
    className: "bg-muted text-muted-foreground",
    icon: Loader2,
  },
  running: {
    label: "Running",
    className: "bg-info/10 text-info",
    icon: Loader2,
    spin: true,
  },
  success: {
    label: "Success",
    className: "bg-success/10 text-success",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    className: "bg-destructive/10 text-destructive",
    icon: AlertCircle,
  },
  skipped: {
    label: "Skipped",
    className: "bg-muted text-muted-foreground",
    icon: MinusCircle,
  },
};

export function StatusBadge({
  status,
  className,
}: {
  status: Status;
  className?: string;
}) {
  const meta = META[status] ?? META.pending;
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        meta.className,
        className,
      )}
    >
      <Icon className={cn("h-3 w-3", meta.spin && "animate-spin")} />
      {meta.label}
    </span>
  );
}
