import { useEffect, useState } from "react";
import { AlertCircle, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { PROJECT_COLORS } from "@/lib/projectColors";
import type { Project, ProjectCreate } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ProjectFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  initial?: Project;
  submitting: boolean;
  error: unknown;
  onSubmit: (values: ProjectCreate) => void;
}

export function ProjectFormDialog({
  open,
  onOpenChange,
  title,
  initial,
  submitting,
  error,
  onSubmit,
}: ProjectFormDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("violet");

  // Reset the form whenever the dialog opens (for create or a different project).
  useEffect(() => {
    if (open) {
      setName(initial?.name ?? "");
      setDescription(initial?.description ?? "");
      setColor(initial?.color ?? "violet");
    }
  }, [open, initial]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({ name: name.trim(), description: description.trim() || undefined, color });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Marketing analytics"
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this workspace is for (optional)"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Colour</Label>
            <div className="flex gap-2">
              {PROJECT_COLORS.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setColor(c.key)}
                  title={c.label}
                  className={cn(
                    "flex h-7 w-7 items-center justify-center rounded-full text-white shadow-sm transition-transform hover:scale-110",
                    c.badge,
                    color === c.key && "ring-2 ring-offset-2 ring-foreground/30",
                  )}
                >
                  {color === c.key && <Check className="h-4 w-4" />}
                </button>
              ))}
            </div>
          </div>

          {error instanceof ApiError && (
            <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5" /> {error.message}
            </p>
          )}

          <Button type="submit" disabled={submitting || !name.trim()}>
            {submitting ? "Saving…" : "Save"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
