import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { GraphJson } from "@/features/flows/types";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { AssistantPanel } from "../AssistantPanel";
import { Activity } from "../Activity";

type Call = { method: string; path: string; body: Record<string, unknown> | undefined };
type Handler = (call: Call) => unknown;

let calls: Call[] = [];
let routes: Record<string, Handler> = {};
const turn = (call: Call) => call.method === "POST" && call.path.endsWith("/turn");
const turns = () => calls.filter(turn);

function respond(body: unknown, status = 200) {
  return {
    ok: status < 400,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

const conflict = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 409, headers: { "content-type": "application/json" } });

beforeEach(() => {
  calls = [];
  routes = {
    "GET /api/assistant/status": () => ({ provider: "deepseek", state: "configured", model: "deepseek-chat" }),
  };
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const call: Call = {
        method: init.method ?? "GET",
        path: url.split("?")[0],
        body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
      };
      calls.push(call);
      const handler = routes[`${call.method} ${call.path}`];
      const result = handler ? await handler(call) : [];
      return result instanceof Response ? result : respond(result);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  useFlowEditorStore.setState({ dirty: false });
});

const base: GraphJson = {
  nodes: [
    { id: "i1", type: "fileInput", position: { x: 0, y: 0 }, data: { label: "Orders", config: { dataset_id: "d1", dataset_version: 1 } } },
    { id: "l1", type: "limitRows", position: { x: 200, y: 0 }, data: { label: "Limit", config: { n: 10 } } },
  ],
  edges: [{ id: "e1", source: "i1", target: "l1" }],
} as never;

const proposal = (extra: Record<string, unknown> = {}) => ({
  message: "Review the proposed canvas changes.",
  proposal: "a".repeat(32),
  delta: {
    added: [{ id: "s1", type: "sortRows", position: { x: 400, y: 0 }, data: { label: "Sort", config: { columns: ["amount"] } } }],
    changed: [{ ...base.nodes[1], data: { label: "Limit", config: { n: 100 } } }],
    connected: [{ id: "e2", source: "l1", target: "s1" }],
    disconnected: [],
  },
  ...extra,
});

const datasets = [
  {
    id: "d1",
    name: "orders",
    source_type: "csv",
    latest_version: 2,
    is_disabled: false,
    column_schema: [
      { name: "customer_id", type: "integer" },
      { name: "email", type: "string" },
      { name: "shipping_cost", type: "float" },
    ],
    column_profile: [{ name: "email", null_count: 3 }],
  },
  { id: "d2", name: "customers", source_type: "csv", latest_version: 1, is_disabled: false, column_schema: [{ name: "customer_id", type: "integer" }] },
  { id: "d3", name: "catalog", source_type: "csv", latest_version: 1, is_disabled: false, column_schema: [{ name: "sku", type: "string" }] },
];

function setup(
  options: {
    graph?: GraphJson;
    disabled?: boolean;
    datasets?: unknown[];
    save?: () => Promise<string | null>;
  } = {},
) {
  let canvas = options.graph ?? base;
  const restored = vi.fn();
  const save = vi.fn(options.save ?? (async () => null));
  const focusPalette = vi.fn();
  const saved = vi.fn((_: string, graph: GraphJson) => {
    canvas = graph;
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = (list: unknown[]) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReactFlowProvider>
          <TooltipProvider>
            <AssistantPanel
              flowId="f1"
              flowName="Orders"
              projectId="p1"
              revision="2026-01-01T00:00:00"
              disabled={options.disabled ?? false}
              datasets={list as never}
              validation={{ errors: [], warnings: [] } as never}
              restored={restored}
              current={() => canvas}
              saved={saved}
              save={save}
              focusPalette={focusPalette}
            />
          </TooltipProvider>
        </ReactFlowProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  const view = render(tree(options.datasets ?? datasets));
  return {
    restored,
    save,
    saved,
    focusPalette,
    canvas: () => canvas,
    rerender: (list: unknown[]) => view.rerender(tree(list)),
  };
}

async function openPanel() {
  fireEvent.click(screen.getByRole("button", { name: /^Assistant(, new reply)?$/ }));
  const panel = screen.getByRole("dialog", { name: /Flow assistant/ });
  const textarea = await within(panel).findByRole("textbox", { name: "Request" });
  return { panel, textarea };
}

async function ask(text: string, submit = "Create proposal") {
  const { textarea } = await openPanelIfClosed();
  fireEvent.change(textarea, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: submit }));
}

