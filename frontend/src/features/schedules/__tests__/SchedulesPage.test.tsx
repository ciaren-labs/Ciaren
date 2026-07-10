import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function makeSchedule(id: string, name: string, flowId: string) {
  return {
    id,
    flow_id: flowId,
    name,
    description: null,
    cron: "0 * * * *",
    timezone: "UTC",
    engine: null,
    is_enabled: true,
    catch_up: false,
    max_retries: 0,
    retry_delay_seconds: 60,
    run_timeout_seconds: null,
    next_run_at: "2026-07-10T00:00:00+00:00",
    last_fired_at: null,
    last_run_id: null,
    last_status: null,
    consecutive_failures: 0,
    retry_count: 0,
    disabled_reason: null,
    parameters: null,
    created_at: "2026-06-01T00:00:00+00:00",
    updated_at: "2026-06-01T00:00:00+00:00",
  };
}

const SCHEDULE_A = makeSchedule("s1", "Nightly ETL run", "f1");
const SCHEDULE_B = makeSchedule("s2", "Weekly report run", "f2");

const resolvers = new Map<string, (run: { id: string }) => void>();
const rejecters = new Map<string, (err: Error) => void>();

vi.mock("@/features/schedules/api", () => ({
  schedulesApi: {
    list: vi.fn(() => Promise.resolve([SCHEDULE_A, SCHEDULE_B])),
    runNow: vi.fn(
      (id: string) =>
        new Promise((resolve, reject) => {
          resolvers.set(id, resolve);
          rejecters.set(id, reject);
        }),
    ),
  },
}));
vi.mock("@/features/flows/api", () => ({
  flowsApi: {
    list: vi.fn(() =>
      Promise.resolve([
        { id: "f1", name: "ETL Flow", project_id: "p1", graph_json: { nodes: [], edges: [] }, is_disabled: false, created_at: "", updated_at: "", last_run_at: null },
        { id: "f2", name: "Report Flow", project_id: "p1", graph_json: { nodes: [], edges: [] }, is_disabled: false, created_at: "", updated_at: "", last_run_at: null },
      ]),
    ),
  },
}));
vi.mock("@/features/projects/api", () => ({
  projectsApi: { list: vi.fn(() => Promise.resolve([{ id: "p1", name: "Default", color: "emerald" }])) },
}));

import { SchedulesPage } from "../SchedulesPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SchedulesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const RUN_NOW_TITLE = "Run now";

describe("SchedulesPage run-now action", () => {
  afterEach(() => {
    resolvers.clear();
    rejecters.clear();
    vi.clearAllMocks();
  });

  it("disables the schedule's row while its run-now request is in flight, then re-enables it", async () => {
    const { schedulesApi } = await import("@/features/schedules/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL run");
    const [runBtn] = screen.getAllByTitle(RUN_NOW_TITLE);
    await user.click(runBtn);

    expect(runBtn).toBeDisabled();
    expect(schedulesApi.runNow).toHaveBeenCalledTimes(1);

    resolvers.get("s1")?.({ id: "run1" });
    await waitFor(() => expect(runBtn).not.toBeDisabled());
  });

  it("keeps each row's pending state independent when two schedules are run concurrently", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL run");
    const [runBtnA, runBtnB] = screen.getAllByTitle(RUN_NOW_TITLE);

    await user.click(runBtnA);
    expect(runBtnA).toBeDisabled();

    await user.click(runBtnB);
    expect(runBtnB).toBeDisabled();
    // The bug this guards against: A's row silently re-enabling once B starts,
    // which a single shared mutation instance's isPending/variables would do.
    expect(runBtnA).toBeDisabled();

    resolvers.get("s2")?.({ id: "run2" });
    await waitFor(() => expect(runBtnB).not.toBeDisabled());
    expect(runBtnA).toBeDisabled();

    resolvers.get("s1")?.({ id: "run1" });
    await waitFor(() => expect(runBtnA).not.toBeDisabled());
  });

  it("ignores a second click on the same schedule while its own run-now request is still pending", async () => {
    const { schedulesApi } = await import("@/features/schedules/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL run");
    const [runBtn] = screen.getAllByTitle(RUN_NOW_TITLE);

    await user.click(runBtn);
    expect(runBtn).toBeDisabled();
    await user.click(runBtn);

    expect(schedulesApi.runNow).toHaveBeenCalledTimes(1);

    resolvers.get("s1")?.({ id: "run1" });
    await waitFor(() => expect(runBtn).not.toBeDisabled());
  });

  it("re-enables a row whose run-now request fails, independently of a concurrent successful one", async () => {
    renderPage();

    await screen.findByText("Nightly ETL run");
    const [runBtnA, runBtnB] = screen.getAllByTitle(RUN_NOW_TITLE);

    await userEvent.setup().click(runBtnA);
    await userEvent.setup().click(runBtnB);
    expect(runBtnA).toBeDisabled();
    expect(runBtnB).toBeDisabled();

    rejecters.get("s1")?.(new Error("boom"));
    await waitFor(() => expect(runBtnA).not.toBeDisabled());
    expect(runBtnB).toBeDisabled();

    resolvers.get("s2")?.({ id: "run2" });
    await waitFor(() => expect(runBtnB).not.toBeDisabled());
  });
});
