import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditorToolbar } from "../components/EditorToolbar";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { FlowValidation } from "@/lib/flowValidation";

const READY_VALIDATION: FlowValidation = {
  issues: [],
  errors: [],
  warnings: [],
  errorsByNode: new Map(),
  canRun: true,
  canExport: true,
  canPreview: true,
};

function baseProps(overrides: Partial<React.ComponentProps<typeof EditorToolbar>> = {}) {
  return {
    flowName: "My Flow",
    onBack: vi.fn(),
    onRename: vi.fn(),
    projectName: "Demo",
    isDisabled: false,
    dirty: false,
    validation: READY_VALIDATION,
    onReEnable: vi.fn(),
    toggleFlowPending: false,
    canUndo: false,
    canRedo: false,
    onUndo: vi.fn(),
    onRedo: vi.fn(),
    previewOpen: false,
    onTogglePreview: vi.fn(),
    previewReason: undefined,
    engine: "pandas" as const,
    onEngineChange: vi.fn(),
    canRun: true,
    createRunPending: false,
    runReason: undefined,
    onRun: vi.fn(),
    canExport: true,
    onExport: vi.fn(),
    parametersCount: 0,
    onOpenParameters: vi.fn(),
    onOpenSchedule: vi.fn(),
    onSave: vi.fn(),
    savePending: false,
    ...overrides,
  };
}

function renderToolbar(overrides: Partial<React.ComponentProps<typeof EditorToolbar>> = {}) {
  return render(
    <TooltipProvider>
      <EditorToolbar {...baseProps(overrides)} />
    </TooltipProvider>,
  );
}

describe("EditorToolbar", () => {
  it("shows the flow name, project, and a 'Ready to run' pill when validation passes", () => {
    renderToolbar();
    expect(screen.getByText("My Flow")).toBeInTheDocument();
    expect(screen.getByText("/ Demo")).toBeInTheDocument();
    expect(screen.getByText("Ready to run")).toBeInTheDocument();
  });

  it("shows an 'unsaved' badge only when dirty and not disabled", () => {
    const { rerender } = renderToolbar({ dirty: true });
    expect(screen.getByText("unsaved")).toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <EditorToolbar {...baseProps({ dirty: false })} />
      </TooltipProvider>,
    );
    expect(screen.queryByText("unsaved")).not.toBeInTheDocument();
  });

  it("collapses to just a Re-enable button when the flow is disabled, hiding all edit actions", () => {
    renderToolbar({ isDisabled: true });
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Re-enable flow/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Undo")).not.toBeInTheDocument();
  });

  it("calls onReEnable when the disabled-state button is clicked", async () => {
    const onReEnable = vi.fn();
    renderToolbar({ isDisabled: true, onReEnable });
    await userEvent.setup().click(screen.getByRole("button", { name: /Re-enable flow/ }));
    expect(onReEnable).toHaveBeenCalledTimes(1);
  });

  it("disables Undo/Redo based on canUndo/canRedo and wires their handlers", async () => {
    const onUndo = vi.fn();
    const onRedo = vi.fn();
    renderToolbar({ canUndo: true, canRedo: false, onUndo, onRedo });
    const undoBtn = screen.getByLabelText("Undo");
    const redoBtn = screen.getByLabelText("Redo");
    expect(undoBtn).not.toBeDisabled();
    expect(redoBtn).toBeDisabled();
    await userEvent.setup().click(undoBtn);
    expect(onUndo).toHaveBeenCalledTimes(1);
  });

  it("toggles the preview button label based on previewOpen", () => {
    const { rerender } = renderToolbar({ previewOpen: false });
    expect(screen.getByText("Preview")).toBeInTheDocument();
    rerender(
      <TooltipProvider>
        <EditorToolbar {...baseProps({ previewOpen: true })} />
      </TooltipProvider>,
    );
    expect(screen.getByText("Hide preview")).toBeInTheDocument();
  });

  it("disables Run when canRun is false and shows the reason via tooltip trigger", () => {
    renderToolbar({ canRun: false, runReason: "Add an output node first" });
    expect(screen.getByText("Run").closest("button")).toBeDisabled();
  });

  it("shows a spinner label while a run is pending", () => {
    renderToolbar({ createRunPending: true });
    expect(screen.getByText("Run").closest("button")).toBeDisabled();
  });

  it("calls onEngineChange with the new engine value", async () => {
    const onEngineChange = vi.fn();
    renderToolbar({ onEngineChange });
    await userEvent.setup().selectOptions(screen.getByTitle("Execution engine"), "polars");
    expect(onEngineChange).toHaveBeenCalledWith("polars");
  });

  it("shows the parameters count badge only when there are parameters", () => {
    const { rerender } = renderToolbar({ parametersCount: 0 });
    expect(screen.queryByText("3")).not.toBeInTheDocument();
    rerender(
      <TooltipProvider>
        <EditorToolbar {...baseProps({ parametersCount: 3 })} />
      </TooltipProvider>,
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows Saving… and disables the button while a save is pending", () => {
    renderToolbar({ savePending: true });
    expect(screen.getByRole("button", { name: /Saving…/ })).toBeDisabled();
  });

  it("calls onSave when Save is clicked", async () => {
    const onSave = vi.fn();
    renderToolbar({ onSave });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
