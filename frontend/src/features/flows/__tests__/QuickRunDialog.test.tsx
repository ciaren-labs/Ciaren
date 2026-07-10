import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuickRunDialog } from "../QuickRunDialog";
import type { Flow } from "@/features/flows/types";

function makeFlow(overrides: Partial<Flow["graph_json"]> = {}): Flow {
  return {
    id: "f1",
    name: "My flow",
    description: null,
    project_id: "p1",
    is_disabled: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    last_run_at: null,
    graph_json: { nodes: [], edges: [], ...overrides },
  };
}

function renderDialog(flow: Flow | null, onRun = vi.fn()) {
  render(
    <QuickRunDialog
      flow={flow}
      onOpenChange={() => {}}
      onRun={onRun}
      isPending={false}
      error={null}
    />,
  );
  return onRun;
}

describe("QuickRunDialog", () => {
  it("runs a parameter-less flow with just the engine (no parameters payload)", async () => {
    const user = userEvent.setup();
    const onRun = renderDialog(makeFlow());

    // No parameter section for a flow that declares none.
    expect(screen.queryByText("Parameters")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^run$/i }));

    expect(onRun).toHaveBeenCalledWith({ engine: "pandas", parameters: undefined });
  });

  it("seeds the engine from the flow's saved engine", () => {
    renderDialog(makeFlow({ engine: "polars" }));
    // The polars button is the selected one (brand background).
    const polars = screen.getByRole("button", { name: "polars" });
    expect(polars.className).toMatch(/bg-brand-600/);
  });

  it("blocks the run until a required parameter is filled, then passes values", async () => {
    const user = userEvent.setup();
    const onRun = renderDialog(
      makeFlow({
        parameters: [
          { name: "keep", type: "integer", default: 2 },
          { name: "label", type: "string" }, // required (no default)
        ],
      }),
    );

    // Required `label` empty → Run disabled (backend would 400 otherwise).
    const run = screen.getByRole("button", { name: /^run$/i });
    expect(run).toBeDisabled();
    expect(screen.getByLabelText("value-keep")).toHaveValue("2"); // default pre-filled

    await user.type(screen.getByLabelText("value-label"), "june");
    await waitFor(() => expect(run).toBeEnabled());
    await user.click(run);

    expect(onRun).toHaveBeenCalledWith({
      engine: "pandas",
      parameters: { keep: 2, label: "june" },
    });
  });

  it("uses a chosen engine alongside collected parameters", async () => {
    const user = userEvent.setup();
    const onRun = renderDialog(
      makeFlow({ parameters: [{ name: "keep", type: "integer", default: 5 }] }),
    );

    await user.click(screen.getByRole("button", { name: "polars" }));
    await user.click(screen.getByRole("button", { name: /^run$/i }));

    expect(onRun).toHaveBeenCalledWith({ engine: "polars", parameters: { keep: 5 } });
  });
});
