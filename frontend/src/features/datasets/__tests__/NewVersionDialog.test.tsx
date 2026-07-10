import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NewVersionDialog } from "../components/NewVersionDialog";

describe("NewVersionDialog", () => {
  it("shows the pending file name in the confirmation copy", () => {
    render(
      <NewVersionDialog
        open
        fileName="sales.csv"
        isPending={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/sales\.csv/)).toBeInTheDocument();
  });

  it("renders nothing interactive when closed", () => {
    render(
      <NewVersionDialog
        open={false}
        fileName="sales.csv"
        isPending={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.queryByText("Add new version?")).not.toBeInTheDocument();
  });

  it("calls onConfirm on the primary action and disables it while pending", async () => {
    const onConfirm = vi.fn();
    render(
      <NewVersionDialog
        open
        fileName="sales.csv"
        isPending={false}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Add new version" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("disables the confirm button while the upload is pending", () => {
    render(
      <NewVersionDialog
        open
        fileName="sales.csv"
        isPending
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Add new version" })).toBeDisabled();
  });

  it("calls onCancel via the Cancel button", async () => {
    const onCancel = vi.fn();
    render(
      <NewVersionDialog
        open
        fileName="sales.csv"
        isPending={false}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
