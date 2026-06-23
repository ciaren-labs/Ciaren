import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/lib/api", () => ({
  transformationsApi: { list: vi.fn(() => Promise.resolve(["mlTrain", "dropNulls"])) },
  mlApi: {
    registeredModels: vi.fn(() =>
      Promise.resolve([
        {
          name: "iris-model",
          description: null,
          aliases: { production: "2" },
          last_updated: "2026-06-23T10:00:00+00:00",
          versions: [
            {
              version: "2",
              run_id: "r2",
              status: "READY",
              aliases: ["production"],
              created: "2026-06-23T10:00:00+00:00",
              metrics: { train_accuracy: 0.97 },
              lineage: { flow_id: "f1", run_id: "run9", dataset_ids: ["d1"] },
            },
          ],
        },
      ]),
    ),
    allExperiments: vi.fn(() =>
      Promise.resolve([
        { experiment_id: "1", name: "flowframe", lifecycle_stage: "active", last_run: null },
      ]),
    ),
    experimentRuns: vi.fn(() =>
      Promise.resolve([
        {
          run_id: "r2",
          run_name: "run-r2",
          status: "FINISHED",
          start_time: "2026-06-23T10:00:00+00:00",
          metrics: { train_accuracy: 0.97, train_rmse: 0.1 },
          params: { model_type: "random_forest_classifier" },
          lineage: { flow_id: "f1", run_id: "run9" },
        },
        {
          run_id: "r1",
          run_name: "run-r1",
          status: "FINISHED",
          start_time: "2026-06-23T09:00:00+00:00",
          metrics: { train_accuracy: 0.80, train_rmse: 0.3 },
          params: { model_type: "logistic_regression" },
          lineage: {},
        },
      ]),
    ),
  },
}));

import { ModelsPage } from "../ModelsPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ModelsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ModelsPage", () => {
  it("lists registered models with versions, aliases, metrics, and lineage links", async () => {
    renderPage();
    expect(await screen.findByText("iris-model")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("0.9700")).toBeInTheDocument();
    expect(screen.getByText("@production → v2")).toBeInTheDocument();
    // Lineage links point back to the flow and run that produced the version.
    const flowLink = screen.getByRole("link", { name: "flow" });
    expect(flowLink).toHaveAttribute("href", "/flows/f1");
  });

  it("shows the experiments leaderboard and highlights the best metric per column", async () => {
    renderPage();
    await screen.findByText("iris-model");
    await userEvent.click(screen.getByRole("tab", { name: /Experiments/i }));

    expect(await screen.findByText("flowframe")).toBeInTheDocument();
    // Both runs and their model types appear in the leaderboard.
    expect(screen.getByText("run-r2")).toBeInTheDocument();
    expect(screen.getByText("random_forest_classifier")).toBeInTheDocument();
    // Best accuracy (higher better) and best rmse (lower better) are highlighted.
    const bestAcc = screen.getByText("0.9700");
    const bestRmse = screen.getByText("0.1000");
    expect(bestAcc.className).toMatch(/text-emerald-600/);
    expect(bestRmse.className).toMatch(/text-emerald-600/);
  });
});
