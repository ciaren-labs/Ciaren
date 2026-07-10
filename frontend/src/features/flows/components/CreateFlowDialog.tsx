import { useState } from "react";
import { useForm } from "react-hook-form";
import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { flowFormSchema, type FlowFormValues } from "@/lib/validators";
import { FLOW_TEMPLATES, buildTemplateGraph } from "@/lib/flowTemplates";
import { cn } from "@/lib/utils";
import type { Project } from "@/features/projects/types";
import type { GraphJson } from "@/features/flows/types";

export function CreateFlowDialog({
  open,
  onOpenChange,
  projects,
  defaultProjectId,
  isPending,
  trigger,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projects: Project[];
  defaultProjectId: string;
  isPending: boolean;
  trigger: React.ReactNode;
  onCreate: (
    values: { name: string; description?: string; projectId: string; graph: GraphJson },
    onSuccess: () => void,
  ) => void;
}) {
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState(defaultProjectId);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FlowFormValues>({ defaultValues: { name: "", description: "" } });

  const handleOpenChange = (o: boolean) => {
    onOpenChange(o);
    if (o) {
      setProjectId(defaultProjectId);
    } else {
      setSelectedTemplateId(null);
    }
  };

  const onSubmit = handleSubmit((values) => {
    const parsed = flowFormSchema.safeParse(values);
    if (!parsed.success) {
      const issue = parsed.error.issues.find((i) => i.path[0] === "name");
      if (issue) setError("name", { message: issue.message });
      return;
    }
    const template = FLOW_TEMPLATES.find((t) => t.id === selectedTemplateId);
    onCreate(
      {
        name: values.name,
        description: values.description,
        projectId,
        graph: template ? buildTemplateGraph(template) : { nodes: [], edges: [] },
      },
      () => {
        reset();
        setSelectedTemplateId(null);
      },
    );
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create flow</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label>Start from</Label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSelectedTemplateId(null)}
                className={cn(
                  "flex items-start gap-2 rounded-md border p-2.5 text-left transition-colors",
                  selectedTemplateId === null
                    ? "border-primary bg-accent"
                    : "border-input hover:bg-muted",
                )}
              >
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <span>
                  <span className="block text-xs font-medium">Blank flow</span>
                  <span className="block text-[11px] text-muted-foreground">
                    Start with an empty canvas.
                  </span>
                </span>
              </button>
              {FLOW_TEMPLATES.map((tpl) => {
                const Icon = tpl.icon;
                const active = selectedTemplateId === tpl.id;
                return (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => setSelectedTemplateId(tpl.id)}
                    className={cn(
                      "flex items-start gap-2 rounded-md border p-2.5 text-left transition-colors",
                      active ? "border-primary bg-accent" : "border-input hover:bg-muted",
                    )}
                  >
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <span>
                      <span className="block text-xs font-medium">{tpl.name}</span>
                      <span className="block text-[11px] text-muted-foreground">
                        {tpl.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label>Name</Label>
            <Input {...register("name")} placeholder="My ETL flow" />
            {errors.name && (
              <p className="text-[11px] text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <Label>Description</Label>
            <Textarea {...register("description")} />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Project</Label>
            <SearchableSelect
              value={projectId}
              onChange={setProjectId}
              allLabel="Default project"
              placeholder="Search projects…"
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
            />
          </div>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Creating…" : "Create"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