async function openPanelIfClosed() {
  if (!screen.queryByRole("dialog", { name: /Flow assistant/ })) return openPanel();
  return { panel: screen.getByRole("dialog"), textarea: screen.getByRole("textbox", { name: "Request" }) };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe("docked assistant panel (AC-U1)", () => {
  it("is non-modal, focuses the request and returns focus to its opener on Escape", async () => {
    setup();
    const opener = screen.getByRole("button", { name: "Assistant" });
    const { panel, textarea } = await openPanel();
    expect(panel).not.toHaveAttribute("aria-modal", "true");
    expect(document.querySelector("[data-state].fixed.inset-0")).toBeNull();
    await waitFor(() => expect(textarea).toHaveFocus());
    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: /Flow assistant/ })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("keeps an in-flight request alive when the panel closes", async () => {
    const pending = deferred<unknown>();
    routes["POST /api/assistant/flows/f1/turn"] = () => pending.promise;
    setup();
    await ask("Keep 100 rows");
    fireEvent.click(screen.getByRole("button", { name: "Close assistant" }));
    await act(async () => pending.resolve(proposal()));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    expect(screen.getByRole("button", { name: "Assistant, new reply" })).toBeInTheDocument();
    await openPanel();
    expect(await screen.findByRole("button", { name: "Apply and save" })).toBeEnabled();
  });

  it("keeps the proposal and request after Inspect on canvas", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    setup();
    await ask("Keep 100 rows");
    fireEvent.click(await screen.findByRole("button", { name: "Inspect on canvas" }));
    expect(screen.getByRole("dialog", { name: /Flow assistant/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply and save" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Conversation" })).getByText("Keep 100 rows")).toBeInTheDocument();
  });
});

describe("conversation thread (AC-U2)", () => {
  it("lists requests and replies in order and keeps them across close and reopen", async () => {
    let n = 0;
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: `Answer ${++n}` });
    setup();
    await ask("First question");
    await screen.findByText("Answer 1");
    await ask("Second question");
    await screen.findByText("Answer 2");
    fireEvent.click(screen.getByRole("button", { name: "Close assistant" }));
    await openPanel();
    const thread = screen.getByRole("list", { name: "Conversation" });
    const items = Array.from(thread.children).map((li) => li.textContent ?? "");
    expect(items.map((t) => t.match(/First question|Answer 1|Second question|Answer 2/)?.[0])).toEqual([
      "First question",
      "Answer 1",
      "Second question",
      "Answer 2",
    ]);
  });
});

describe("proposal card (AC-U3, AC-U6)", () => {
  it("summarises the proposal, focuses its heading and announces it", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    setup();
    await ask("Keep 100 rows");
    const heading = await screen.findByRole("heading", { name: "Proposed changes" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByText("1 new node · 1 updated setting · 1 connection")).toBeInTheDocument();
    expect(screen.getByText("Proposal ready: 1 new node, 1 updated setting, 1 connection")).toBeInTheDocument();
    expect(screen.getByText(/Expires in 3:00/)).toBeInTheDocument();
    for (const name of ["Apply and save", "Discard", "Edit request", "Regenerate"])
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
  });

  it("uses the server expiry and turns Apply into Regenerate when expired", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal({ expires_in: 0 });
    setup();
    await ask("Keep 100 rows");
    expect(await screen.findByText("Proposal expired")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply and save" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    await waitFor(() => expect(turns()).toHaveLength(2));
    expect(turns()[1].body?.question).toBe("Keep 100 rows");
  });

  it("puts the request back in the composer on Edit request and drops the proposal on Discard", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    setup();
    await ask("Keep 100 rows");
    fireEvent.click(await screen.findByRole("button", { name: "Edit request" }));
    const textarea = screen.getByRole("textbox", { name: "Request" });
    expect(textarea).toHaveValue("Keep 100 rows");
    expect(textarea).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.queryByRole("button", { name: "Apply and save" })).not.toBeInTheDocument();
    expect(screen.getByText("Discarded")).toBeInTheDocument();
  });
});

