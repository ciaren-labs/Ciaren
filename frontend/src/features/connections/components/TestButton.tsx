import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Cable, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function TestButton({
  onTest,
  isPending,
  result,
  error,
  size = "default",
  disabled = false,
  className,
}: {
  onTest: () => void;
  isPending: boolean;
  result?: { ok: boolean; message: string };
  error?: unknown;
  size?: "sm" | "default";
  disabled?: boolean;
  className?: string;
}) {
  const [visibleResult, setVisibleResult] = useState<{ ok: boolean; message: string } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    clearTimeout(timerRef.current);
    // Derive a displayable result from either the happy-path data or a thrown error.
    const derived: { ok: boolean; message: string } | undefined =
      result ??
      (error
        ? { ok: false, message: (error as { message?: string }).message ?? "Test failed" }
        : undefined);
    if (derived) {
      setVisibleResult(derived);
      timerRef.current = setTimeout(() => setVisibleResult(null), 5000);
    } else {
      setVisibleResult(null);
    }
    return () => clearTimeout(timerRef.current);
  }, [result, error]);

  if (isPending) {
    return (
      <Button size={size} variant="outline" disabled className={className}>
        <Loader2 className={cn("animate-spin", size === "sm" ? "h-3 w-3" : "mr-1.5 h-3.5 w-3.5")} />
        {size !== "sm" && "Testing…"}
      </Button>
    );
  }

  if (visibleResult) {
    const button = (
      <Button
        size={size}
        variant="outline"
        onClick={onTest}
        title={visibleResult.message}
        className={cn(
          "transition-all duration-300",
          visibleResult.ok
            ? "border-emerald-400 bg-emerald-50 text-emerald-700 hover:bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400"
            : "border-red-400 bg-red-50 text-red-700 hover:bg-red-50 dark:bg-red-950 dark:text-red-400",
          !visibleResult.ok && className,
        )}
      >
        {visibleResult.ok ? (
          <Check className={cn(size === "sm" ? "h-3 w-3" : "mr-1.5 h-3.5 w-3.5")} />
        ) : (
          <AlertTriangle className={cn(size === "sm" ? "h-3 w-3" : "mr-1.5 h-3.5 w-3.5")} />
        )}
        {size === "sm"
          ? visibleResult.ok ? "OK" : "Error"
          : visibleResult.ok ? "Connected!" : "Failed"}
      </Button>
    );
    // Failure isn't just a red button — surface the real backend error message
    // as visible, accessible text (same convention as the create/update form
    // errors below), not just a hover-only title attribute.
    if (!visibleResult.ok) {
      return (
        <div className={cn("flex flex-col items-start gap-1", className)}>
          {button}
          <p role="alert" className="max-w-xs text-xs text-destructive">
            {visibleResult.message}
          </p>
        </div>
      );
    }
    return button;
  }

  return (
    <Button size={size} variant="outline" onClick={onTest} disabled={disabled} className={className}>
      {size !== "sm" && <Cable className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />}
      {size === "sm" ? "Test" : "Test connection"}
    </Button>
  );
}
