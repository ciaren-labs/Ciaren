import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScheduleFormDialog } from "../ScheduleFormDialog";

const FLOW = {
  id: "f1",
  name: "Param flow",
  description: null,
  project_id: "p1",
  is_disabled: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  last_run_at: null,
  graph_json: {
    nodes: [],
    edges: [],
    parameters: [
      { name: "keep", type: "integer", default: 2 },
      { name: "label", type: "string" }, // required
    ],
  },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = String(url);
      const body = path.includes("/api/flows") ? [FLOW] : []; // projects → []
      return { ok: true, status: 200, json: async () => body };
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

function renderForm(onSubmit = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ScheduleFormDialog
        open
        onOpenChange={() => {}}
        lockedFlowId="f1"
        submitting={false}
        error={null}
        onSubmit={onSubmit}
      />
    </QueryClientProvider>,
  );
  return onSubmit;
}

describe("ScheduleFormDialog parameter overrides", () => {
  it("shows the flow's parameters, defaulting and requiring as declared", async () => {
    renderForm();
    const keep = await screen.findByLabelText("value-keep");
    expect(keep).toHaveValue("2");
    expect(screen.getByLabelText("value-label")).toHaveValue("");
    // Required `label` empty → cannot create yet.
    expect(screen.getByRole("button", { name: /create schedule/i })).toBeDisabled();
  });

  it("submits coerced parameter overrides", async () => {
    const user = userEvent.setup();
    const onSubmit = renderForm();
    await screen.findByLabelText("value-keep");

    await user.type(screen.getByLabelText("value-label"), "june");
    const create = screen.getByRole("button", { name: /create schedule/i });
    await waitFor(() => expect(create).toBeEnabled());
    await user.click(create);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const [flowId, body] = onSubmit.mock.calls[0];
    expect(flowId).toBe("f1");
    expect(body.parameters).toEqual({ keep: 2, label: "june" });
  });
});