describe("guidance card (AC-U4, F2)", () => {
  it.each([
    ["unsupported_node", "This step is not available yet"],
    ["locked_node", "This node is locked"],
    ["unsaved_changes", "Save your changes first"],
    ["multiple_inputs", "Several inputs on the canvas"],
    ["no_dataset", "Choose a dataset first"],
    ["ml_disabled", "Machine learning is turned off"],
    ["no_failed_run", "No failed run to diagnose"],
    ["budget_exhausted", "Request budget used up"],
    ["provider_no_tools", "This model cannot edit flows"],
    ["abstained", "The assistant was not confident"],
    ["no_change", "Nothing to change"],
    ["validation_failed", "The proposal did not pass checks"],
    ["step_limit", "Too many steps for one request"],
    ["timeout", "The request took too long"],
  ])("explains %s in plain copy with the server message as support", async (reason, title) => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: `Server detail for ${reason}.`, reason });
    setup();
    await ask("Pivot by month");
    const heading = await screen.findByRole("heading", { name: title });
    const card = within(heading.closest("article")!);
    expect(card.getByText(`Server detail for ${reason}.`)).toBeInTheDocument();
    expect(card.getByTestId("guidance-explanation").textContent).toMatch(/^[A-Z].+\.$/);
    expect(card.queryByText("Supported")).not.toBeInTheDocument();
  });

  it("lists supported capabilities only when the server sends them", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({
      message: "Pivoting is not available.",
      reason: "unsupported_node",
      supported: ["Limit rows", "Sort rows"],
    });
    setup();
    await ask("Pivot by month");
    await screen.findByRole("heading", { name: "This step is not available yet" });
    expect(screen.getByText("Supported")).toBeInTheDocument();
    expect(screen.getByText("Sort rows")).toBeInTheDocument();
  });

  it("falls back to a generic title without a hardcoded capability list", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: "No supported change was identified." });
    setup();
    await ask("Pivot by month");
    expect(await screen.findByRole("heading", { name: "No change proposed" })).toBeInTheDocument();
    expect(screen.getByText("No supported change was identified.")).toBeInTheDocument();
    expect(screen.queryByText("Supported")).not.toBeInTheDocument();
    expect(screen.queryByText(/edits file flows/)).not.toBeInTheDocument();
  });

  const refusal = (action: string, target?: string) => ({
    message: "The assistant stopped.",
    reason: "abstained",
    suggestions: [{ label: `Do ${action}`, action, ...(target && { target }) }],
  });

  it.each([
    ["retry", false],
    ["share_names", true],
  ])("%s regenerates the request", async (action, shareNames) => {
    routes["POST /api/assistant/flows/f1/turn"] = () => refusal(action);
    setup();
    await ask("Pivot by month");
    fireEvent.click(await screen.findByRole("button", { name: `Do ${action}` }));
    await waitFor(() => expect(turns()).toHaveLength(2));
    expect(turns()[1].body).toMatchObject({ question: "Pivot by month", share_names: shareNames });
  });

  it("switch_mode switches to the target mode", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => refusal("switch_mode", "docs");
    setup();
    await ask("Pivot by month");
    fireEvent.click(await screen.findByRole("button", { name: "Do switch_mode" }));
    expect(screen.getByRole("button", { name: "Guides" })).toHaveAttribute("aria-pressed", "true");
    expect(turns()).toHaveLength(1);
  });

  it.each([
    ["open_docs", "https://ciaren.com/docs/latest/guide/scheduling", "https://ciaren.com/docs/latest/guide/scheduling"],
    ["open_docs", undefined, "https://ciaren.com/docs/latest/guide/flow-assistant"],
    ["open_docs", "javascript:alert(1)", "https://ciaren.com/docs/latest/guide/flow-assistant"],
    ["enable_ml", undefined, "/settings"],
  ])("%s with target %s links to %s", async (action, target, href) => {
    routes["POST /api/assistant/flows/f1/turn"] = () => refusal(action, target);
    setup();
    await ask("Pivot by month");
    expect(await screen.findByRole("link", { name: `Do ${action}` })).toHaveAttribute("href", href);
  });

  it("manual_edit closes the panel and focuses the palette", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => refusal("manual_edit");
    const { focusPalette } = setup();
    await ask("Pivot by month");
    fireEvent.click(await screen.findByRole("button", { name: "Do manual_edit" }));
    expect(screen.queryByRole("dialog", { name: /Flow assistant/ })).not.toBeInTheDocument();
    await waitFor(() => expect(focusPalette).toHaveBeenCalled());
  });

  it("save saves through the editor and regenerates on the new revision", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => refusal("save");
    const { save } = setup({ save: async () => "2026-01-01T00:00:05" });
    await ask("Pivot by month");
    fireEvent.click(await screen.findByRole("button", { name: "Do save" }));
    await waitFor(() => expect(turns()).toHaveLength(2));
    expect(save).toHaveBeenCalledTimes(1);
    expect(turns()[1].body).toMatchObject({ question: "Pivot by month", revision: "2026-01-01T00:00:05" });
  });

  it("does not regenerate when the save fails", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => refusal("save");
    const { save } = setup({ save: async () => null });
    await ask("Pivot by month");
    fireEvent.click(await screen.findByRole("button", { name: "Do save" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    await act(async () => {});
    expect(turns()).toHaveLength(1);
  });
});

