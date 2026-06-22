import { AlertTriangle, Loader2, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  variant?: "destructive" | "warning" | "default";
  isPending?: boolean;
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  variant = "default",
  isPending,
  onConfirm,
}: ConfirmDialogProps) {
  const Icon =
    variant === "destructive" ? Trash2 : AlertTriangle;
  const iconClass =
    variant === "destructive"
      ? "text-destructive"
      : "text-amber-500";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className={`h-4 w-4 shrink-0 ${iconClass}`} />
            {title}
          </DialogTitle>
        </DialogHeader>
        <div className="text-sm text-muted-foreground">{description}</div>
        <div className="mt-2 flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
