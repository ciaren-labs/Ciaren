import { useEffect } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { useToastStore, type Toast, type ToastVariant } from "@/stores/toastStore";
import { cn } from "@/lib/utils";

const VARIANT_STYLES: Record<ToastVariant, { icon: typeof Info; iconClass: string }> = {
  success: { icon: CheckCircle2, iconClass: "text-success" },
  error: { icon: AlertCircle, iconClass: "text-destructive" },
  warning: { icon: AlertTriangle, iconClass: "text-warning" },
  info: { icon: Info, iconClass: "text-info" },
};

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss);
  const { icon: Icon, iconClass } = VARIANT_STYLES[toast.variant];

  useEffect(() => {
    const timer = setTimeout(() => dismiss(toast.id), toast.duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, dismiss]);

  return (
    <div
      role={toast.variant === "error" ? "alert" : "status"}
      className="pointer-events-auto flex w-full animate-slide-in-right items-start gap-2.5 rounded-lg border border-border bg-popover p-3 shadow-lg"
    >
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", iconClass)} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-snug">{toast.title}</p>
        {toast.description && (
          <p className="mt-0.5 break-words text-xs text-muted-foreground">{toast.description}</p>
        )}
        {toast.action && (
          <Link
            to={toast.action.to}
            onClick={() => dismiss(toast.id)}
            className="mt-1.5 inline-block text-xs font-medium text-primary hover:underline"
          >
            {toast.action.label} →
          </Link>
        )}
      </div>
      <button
        onClick={() => dismiss(toast.id)}
        className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label="Dismiss notification"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/** Fixed bottom-right stack of app notifications. Mounted once in App. */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[22rem] max-w-[calc(100vw-2rem)] flex-col gap-2"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
