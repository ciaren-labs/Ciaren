import { Routes, Route } from "react-router-dom";
import { AppHeader } from "@/components/layout/AppHeader";
import { LandingPage } from "@/features/landing/LandingPage";
import { FlowListPage } from "@/features/flows/FlowListPage";
import { FlowEditorPage } from "@/features/flows/FlowEditorPage";
import { DatasetsPage } from "@/features/datasets/DatasetsPage";
import { RunsPage } from "@/features/runs/RunsPage";
import { RunDetailPage } from "@/features/runs/RunDetailPage";
import { ProjectsPage } from "@/features/projects/ProjectsPage";
import { ProjectDetailPage } from "@/features/projects/ProjectDetailPage";

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <main className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/flows" element={<FlowListPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/flows/:flowId" element={<FlowEditorPage />} />
        </Routes>
      </main>
    </div>
  );
}
