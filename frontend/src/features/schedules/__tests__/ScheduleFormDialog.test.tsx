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

  it("uses live parameterSpecs (editor) even when the saved flow has none", async () => {
    // Saved flow has no parameters; the editor passes just-declared specs.
    const noParamFlow = { ...FLOW, graph_json: { nodes: [], edges: [] } };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const body = String(url).includes("/api/flows") ? [noParamFlow] : [];
        return { ok: true, status: 200, json: async () => body };
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ScheduleFormDialog
          open
          onOpenChange={() => {}}
          lockedFlowId="f1"
          parameterSpecs={[{ name: "keep", type: "integer", default: 2 }]}
          submitting={false}
          error={null}
          onSubmit={vi.fn()}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByLabelText("value-keep")).toHaveValue("2");
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

const NO_PARAM_FLOW = { ...FLOW, graph_json: { nodes: [], edges: [] } };

function stubFlow(flow: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = String(url).includes("/api/flows") ? [flow] : [];
      return { ok: true, status: 200, json: async () => body };
    }),
  );
}

describe("ScheduleFormDialog run timeout", () => {
  it("submits the run timeout entered in Advanced options", async () => {
    stubFlow(NO_PARAM_FLOW);
    const user = userEvent.setup();
    const onSubmit = renderForm();

    await screen.findByRole("button", { name: /create schedule/i });
    await user.click(screen.getByRole("button", { name: /advanced options/i }));
    await user.type(screen.getByLabelText("run-timeout-seconds"), "120");
    await user.click(screen.getByRole("button", { name: /create schedule/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][1].run_timeout_seconds).toBe(120);
  });

  // 0 is a distinct, meaningful value (no limit) — it must survive as 0, not be
  // dropped as "empty".
  it("submits 0 (no limit) distinctly from a blank server-default", async () => {
    stubFlow(NO_PARAM_FLOW);
    const user = userEvent.setup();
    const onSubmit = renderForm();

    await screen.findByRole("button", { name: /create schedule/i });
    await user.click(screen.getByRole("button", { name: /advanced options/i }));
    await user.type(screen.getByLabelText("run-timeout-seconds"), "0");
    await user.click(screen.getByRole("button", { name: /create schedule/i }));

    expect(onSubmit.mock.calls[0][1].run_timeout_seconds).toBe(0);
  });

  it("omits the run timeout when left blank (falls back to the server default)", async () => {
    stubFlow(NO_PARAM_FLOW);
    const user = userEvent.setup();
    const onSubmit = renderForm();

    await user.click(await screen.findByRole("button", { name: /create schedule/i }));

    expect(onSubmit.mock.calls[0][1].run_timeout_seconds).toBeUndefined();
  });

  it("seeds and opens Advanced from an existing schedule's timeout (edit)", async () => {
    stubFlow(NO_PARAM_FLOW);
    const schedule = {
      id: "s1",
      flow_id: "f1",
      name: "Nightly",
      description: null,
      cron: "0 * * * *",
      timezone: "UTC",
      engine: null,
      is_enabled: true,
      catch_up: false,
      max_retries: 0,
      retry_delay_seconds: 60,
      run_timeout_seconds: 90,
      next_run_at: null,
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
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ScheduleFormDialog
          open
          onOpenChange={() => {}}
          schedule={schedule}
          submitting={false}
          error={null}
          onSubmit={vi.fn()}
        />
      </QueryClientProvider>,
    );

    // Advanced auto-expands because a non-default timeout is set, and the field
    // is seeded with the saved value.
    expect(await screen.findByLabelText("run-timeout-seconds")).toHaveValue(90);
  });
});
