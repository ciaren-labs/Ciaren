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
  it("lists registered models with versions, aliases, metrics, lineage and copy", async () => {
    renderPage();
    // Name appears in both the summary strip and the detail card.
    expect((await screen.findAllByText("iris-model")).length).toBeGreaterThan(0);
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getAllByText("0.9700").length).toBeGreaterThan(0);
    expect(screen.getByText("@production → v2")).toBeInTheDocument();
    // Lineage flow chip links back to the producing flow.
    const flowLink = screen.getAllByRole("link", { name: /Flow/i })[0];
    expect(flowLink).toHaveAttribute("href", "/flows/f1");
    // Copy buttons for the model URI + run id.
    expect(screen.getByText("URI")).toBeInTheDocument();
    expect(screen.getByText("run id")).toBeInTheDocument();
    // Alias editor offers adding a new alias.
    expect(screen.getByText("alias")).toBeInTheDocument();
  });

  it("shows the experiments leaderboard ranked with best metric highlighted", async () => {
    renderPage();
    await screen.findAllByText("iris-model");
    await userEvent.click(screen.getByRole("tab", { name: /Experiments/i }));

    expect(await screen.findByText("flowframe")).toBeInTheDocument();
    expect(screen.getByText("run-r2")).toBeInTheDocument();
    // model type shows in both the summary header and the leaderboard row.
    expect(screen.getAllByText("random_forest_classifier").length).toBeGreaterThan(0);
    // Best accuracy (0.97) is highlighted somewhere (summary + leaderboard cell).
    const best = screen.getAllByText("0.9700");
    expect(best.some((el) => el.className.includes("text-emerald-600"))).toBe(true);
  });
});
