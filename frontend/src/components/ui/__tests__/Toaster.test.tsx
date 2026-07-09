import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Toaster } from "../Toaster";
import { toast, useToastStore } from "@/stores/toastStore";

function renderToaster() {
  return render(
    <MemoryRouter>
      <Toaster />
    </MemoryRouter>,
  );
}

describe("Toaster", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  it("renders a link action and dismisses on click", async () => {
    const user = userEvent.setup();
    toast.success("Run started", { action: { label: "View run", to: "/runs/abc" } });
    renderToaster();

    const link = screen.getByRole("link", { name: "View run →" });
    expect(link).toHaveAttribute("href", "/runs/abc");

    await user.click(link);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("renders a callback action, invokes it, and dismisses the toast", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    toast.success("Node deleted", { action: { label: "Undo", onClick } });
    renderToaster();

    const button = screen.getByRole("button", { name: "Undo" });
    await user.click(button);

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("does not render any action affordance when the toast has none", () => {
    toast.info("Just fyi");
    renderToaster();

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryAllByRole("button")).toHaveLength(1); // only the dismiss "x"
  });

  it("renders only the link when an action malformed past the type system carries both to and onClick", () => {
    // ToastAction's type prevents this at every current call site, but the
    // union isn't runtime-enforced (no shared literal tag) — a future caller
    // (or anything bypassing the type with `as`) shouldn't be able to render
    // both a Link and a button for one toast.
    const onClick = vi.fn();
    useToastStore.getState().push({
      variant: "success",
      title: "Ambiguous",
      action: { label: "Both", to: "/somewhere", onClick } as any,
    });
    renderToaster();

    expect(screen.getByRole("link", { name: "Both →" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Both" })).not.toBeInTheDocument();
  });

  it("dismisses via its own close button independent of any action", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    toast.success("Node deleted", { action: { label: "Undo", onClick } });
    renderToaster();

    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));

    expect(onClick).not.toHaveBeenCalled();
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });
});