describe("conflicts and unsaved canvas (F3)", () => {
  it.each([
    ["unsaved_changes", "Save your changes first"],
    ["disabled_flow", "This flow is disabled"],
  ])("shows a 409 %s as guidance, not a failure", async (reason, title) => {
    routes["POST /api/assistant/flows/f1/turn"] = () =>
      conflict({ detail: "Server conflict detail.", reason });
    setup();
    await ask("Keep 100 rows");
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText("Server conflict detail.")).toBeInTheDocument();
    expect(screen.queryByText("Request failed")).not.toBeInTheDocument();
  });

  it("keeps other 409 responses as failures", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => conflict({ detail: "Stale revision." });
    setup();
    await ask("Keep 100 rows");
    expect(await screen.findByRole("heading", { name: "Request failed" })).toBeInTheDocument();
    expect(screen.getByText("Stale revision.")).toBeInTheDocument();
  });

  it("offers Save on a server unsaved_changes conflict", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () =>
      conflict({ detail: "Save the canvas first.", reason: "unsaved_changes" });
    setup();
    await ask("Keep 100 rows");
    expect(await screen.findByRole("button", { name: "Save and continue" })).toBeInTheDocument();
  });

  it.each([
    ["Build", "Create proposal"],
    ["Diagnose", "Diagnose flow"],
  ])("sends no %s request while the canvas has unsaved edits", async (mode, submit) => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: "ok" });
    const { save } = setup({
      save: async () => {
        useFlowEditorStore.setState({ dirty: false });
        return "2026-01-01T00:00:05";
      },
    });
    await openPanel();
    fireEvent.click(screen.getByRole("button", { name: mode }));
    act(() => useFlowEditorStore.setState({ dirty: true }));
    await ask("Keep 100 rows", submit);
    expect(await screen.findByRole("heading", { name: "Save your changes first" })).toBeInTheDocument();
    expect(turns()).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() => expect(turns()).toHaveLength(1));
    expect(save).toHaveBeenCalledTimes(1);
    expect(turns()[0].body?.revision).toBe("2026-01-01T00:00:05");
  });

  it("still answers guide questions with unsaved edits", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: "Use the export dialog." });
    setup();
    await openPanel();
    fireEvent.click(screen.getByRole("button", { name: "Guides" }));
    act(() => useFlowEditorStore.setState({ dirty: true }));
    await ask("How do I export?", "Ask the guides");
    await waitFor(() => expect(turns()).toHaveLength(1));
    expect(turns()[0].body?.graph).toBeUndefined();
  });
});

