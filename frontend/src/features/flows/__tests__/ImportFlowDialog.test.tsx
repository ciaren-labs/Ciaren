import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ImportFlowDialog } from "../components/ImportFlowDialog";

function renderDialog(overrides: Partial<React.ComponentProps<typeof ImportFlowDialog>> = {}) {
  const onSubmit = vi.fn();
  const onOpenChange = vi.fn();
  const onNameChange = vi.fn();
  render(
    <ImportFlowDialog
      open
      onOpenChange={onOpenChange}
      name="Imported flow"
      onNameChange={onNameChange}
      nameError={null}
      warning={null}
      error={null}
      isPending={false}
      onSubmit={onSubmit}
      {...overrides}
    />,
  );
  return { onSubmit, onOpenChange, onNameChange };
}

describe("ImportFlowDialog", () => {
  it("calls onSubmit when the form is submitted", async () => {
    const { onSubmit } = renderDialog();
    await userEvent.setup().click(screen.getByRole("button", { name: "Import" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("closes via Cancel without calling onSubmit", async () => {
    const { onSubmit, onOpenChange } = renderDialog();
    await userEvent.setup().click(screen.getByRole("button", { name: "Cancel" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("shows the name error and warning independently", () => {
    renderDialog({ nameError: "Name is required.", warning: "will be upgraded" });
    expect(screen.getByText("Name is required.")).toBeInTheDocument();
    expect(screen.getByText(/will be upgraded/)).toBeInTheDocument();
  });

  it("hides the warning once an error is present, matching FlowListPage's mutual-exclusion", () => {
    renderDialog({ warning: "will be upgraded", error: "Import failed." });
    expect(screen.queryByText(/will be upgraded/)).not.toBeInTheDocument();
    expect(screen.getByText("Import failed.")).toBeInTheDocument();
  });

  it("disables the Import button while pending", () => {
    renderDialog({ isPending: true });
    expect(screen.getByRole("button", { name: "Import" })).toBeDisabled();
  });

  it("propagates name field edits via onNameChange", async () => {
    const { onNameChange } = renderDialog({ name: "" });
    await userEvent.setup().type(screen.getByPlaceholderText("Flow name"), "x");
    expect(onNameChange).toHaveBeenCalledWith("x");
  });
});
