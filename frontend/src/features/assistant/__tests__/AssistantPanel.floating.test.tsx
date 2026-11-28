import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AssistantPanel } from "../AssistantPanel";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ provider: "off", state: "missing" }),
      text: async () => JSON.stringify({ provider: "off", state: "missing" }),
    })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPanel(host: HTMLElement | null) {
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
              revision="r1"
              disabled={false}
              datasets={[]}
              validation={{ errors: [], warnings: [] } as never}
              restored={() => {}}
              current={() => ({ nodes: [], edges: [] })}
              saved={() => {}}
              save={async () => null}
              focusPalette={() => {}}
              floatingHost={host}
            />
          </TooltipProvider>
        </ReactFlowProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AssistantPanel floating launcher", () => {
  it("shows a launcher over the canvas that opens the assistant and hides while it is open", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    renderPanel(host);

    const launcher = within(host).getByRole("button", { name: "Ask the flow assistant" });
    fireEvent.click(launcher);

    expect(screen.getByRole("dialog", { name: /Flow assistant/ })).toBeInTheDocument();
    expect(within(host).queryByRole("button", { name: "Ask the flow assistant" })).not.toBeInTheDocument();
    host.remove();
  });

  it("renders no launcher without a canvas host", () => {
    renderPanel(null);
    expect(screen.queryByRole("button", { name: "Ask the flow assistant" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Assistant/ })).toBeInTheDocument();
  });
});
