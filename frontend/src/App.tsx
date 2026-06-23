import { Routes, Route } from "react-router-dom";
import { AppHeader } from "@/components/layout/AppHeader";
import { AppFooter } from "@/components/layout/AppFooter";
import { LandingPage } from "@/features/landing/LandingPage";
import { FlowListPage } from "@/features/flows/FlowListPage";
import { FlowEditorPage } from "@/features/flows/FlowEditorPage";
import { DatasetsPage } from "@/features/datasets/DatasetsPage";
import { ConnectionsPage } from "@/features/connections/ConnectionsPage";
import { RunsPage } from "@/features/runs/RunsPage";
import { RunDetailPage } from "@/features/runs/RunDetailPage";
import { ModelsPage } from "@/features/models/ModelsPage";
import { SchedulesPage } from "@/features/schedules/SchedulesPage";
import { ScheduleDetailPage } from "@/features/schedules/ScheduleDetailPage";
import { ProjectsPage } from "@/features/projects/ProjectsPage";
import { ProjectDetailPage } from "@/features/projects/ProjectDetailPage";

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/flows" element={<FlowListPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/connections" element={<ConnectionsPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/schedules/:scheduleId" element={<ScheduleDetailPage />} />
          <Route path="/flows/:flowId" element={<FlowEditorPage />} />
        </Routes>
      </main>
      <AppFooter />
    </div>
  );
}
