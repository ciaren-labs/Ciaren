import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function makeDataset(id: string, name: string) {
  return {
    id,
    name,
    source_type: "csv" as const,
    dataset_kind: "input" as const,
    project_id: "p1",
    is_disabled: false,
    latest_version: 1,
    version_count: 1,
    column_schema: [],
    data_sample: null,
    column_profile: null,
    created_at: "2026-06-01T00:00:00+00:00",
    updated_at: "2026-06-01T00:00:00+00:00",
  };
}

function makeRun(id: string, flowId: string, flowName: string) {
  return {
    id,
    flow_id: flowId,
    flow_name: flowName,
    project_id: "p1",
    input_dataset_id: null,
    input_datasets: null,
    status: "failed" as const,
    engine: "pandas",
    trigger: "manual" as const,
    schedule_id: null,
    output_location: null,
    started_at: "2026-07-01T00:00:00+00:00",
    finished_at: "2026-07-01T00:01:00+00:00",
    created_at: "2026-07-01T00:00:00+00:00",
  };
}

const RUN_A = makeRun("r1", "f1", "Nightly ETL");
const RUN_B = makeRun("r2", "f2", "Weekly Report");

const resolvers = new Map<string, (run: { id: string }) => void>();
const rejecters = new Map<string, (err: Error) => void>();

vi.mock("@/features/runs/api", () => ({
  runsApi: {
    list: vi.fn(() => Promise.resolve([RUN_A, RUN_B])),
    retry: vi.fn(
      (id: string) =>
        new Promise((resolve, reject) => {
          resolvers.set(id, resolve);
          rejecters.set(id, reject);
        }),
    ),
  },
}));
vi.mock("@/features/flows/api", () => ({
  flowsApi: { list: vi.fn(() => Promise.resolve([])) },
}));
vi.mock("@/features/datasets/api", () => ({
  datasetsApi: { list: vi.fn(() => Promise.resolve([])) },
}));
vi.mock("@/features/projects/api", () => ({
  projectsApi: { list: vi.fn(() => Promise.resolve([{ id: "p1", name: "Default", color: "emerald" }])) },
}));

import { RunsPage } from "../RunsPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RunsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const RETRY_TITLE = "Re-run the flow with the same config (creates a new run)";

describe("RunsPage retry action", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    resolvers.clear();
    rejecters.clear();
    vi.clearAllMocks();
  });

  it("disables only the retried run's button, not every failed run's button", async () => {
    const { runsApi } = await import("@/features/runs/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [retryBtnA, retryBtnB] = screen.getAllByTitle(RETRY_TITLE);
    await user.click(retryBtnA);

    expect(retryBtnA).toBeDisabled();
    // The bug this guards against: retry.isPending applied to every row would
    // also disable B's button even though only A is retrying.
    expect(retryBtnB).not.toBeDisabled();
    expect(runsApi.retry).toHaveBeenCalledTimes(1);

    resolvers.get("r1")?.({ id: "new-run-1" });
    await waitFor(() => expect(retryBtnA).not.toBeDisabled());
  });

  it("keeps each row's retrying state independent when two runs are retried concurrently", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [retryBtnA, retryBtnB] = screen.getAllByTitle(RETRY_TITLE);

    await user.click(retryBtnA);
    await user.click(retryBtnB);
    expect(retryBtnA).toBeDisabled();
    expect(retryBtnB).toBeDisabled();

    resolvers.get("r2")?.({ id: "new-run-2" });
    await waitFor(() => expect(retryBtnB).not.toBeDisabled());
    expect(retryBtnA).toBeDisabled();

    resolvers.get("r1")?.({ id: "new-run-1" });
    await waitFor(() => expect(retryBtnA).not.toBeDisabled());
  });

  it("ignores a second click on the same run while its own retry is still pending", async () => {
    const { runsApi } = await import("@/features/runs/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [retryBtnA] = screen.getAllByTitle(RETRY_TITLE);

    await user.click(retryBtnA);
    expect(retryBtnA).toBeDisabled();
    await user.click(retryBtnA);

    expect(runsApi.retry).toHaveBeenCalledTimes(1);

    resolvers.get("r1")?.({ id: "new-run-1" });
    await waitFor(() => expect(retryBtnA).not.toBeDisabled());
  });

  it("re-enables a row whose retry fails, independently of a concurrent successful one", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [retryBtnA, retryBtnB] = screen.getAllByTitle(RETRY_TITLE);

    await user.click(retryBtnA);
    await user.click(retryBtnB);

    rejecters.get("r1")?.(new Error("boom"));
    await waitFor(() => expect(retryBtnA).not.toBeDisabled());
    expect(retryBtnB).toBeDisabled();

    resolvers.get("r2")?.({ id: "new-run-2" });
    await waitFor(() => expect(retryBtnB).not.toBeDisabled());
  });

  it("does not start a retry when the confirmation is declined", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);
    const { runsApi } = await import("@/features/runs/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [retryBtnA] = screen.getAllByTitle(RETRY_TITLE);
    await user.click(retryBtnA);

    expect(retryBtnA).not.toBeDisabled();
    expect(runsApi.retry).not.toHaveBeenCalled();
  });
});

describe("RunsPage dataset label", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("falls back to the name snapshotted on the run when the dataset is no longer in the live list", async () => {
    // Regression: a purged dataset drops out of datasetsApi.list(), so the old
    // id-only lookup rendered "—" for every run that used it, even though the
    // run itself recorded the dataset's name at run time.
    const { runsApi } = await import("@/features/runs/api");
    const { datasetsApi } = await import("@/features/datasets/api");
    vi.mocked(runsApi.list).mockResolvedValueOnce([
      {
        ...RUN_A,
        input_datasets: [{ dataset_id: "purged-ds", version_number: 3, dataset_name: "Purged Dataset" }],
      },
    ]);
    vi.mocked(datasetsApi.list).mockResolvedValueOnce([]); // dataset no longer exists

    renderPage();

    expect(await screen.findByText("Purged Dataset")).toBeInTheDocument();
  });

  it("prefers the live dataset name over the run's snapshot (picks up renames)", async () => {
    const { runsApi } = await import("@/features/runs/api");
    const { datasetsApi } = await import("@/features/datasets/api");
    vi.mocked(runsApi.list).mockResolvedValueOnce([
      {
        ...RUN_A,
        input_datasets: [{ dataset_id: "ds1", version_number: 1, dataset_name: "Old Name" }],
      },
    ]);
    vi.mocked(datasetsApi.list).mockResolvedValueOnce([makeDataset("ds1", "New Name")]);

    renderPage();

    expect(await screen.findByText("New Name")).toBeInTheDocument();
    expect(screen.queryByText("Old Name")).not.toBeInTheDocument();
  });
});
