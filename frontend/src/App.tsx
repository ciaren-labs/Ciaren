import { Routes, Route } from "react-router-dom";
import { AppHeader } from "@/components/layout/AppHeader";
import { FlowListPage } from "@/features/flows/FlowListPage";
import { FlowEditorPage } from "@/features/flows/FlowEditorPage";
import { DatasetsPage } from "@/features/datasets/DatasetsPage";

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <main className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<FlowListPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/flows/:flowId" element={<FlowEditorPage />} />
        </Routes>
      </main>
    </div>
  );
}
