import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

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

vi.mock("@/lib/api", () => ({
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
  flowsApi: { list: vi.fn(() => Promise.resolve([])) },
  datasetsApi: { list: vi.fn(() => Promise.resolve([])) },
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
    const { runsApi } = await import("@/lib/api");
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
    const { runsApi } = await import("@/lib/api");
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
    const { runsApi } = await import("@/lib/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [retryBtnA] = screen.getAllByTitle(RETRY_TITLE);
    await user.click(retryBtnA);

    expect(retryBtnA).not.toBeDisabled();
    expect(runsApi.retry).not.toHaveBeenCalled();
  });
});
