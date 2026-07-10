import { useMemo } from "react";
import { BrainCircuit, FlaskConical, Tag } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useFlows } from "@/features/flows/hooks";
import { useProjects } from "@/features/projects/hooks";
import { useMlEnabled } from "./hooks";
import { RegisteredModelsTab } from "./components/RegisteredModelsTab";
import { ExperimentsTab } from "./components/ExperimentsTab";

export function ModelsPage() {
  const mlEnabled = useMlEnabled();
  const { data: flows } = useFlows();
  const { data: projects } = useProjects();
  const flowName = useMemo(() => new Map((flows ?? []).map((f) => [f.id, f.name])), [flows]);
  const flowProject = useMemo(
    () => new Map((flows ?? []).map((f) => [f.id, f.project_id])),
    [flows],
  );
  const projectName = useMemo(() => new Map((projects ?? []).map((p) => [p.id, p.name])), [projects]);
  const projectColorById = useMemo(
    () => new Map((projects ?? []).map((p) => [p.id, p.color])),
    [projects],
  );

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <BrainCircuit className="h-6 w-6 text-purple-600" /> ML Models
        </h1>
        <p className="text-sm text-muted-foreground">
          Models and experiments tracked with MLflow — with links back to the
          flows and runs that produced them.
        </p>
      </div>

      {!mlEnabled ? (
        <MlDisabledNotice />
      ) : (
        <Tabs defaultValue="models">
          <TabsList>
            <TabsTrigger value="models">
              <Tag className="mr-1.5 h-4 w-4" /> Registered Models
            </TabsTrigger>
            <TabsTrigger value="experiments">
              <FlaskConical className="mr-1.5 h-4 w-4" /> Experiments
            </TabsTrigger>
          </TabsList>
          <TabsContent value="models">
            <RegisteredModelsTab
              flowName={flowName}
              flowProject={flowProject}
              projectName={projectName}
              projectColorById={projectColorById}
            />
          </TabsContent>
          <TabsContent value="experiments">
            <ExperimentsTab flowName={flowName} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function MlDisabledNotice() {
  return (
    <div className="rounded-lg border border-dashed border-border p-10 text-center">
      <BrainCircuit className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
      <p className="text-sm font-medium">Machine learning is disabled</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Set <code className="font-mono">CIAREN_ML_ENABLED=true</code> to train and track models.
        If it's already set, run <code className="font-mono">ciaren check</code> — this usually
        means scikit-learn, MLflow, or joblib failed to import.
      </p>
    </div>
  );
}
