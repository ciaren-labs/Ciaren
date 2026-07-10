import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function makeFlow(id: string, name: string) {
  return {
    id,
    name,
    description: "",
    project_id: "p1",
    graph_json: { nodes: [], edges: [] },
    is_disabled: false,
    created_at: "2026-06-01T00:00:00+00:00",
    updated_at: "2026-06-01T00:00:00+00:00",
    last_run_at: null,
  };
}

const FLOW_A = makeFlow("f1", "Nightly ETL");
const FLOW_B = makeFlow("f2", "Weekly Report");

const resolvers = new Map<string, (flow: ReturnType<typeof makeFlow>) => void>();
const rejecters = new Map<string, (err: Error) => void>();

vi.mock("@/features/flows/api", () => ({
  flowsApi: {
    list: vi.fn(() => Promise.resolve([FLOW_A, FLOW_B])),
    duplicate: vi.fn(
      (id: string) =>
        new Promise((resolve, reject) => {
          resolvers.set(id, resolve);
          rejecters.set(id, reject);
        }),
    ),
  },
}));
vi.mock("@/features/projects/api", () => ({
  projectsApi: { list: vi.fn(() => Promise.resolve([{ id: "p1", name: "Default", color: "emerald" }])) },
}));
vi.mock("@/features/schedules/api", () => ({
  schedulesApi: { list: vi.fn(() => Promise.resolve([])) },
}));

import { FlowListPage } from "../FlowListPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FlowListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const DUPLICATE_TITLE = "Duplicate flow (graph, parameters and engine — not schedules or history)";

describe("FlowListPage duplicate action", () => {
  afterEach(() => {
    resolvers.clear();
    rejecters.clear();
    vi.clearAllMocks();
  });

  it("disables the duplicated flow's row while the request is in flight, then re-enables it", async () => {
    const { flowsApi } = await import("@/features/flows/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [duplicateBtn] = screen.getAllByTitle(DUPLICATE_TITLE);
    await user.click(duplicateBtn);

    expect(duplicateBtn).toBeDisabled();
    expect(flowsApi.duplicate).toHaveBeenCalledTimes(1);

    resolvers.get("f1")?.(makeFlow("f3", "Nightly ETL (copy)"));

    await waitFor(() => expect(duplicateBtn).not.toBeDisabled());
  });

  it("keeps each row's pending state independent when two different flows are duplicated concurrently", async () => {
    const { flowsApi } = await import("@/features/flows/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [duplicateBtnA, duplicateBtnB] = screen.getAllByTitle(DUPLICATE_TITLE);

    // Start duplicating flow A, then — while A is still in flight — start
    // duplicating flow B. A single shared mutation instance would previously
    // make A's row look "finished" the moment B's request started, since
    // isPending/variables reflect only the most recently invoked call.
    await user.click(duplicateBtnA);
    expect(duplicateBtnA).toBeDisabled();

    await user.click(duplicateBtnB);
    expect(duplicateBtnB).toBeDisabled();
    // The bug this guards against: A's row silently re-enabling once B starts.
    expect(duplicateBtnA).toBeDisabled();

    resolvers.get("f2")?.(makeFlow("f4", "Weekly Report (copy)"));
    await waitFor(() => expect(duplicateBtnB).not.toBeDisabled());
    // B finishing must not affect A, which is still in flight.
    expect(duplicateBtnA).toBeDisabled();

    resolvers.get("f1")?.(makeFlow("f3", "Nightly ETL (copy)"));
    await waitFor(() => expect(duplicateBtnA).not.toBeDisabled());

    expect(flowsApi.duplicate).toHaveBeenCalledTimes(2);
    expect(flowsApi.duplicate).toHaveBeenCalledWith("f1");
    expect(flowsApi.duplicate).toHaveBeenCalledWith("f2");
  });

  it("ignores a second click on the same flow while its own duplicate request is still pending", async () => {
    const { flowsApi } = await import("@/features/flows/api");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Nightly ETL");
    const [duplicateBtn] = screen.getAllByTitle(DUPLICATE_TITLE);

    await user.click(duplicateBtn);
    expect(duplicateBtn).toBeDisabled();
    // The disabled attribute is what actually blocks this second click at the
    // DOM level once React has re-rendered; the duplicatingIds guard in
    // handleDuplicate exists as a belt-and-braces check for the same-tick
    // window before that re-render commits.
    await user.click(duplicateBtn);

    expect(flowsApi.duplicate).toHaveBeenCalledTimes(1);

    resolvers.get("f1")?.(makeFlow("f3", "Nightly ETL (copy)"));
    await waitFor(() => expect(duplicateBtn).not.toBeDisabled());
  });

  it("re-enables a row whose duplicate request fails, independently of a concurrent successful one", async () => {
    renderPage();

    await screen.findByText("Nightly ETL");
    const [duplicateBtnA, duplicateBtnB] = screen.getAllByTitle(DUPLICATE_TITLE);

    await userEvent.setup().click(duplicateBtnA);
    await userEvent.setup().click(duplicateBtnB);
    expect(duplicateBtnA).toBeDisabled();
    expect(duplicateBtnB).toBeDisabled();

    // A fails; B is still in flight and must be unaffected.
    rejecters.get("f1")?.(new Error("boom"));
    await waitFor(() => expect(duplicateBtnA).not.toBeDisabled());
    expect(duplicateBtnB).toBeDisabled();

    resolvers.get("f2")?.(makeFlow("f4", "Weekly Report (copy)"));
    await waitFor(() => expect(duplicateBtnB).not.toBeDisabled());
  });
});
