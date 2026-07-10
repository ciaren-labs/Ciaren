import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateFlowDialog } from "../components/CreateFlowDialog";
import type { Project } from "@/features/projects/types";

const PROJECT: Project = {
  id: "p1",
  name: "Marketing",
  description: null,
  color: "violet",
  is_default: false,
  is_disabled: false,
  dataset_count: 0,
  flow_count: 0,
  created_at: "2026-06-01T00:00:00+00:00",
  updated_at: "2026-06-01T00:00:00+00:00",
};

function renderDialog(overrides: Partial<React.ComponentProps<typeof CreateFlowDialog>> = {}) {
  const onCreate = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <CreateFlowDialog
      open
      onOpenChange={onOpenChange}
      projects={[PROJECT]}
      defaultProjectId=""
      isPending={false}
      trigger={<button>New flow</button>}
      onCreate={onCreate}
      {...overrides}
    />,
  );
  return { onCreate, onOpenChange };
}

describe("CreateFlowDialog", () => {
  it("does not submit and shows an error when the name field is empty", async () => {
    const { onCreate } = renderDialog();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).not.toHaveBeenCalled();
    expect(await screen.findByText(/required/i)).toBeInTheDocument();
  });

  it("submits a blank-flow graph by default, using the default project id", async () => {
    const { onCreate } = renderDialog({ defaultProjectId: "p1" });
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("My ETL flow"), "My flow");
    await user.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "My flow",
        projectId: "p1",
        graph: { nodes: [], edges: [] },
      }),
      expect.any(Function),
    );
  });

  it("submits a non-empty graph when a template is selected", async () => {
    const { onCreate } = renderDialog();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("My ETL flow"), "Templated flow");
    await user.click(screen.getByText("Clean & Deduplicate"));
    await user.click(screen.getByRole("button", { name: "Create" }));

    const [call] = onCreate.mock.calls;
    expect(call[0].graph.nodes.length).toBeGreaterThan(0);
  });

  it("disables the submit button while pending and shows a busy label", () => {
    renderDialog({ isPending: true });
    const btn = screen.getByRole("button", { name: "Creating…" });
    expect(btn).toBeDisabled();
  });

  it("passes an onSuccess callback to onCreate as the second argument", async () => {
    const { onCreate } = renderDialog();
    await userEvent.setup().type(screen.getByPlaceholderText("My ETL flow"), "My flow");
    await userEvent.setup().click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledTimes(1);
    expect(typeof onCreate.mock.calls[0][1]).toBe("function");
  });

  it("keeps the typed name and selected template if the create request fails (onSuccess never called)", async () => {
    const user = userEvent.setup();
    // Simulate a failed mutation: onCreate is invoked, but its onSuccess
    // callback is deliberately never called back — mirroring a real
    // createFlow.mutate() rejection, where FlowListPage has no onError
    // handler for this dialog and just leaves it open.
    const onCreate = vi.fn();
    renderDialog({ onCreate });

    await user.type(screen.getByPlaceholderText("My ETL flow"), "Survives failure");
    await user.click(screen.getByText("Clean & Deduplicate"));
    await user.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledTimes(1);
    // The form must NOT have been reset — the user shouldn't have to retype
    // everything after a failed submission.
    expect(screen.getByPlaceholderText("My ETL flow")).toHaveValue("Survives failure");
    expect(screen.getByText("Clean & Deduplicate").closest("button")!.className).toContain(
      "border-primary",
    );
  });

  it("resets the form once onCreate invokes its onSuccess callback", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn((_values, onSuccess: () => void) => onSuccess());
    renderDialog({ onCreate });

    await user.type(screen.getByPlaceholderText("My ETL flow"), "Succeeds");
    await user.click(screen.getByText("Clean & Deduplicate"));
    await user.click(screen.getByRole("button", { name: "Create" }));

    expect(screen.getByPlaceholderText("My ETL flow")).toHaveValue("");
    expect(screen.getByText("Clean & Deduplicate").closest("button")!.className).not.toContain(
      "border-primary",
    );
  });

  it("resets the selected template once the dialog is closed via Escape and reopened", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();

    function Wrapper() {
      const [open, setOpen] = useState(true);
      return (
        <>
          <button onClick={() => setOpen(true)}>Reopen</button>
          <CreateFlowDialog
            open={open}
            onOpenChange={setOpen}
            projects={[PROJECT]}
            defaultProjectId=""
            isPending={false}
            trigger={<button>New flow trigger</button>}
            onCreate={onCreate}
          />
        </>
      );
    }
    render(<Wrapper />);

    const templateButton = () => screen.getByText("Clean & Deduplicate").closest("button")!;

    await user.click(templateButton());
    expect(templateButton().className).toContain("border-primary");

    // Radix's onOpenChange fires for an Escape-driven close (unlike an
    // externally forced `open` prop flip), which is what actually resets
    // selectedTemplateId in the component.
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Reopen" }));

    await user.type(screen.getByPlaceholderText("My ETL flow"), "Fresh flow");
    await user.click(screen.getByRole("button", { name: "Create" }));

    // A stale selectedTemplateId would have produced a non-empty graph here.
    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({ graph: { nodes: [], edges: [] } }),
      expect.any(Function),
    );
  });
});
