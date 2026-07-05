import { lazy, Suspense, useEffect, type ComponentType } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster } from "@/components/ui/Toaster";
import { useThemeStore } from "@/stores/themeStore";
import { AppHeader } from "@/components/layout/AppHeader";
import { AppFooter } from "@/components/layout/AppFooter";
// The landing page is the first paint for new visitors, so keep it in the entry
// bundle. Every other route is code-split into its own chunk so the marketing page
// (and each first navigation) only loads the JS it needs — the flow editor, in
// particular, pulls in React Flow and all node config forms.
import { LandingPage } from "@/features/landing/LandingPage";

const named = <T, K extends keyof T>(loader: () => Promise<T>, key: K) =>
  lazy(() => loader().then((m) => ({ default: m[key] as unknown as ComponentType })));

const FlowListPage = named(() => import("@/features/flows/FlowListPage"), "FlowListPage");
const FlowEditorPage = named(() => import("@/features/flows/FlowEditorPage"), "FlowEditorPage");
const DatasetsPage = named(() => import("@/features/datasets/DatasetsPage"), "DatasetsPage");
const ConnectionsPage = named(() => import("@/features/connections/ConnectionsPage"), "ConnectionsPage");
const RunsPage = named(() => import("@/features/runs/RunsPage"), "RunsPage");
const RunDetailPage = named(() => import("@/features/runs/RunDetailPage"), "RunDetailPage");
const ModelsPage = named(() => import("@/features/models/ModelsPage"), "ModelsPage");
const SchedulesPage = named(() => import("@/features/schedules/SchedulesPage"), "SchedulesPage");
const ScheduleDetailPage = named(() => import("@/features/schedules/ScheduleDetailPage"), "ScheduleDetailPage");
const ProjectsPage = named(() => import("@/features/projects/ProjectsPage"), "ProjectsPage");
const ProjectDetailPage = named(() => import("@/features/projects/ProjectDetailPage"), "ProjectDetailPage");
const PluginsPage = named(() => import("@/features/plugins/PluginsPage"), "PluginsPage");
const SettingsPage = named(() => import("@/features/settings/SettingsPage"), "SettingsPage");

function RouteFallback() {
  return (
    <div className="flex h-full items-center justify-center py-24">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

export default function App() {
  // Reset the error boundary on navigation so an error on one page doesn't
  // strand the user — moving to another route clears the fallback.
  const location = useLocation();
  const theme = useThemeStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <main className="min-h-0 flex-1 overflow-y-auto">
        <ErrorBoundary resetKey={location.pathname}>
        <Suspense fallback={<RouteFallback />}>
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
          <Route path="/plugins" element={<PluginsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/flows/:flowId" element={<FlowEditorPage />} />
        </Routes>
        </Suspense>
        </ErrorBoundary>
      </main>
      <AppFooter />
      <Toaster />
    </div>
  );
}