describe("proposal trace, removals and server graph (F4, F5)", () => {
  it("shows the step trace and usage when present", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () =>
      proposal({
        steps: [
          { tool: "inspect_schema", ok: true },
          { tool: "add_node", ok: false },
        ],
        usage: { calls: 3, input_tokens: 1200, output_tokens: 340 },
      });
    setup();
    await ask("Keep 100 rows");
    const summary = await screen.findByText("Steps (2)");
    const trace = summary.closest("details")!;
    expect(trace).not.toHaveAttribute("open");
    expect(within(trace).getByText("inspect_schema").closest("li")).toHaveTextContent(/ok/);
    expect(within(trace).getByText("add_node").closest("li")).toHaveTextContent(/failed/);
    expect(screen.getByText("3 calls · 1,200 input tokens · 340 output tokens")).toBeInTheDocument();
  });

  it("omits trace and usage when the server sends neither", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    setup();
    await ask("Keep 100 rows");
    await screen.findByRole("heading", { name: "Proposed changes" });
    expect(screen.queryByText(/^Steps \(/)).not.toBeInTheDocument();
    expect(screen.queryByText(/tokens/)).not.toBeInTheDocument();
  });

  const removal = () => ({
    message: "Remove the limit.",
    proposal: "c".repeat(32),
    delta: { added: [], changed: [], connected: [], disconnected: [], removed: ["l1"] },
  });

  it("summarises removed nodes and marks them on the map", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = removal;
    setup();
    await ask("Remove the limit");
    expect(await screen.findByText("1 removed node")).toBeInTheDocument();
    expect(screen.getByText("Remove Limit")).toBeInTheDocument();
    expect(document.querySelector('.assistant-map [data-removed="l1"]')).not.toBeNull();
  });

  it("drops removed nodes and their edges when the server returns no graph", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = removal;
    routes["POST /api/assistant/flows/f1/apply"] = () => ({ revision: "2026-01-01T00:00:01" });
    const { canvas } = setup();
    await ask("Remove the limit");
    fireEvent.click(await screen.findByRole("button", { name: "Apply and save" }));
    await screen.findByRole("status", { name: "Saved" });
    expect(canvas().nodes.map((n) => n.id)).toEqual(["i1"]);
    expect(canvas().edges).toEqual([]);
  });

  it("loads the graph the server saved instead of the local delta", async () => {
    const server = { nodes: [{ ...base.nodes[0], position: { x: 9, y: 9 } }], edges: [] };
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    routes["POST /api/assistant/flows/f1/apply"] = () => ({ revision: "2026-01-01T00:00:01", graph: server });
    const { saved } = setup();
    await ask("Keep 100 rows");
    fireEvent.click(await screen.findByRole("button", { name: "Apply and save" }));
    await screen.findByRole("status", { name: "Saved" });
    expect(saved).toHaveBeenCalledWith("2026-01-01T00:00:01", server);
  });
});

