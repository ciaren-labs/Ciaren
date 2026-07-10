import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const clearAliasResolvers = new Map<string, () => void>();

vi.mock("@/features/transformations/api", () => ({
  transformationsApi: { list: vi.fn(() => Promise.resolve(["mlTrainClassifier", "dropNulls"])) },
}));
vi.mock("@/features/flows/api", () => ({
  flowsApi: {
    list: vi.fn(() =>
      Promise.resolve([
        { id: "f1", name: "Iris Quick Classifier", project_id: "p1", graph_json: { nodes: [], edges: [] }, is_disabled: false, created_at: "", updated_at: "", last_run_at: null },
      ]),
    ),
  },
}));
vi.mock("@/features/projects/api", () => ({
  projectsApi: { list: vi.fn(() => Promise.resolve([{ id: "p1", name: "Demo", color: "emerald" }])) },
}));
vi.mock("@/features/models/api", () => ({
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
              aliases: ["production", "champion"],
              created: "2026-06-23T10:00:00+00:00",
              metrics: { train_accuracy: 0.97 },
              lineage: { flow_id: "f1", run_id: "run9", dataset_ids: ["d1"] },
            },
          ],
        },
      ]),
    ),
    setAlias: vi.fn(() => Promise.resolve({ model: "iris-model", alias: "x", version: "2" })),
    clearAlias: vi.fn(
      (model: string, alias: string) =>
        new Promise<{ model: string; alias: string }>((resolve) => {
          clearAliasResolvers.set(alias, () => resolve({ model, alias }));
        }),
    ),
    allExperiments: vi.fn(() =>
      Promise.resolve([
        { experiment_id: "1", name: "ciaren", lifecycle_stage: "active", last_run: null },
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
    // Segmented by project.
    expect(screen.getByText("Demo")).toBeInTheDocument();
    // Lineage flow chip shows the flow name and links back to the producing flow.
    const flowLink = screen.getAllByRole("link").find((l) => l.getAttribute("href") === "/flows/f1");
    expect(flowLink).toBeDefined();
    expect(flowLink).toHaveTextContent("Iris Quick Classifier");
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

    expect(await screen.findByText("ciaren")).toBeInTheDocument();
    expect(screen.getByText("run-r2")).toBeInTheDocument();
    // model type shows in both the summary header and the leaderboard row.
    expect(screen.getAllByText("random_forest_classifier").length).toBeGreaterThan(0);
    // Best accuracy (0.97) is highlighted somewhere (summary + leaderboard cell).
    const best = screen.getAllByText("0.9700");
    expect(best.some((el) => el.className.includes("text-emerald-600"))).toBe(true);
  });
});

describe("ModelsPage alias clearing", () => {
  afterEach(() => {
    clearAliasResolvers.clear();
    vi.clearAllMocks();
  });

  it("disables only the cleared alias's own button when a version has multiple aliases", async () => {
    const { mlApi } = await import("@/features/models/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findAllByText("iris-model");
    const prodClear = screen.getByTitle("Clear @production");
    const championClear = screen.getByTitle("Clear @champion");

    await user.click(prodClear);

    expect(prodClear).toBeDisabled();
    // The bug this guards against: clearAlias.isPending applied to every
    // alias chip on the row would also disable @champion's button.
    expect(championClear).not.toBeDisabled();
    expect(mlApi.clearAlias).toHaveBeenCalledTimes(1);
    expect(mlApi.clearAlias).toHaveBeenCalledWith("iris-model", "production");

    clearAliasResolvers.get("production")?.();
    await waitFor(() => expect(prodClear).not.toBeDisabled());
  });

  it("keeps two aliases' clearing state independent when cleared concurrently", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findAllByText("iris-model");
    const prodClear = screen.getByTitle("Clear @production");
    const championClear = screen.getByTitle("Clear @champion");

    await user.click(prodClear);
    await user.click(championClear);
    expect(prodClear).toBeDisabled();
    expect(championClear).toBeDisabled();

    clearAliasResolvers.get("champion")?.();
    await waitFor(() => expect(championClear).not.toBeDisabled());
    expect(prodClear).toBeDisabled();

    clearAliasResolvers.get("production")?.();
    await waitFor(() => expect(prodClear).not.toBeDisabled());
  });
});
