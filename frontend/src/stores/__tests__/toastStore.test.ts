import { beforeEach, describe, expect, it } from "vitest";
import { toast, useToastStore } from "@/stores/toastStore";

describe("toastStore", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  it("pushes toasts with variant defaults", () => {
    toast.success("Saved");
    toast.error("Broke");
    const { toasts } = useToastStore.getState();
    expect(toasts).toHaveLength(2);
    expect(toasts[0]).toMatchObject({ variant: "success", title: "Saved" });
    // Errors linger longer than confirmations.
    expect(toasts[1].duration).toBeGreaterThan(toasts[0].duration);
  });

  it("carries description and action through", () => {
    toast.success("Run started", {
      description: "Engine: pandas",
      action: { label: "View run", to: "/runs/abc" },
    });
    const [t] = useToastStore.getState().toasts;
    expect(t.description).toBe("Engine: pandas");
    expect(t.action).toEqual({ label: "View run", to: "/runs/abc" });
  });

  it("carries a callback action through (e.g. Undo) distinct from a link action", () => {
    const onClick = () => {};
    toast.success("Node deleted", { action: { label: "Undo", onClick } });
    const [t] = useToastStore.getState().toasts;
    expect(t.action).toEqual({ label: "Undo", onClick });
  });

  it("dismisses by id", () => {
    const id = toast.info("Hello");
    toast.info("World");
    useToastStore.getState().dismiss(id);
    const { toasts } = useToastStore.getState();
    expect(toasts).toHaveLength(1);
    expect(toasts[0].title).toBe("World");
  });

  it("caps the stack at four toasts, dropping the oldest", () => {
    for (let i = 0; i < 6; i++) toast.info(`t${i}`);
    const { toasts } = useToastStore.getState();
    expect(toasts).toHaveLength(4);
    expect(toasts[0].title).toBe("t2");
    expect(toasts[3].title).toBe("t5");
  });
});