describe("empty state (AC-U5)", () => {
  it("builds suggested prompts from the selected dataset schema", async () => {
    setup({ graph: { nodes: [], edges: [] } as never });
    await openPanel();
    fireEvent.change(screen.getByLabelText("Input dataset"), { target: { value: "d1" } });
    expect(within(screen.getByRole("region", { name: "Get started" })).getByText("orders")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove rows where email is empty" }));
    expect(screen.getByRole("textbox", { name: "Request" })).toHaveValue("Remove rows where email is empty");
    expect(screen.getByRole("button", { name: "Sort by shipping_cost" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Canvas tools" })).toBeInTheDocument();
  });

  it("suggests general capabilities instead of a fixed step list", async () => {
    setup({ graph: { nodes: [], edges: [] } as never });
    await openPanel();
    fireEvent.change(screen.getByLabelText("Input dataset"), { target: { value: "d1" } });
    for (const name of [
      "Join orders with customers and aggregate revenue by month",
      "Encode categories and scale numeric features",
    ])
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
  });
});

describe("request lifecycle (AC-U6)", () => {
  it("submits with Ctrl+Enter, focuses Cancel and shows cancellation as neutral status", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => new Promise(() => {});
    setup();
    const { textarea } = await openPanel();
    fireEvent.change(textarea, { target: { value: "Keep 100 rows" } });
    fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });
    const cancel = await screen.findByRole("button", { name: "Cancel request" });
    await waitFor(() => expect(cancel).toHaveFocus());
    expect(screen.getByText("Reading schema")).toBeInTheDocument();
    fireEvent.click(cancel);
    expect(screen.getByText(/Request cancelled/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });
});

describe("apply, undo and activity (AC-U7)", () => {
  it("shows a saved toast whose Undo reverts through the activity API", async () => {
    const revision = "2026-01-01T00:00:01";
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    routes["POST /api/assistant/flows/f1/apply"] = () => ({ revision });
    routes["GET /api/assistant/flows/f1/activity"] = () => ({
      entries: [{ id: "ev1", date: `${revision}Z`, source: "build", state: "available", reverses: null, details: [] }],
      next: null,
    });
    routes["POST /api/assistant/flows/f1/activity/ev1/preview"] = () => ({ confirmation: "b".repeat(32), details: [] });
    routes["POST /api/assistant/flows/f1/activity/ev1/revert"] = () => ({ revision: "r3", activity: "ev2" });
    routes["GET /api/flows/f1"] = () => ({ id: "f1", updated_at: "r3", graph_json: base });
    const { restored } = setup();
    await ask("Keep 100 rows");
    fireEvent.click(await screen.findByRole("button", { name: "Apply and save" }));
    const toast = await screen.findByRole("status", { name: "Saved" });
    expect(within(toast).getByRole("button", { name: "View in Activity" })).toBeInTheDocument();
    fireEvent.click(within(toast).getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(restored).toHaveBeenCalled());
    expect(calls.find((c) => c.path.endsWith("/revert"))?.body).toEqual({ proposal: "b".repeat(32) });
  });

  it("moves focus to the request after Apply and keeps toasts auto-dismissing after a click", async () => {
    let n = 0;
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    routes["POST /api/assistant/flows/f1/apply"] = () => ({ revision: `2026-01-01T00:00:0${++n}` });
    setup();
    await ask("Keep 100 rows");
    fireEvent.click(await screen.findByRole("button", { name: "Apply and save" }));
    const toast = await screen.findByRole("status", { name: "Saved" });
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Request" })).toHaveFocus());
    // Hover pauses the toast; dismissing it by click fires no mouseleave.
    fireEvent.mouseEnter(toast);
    fireEvent.click(within(toast).getByRole("button", { name: "Dismiss" }));
    await ask("Keep 100 rows");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      fireEvent.click(await screen.findByRole("button", { name: "Apply and save" }));
      await screen.findByRole("status", { name: "Saved" });
      await act(async () => vi.advanceTimersByTime(15_000));
      expect(screen.queryByRole("status", { name: "Saved" })).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("reports a save made while the canvas changed without a failure alert", async () => {
    let canvasEdited = false;
    routes["POST /api/assistant/flows/f1/turn"] = () => proposal();
    routes["POST /api/assistant/flows/f1/apply"] = () => {
      canvasEdited = true;
      return { revision: "2026-01-01T00:00:01" };
    };
    const edited = { ...base, nodes: [...base.nodes, { ...base.nodes[1], id: "l2" }] } as never;
    let canvas: GraphJson = base;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ReactFlowProvider>
            <TooltipProvider>
              <AssistantPanel
                flowId="f1"
                flowName="Orders"
                projectId="p1"
                revision="2026-01-01T00:00:00"
                disabled={false}
                datasets={datasets as never}
                validation={{ errors: [], warnings: [] } as never}
                restored={() => {}}
                current={() => (canvasEdited ? edited : canvas)}
                saved={(_, graph) => {
                  canvas = graph;
                }}
                save={async () => null}
                focusPalette={() => {}}
              />
            </TooltipProvider>
          </ReactFlowProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await ask("Keep 100 rows");
    fireEvent.click(await screen.findByRole("button", { name: "Apply and save" }));
    expect(await screen.findByText(/Saved on the server while the canvas changed/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not mark a reply as unread when it arrived while the panel was open", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: "Answer" });
    setup();
    await ask("What does this flow do?");
    await screen.findByText("Answer");
    fireEvent.click(screen.getByRole("button", { name: "Close assistant" }));
    expect(screen.getByRole("button", { name: "Assistant" })).not.toHaveAccessibleName(/unread|new/i);
    expect(document.querySelector("[data-unseen]")).toBeNull();
  });

  it("explains inline why a disabled flow cannot change", async () => {
    setup({ disabled: true });
    await openPanel();
    expect(screen.getByText(/This flow is disabled/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create proposal" })).toBeDisabled();
  });

  it("titles entries with the review summary and names what a reversal reverses", async () => {
    routes["GET /api/assistant/flows/f1/activity"] = () => ({
      entries: [
        {
          id: "ev2",
          date: "2026-01-01T00:00:02Z",
          source: "revert",
          state: "recorded",
          reverses: "ev1",
          details: [{ action: "remove_node", kind: "sortRows" }],
        },
        {
          id: "ev1",
          date: "2026-01-01T00:00:01Z",
          source: "build",
          state: "reverted",
          reverses: null,
          details: [
            { action: "add_node", kind: "sortRows" },
            { action: "edit_field", kind: "limitRows", field: "n", before: 10, after: 100 },
            { action: "connect", from: "limitRows", to: "sortRows" },
          ],
        },
      ],
      next: null,
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Activity flowId="f1" projectId="p1" revision="r" disabled={false} current={() => base} restored={() => {}} locking={() => {}} />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "1 new node · 1 updated setting · 1 connection" })).toBeInTheDocument();
    expect(screen.getByText(/Reverses “1 new node · 1 updated setting · 1 connection”/)).toBeInTheDocument();
  });
});

describe("request payload fixes (AC-U10)", () => {
  it("sends the dataset chosen for Diagnose on an empty canvas (VER-006)", async () => {
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: "No failure." });
    setup({ graph: { nodes: [], edges: [] } as never });
    await openPanel();
    fireEvent.click(screen.getByRole("button", { name: "Diagnose" }));
    fireEvent.change(screen.getByLabelText("Input dataset"), { target: { value: "d1" } });
    await ask("Why did it fail?", "Diagnose flow");
    await waitFor(() => expect(turns()).toHaveLength(1));
    expect(turns()[0].body?.dataset_id).toBe("d1");
  });

  it("does not send version 0 when a training input is no longer known (VER-007)", async () => {
    routes["GET /api/transformations"] = () => ["mlTrainClassifier"];
    routes["POST /api/assistant/flows/f1/turn"] = () => ({ message: "ok" });
    const { rerender } = setup({ graph: { nodes: [], edges: [] } as never });
    await openPanel();
    fireEvent.change(screen.getByLabelText("Input dataset"), { target: { value: "d1" } });
    fireEvent.change(screen.getByLabelText("Right input for Join"), { target: { value: "d2" } });
    fireEvent.change(await screen.findByLabelText(/Second lookup/), { target: { value: "d3" } });
    fireEvent.change(screen.getByLabelText("Regression target"), { target: { value: "shipping_cost" } });
    rerender(datasets.slice(0, 2));
    fireEvent.change(screen.getByRole("textbox", { name: "Request" }), { target: { value: "Predict cost" } });
    const submit = screen.getByRole("button", { name: "Create proposal" });
    fireEvent.click(submit);
    expect(submit).toBeDisabled();
    expect(turns().some((c) => JSON.stringify(c.body?.training ?? {}).includes('"versions":[2,1,0]'))).toBe(false);
    expect(turns()).toHaveLength(0);
  });
});
