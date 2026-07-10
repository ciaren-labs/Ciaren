import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import type { FlowValidation } from "@/features/flows/editor/flowValidation";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Compact pill showing whether the flow is ready to run, plus a hover list of
 * the blocking errors / warnings.
 */
export function ValidationSummary({ validation }: { validation: FlowValidation }) {
  const { errors, warnings } = validation;

  if (errors.length === 0 && warnings.length === 0) {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700 animate-fade-in">
        <CheckCircle2 className="h-3.5 w-3.5" /> Ready to run
      </span>
    );
  }

  const isError = errors.length > 0;
  const items = [...errors, ...warnings];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className={cn(
            "flex cursor-help items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium animate-fade-in",
            isError
              ? "bg-destructive/10 text-destructive"
              : "bg-amber-100 text-amber-700",
          )}
        >
          {isError ? (
            <XCircle className="h-3.5 w-3.5" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5" />
          )}
          {errors.length > 0 && `${errors.length} error${errors.length > 1 ? "s" : ""}`}
          {errors.length > 0 && warnings.length > 0 && ", "}
          {warnings.length > 0 &&
            `${warnings.length} warning${warnings.length > 1 ? "s" : ""}`}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm">
        <ul className="flex list-disc flex-col gap-1 pl-3">
          {items.slice(0, 8).map((issue, i) => (
            <li key={i}>{issue.message}</li>
          ))}
          {items.length > 8 && <li>…and {items.length - 8} more</li>}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
