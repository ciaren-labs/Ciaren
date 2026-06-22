import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import {
  useCreateFlow,
  useDeleteFlow,
  useFlows,
} from "./hooks";
import {
  flowFormSchema,
  type FlowFormValues,
} from "@/lib/validators";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

export function FlowListPage() {
  const { data: flows, isLoading } = useFlows();
  const createFlow = useCreateFlow();
  const deleteFlow = useDeleteFlow();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FlowFormValues>({
    defaultValues: { name: "", description: "" },
  });

  const onCreate = handleSubmit((values) => {
    const parsed = flowFormSchema.safeParse(values);
    if (!parsed.success) return;
    createFlow.mutate(
      {
        name: values.name,
        description: values.description,
        graph_json: { nodes: [], edges: [] },
      },
      {
        onSuccess: (flow) => {
          reset();
          setOpen(false);
          navigate(`/flows/${flow.id}`);
        },
      },
    );
  });

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Flows</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>New flow</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create flow</DialogTitle>
            </DialogHeader>
            <form onSubmit={onCreate} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <Label>Name</Label>
                <Input {...register("name")} placeholder="My ETL flow" />
                {errors.name && (
                  <p className="text-[11px] text-destructive">
                    {errors.name.message}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label>Description</Label>
                <Textarea {...register("description")} />
              </div>
              <Button type="submit" disabled={createFlow.isPending}>
                {createFlow.isPending ? "Creating…" : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(flows ?? []).map((flow) => (
          <Card key={flow.id}>
            <CardHeader>
              <CardTitle className="text-base">{flow.name}</CardTitle>
              <CardDescription>
                {flow.description || "No description"}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              {flow.graph_json?.nodes.length ?? 0} nodes
            </CardContent>
            <CardFooter className="gap-2">
              <Button
                size="sm"
                onClick={() => navigate(`/flows/${flow.id}`)}
              >
                Open
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
                  if (confirm(`Delete flow "${flow.name}"?`)) {
                    deleteFlow.mutate(flow.id);
                  }
                }}
              >
                Delete
              </Button>
            </CardFooter>
          </Card>
        ))}
        {flows && flows.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No flows yet. Create one to start building.
          </p>
        )}
      </div>
    </div>
  );
}
