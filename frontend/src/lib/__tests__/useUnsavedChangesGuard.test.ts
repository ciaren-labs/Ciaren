import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useUnsavedChangesGuard } from "@/lib/useUnsavedChangesGuard";

describe("useUnsavedChangesGuard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("registers a beforeunload listener while dirty and removes it when clean", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");

    const { rerender, unmount } = renderHook(({ dirty }) => useUnsavedChangesGuard(dirty), {
      initialProps: { dirty: true },
    });
    expect(addSpy.mock.calls.some(([type]) => type === "beforeunload")).toBe(true);

    // Becoming clean tears the listener down.
    rerender({ dirty: false });
    expect(removeSpy.mock.calls.some(([type]) => type === "beforeunload")).toBe(true);

    unmount();
  });

  it("does not register beforeunload when starting clean", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    renderHook(() => useUnsavedChangesGuard(false));
    expect(addSpy.mock.calls.some(([type]) => type === "beforeunload")).toBe(false);
  });

  it("proceeds immediately without a prompt when not dirty", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { result } = renderHook(() => useUnsavedChangesGuard(false));
    const proceed = vi.fn();
    result.current(proceed);
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(proceed).toHaveBeenCalledTimes(1);
  });

  it("prompts when dirty and only proceeds if the user confirms", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { result } = renderHook(() => useUnsavedChangesGuard(true));
    const proceed = vi.fn();

    result.current(proceed);
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(proceed).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    result.current(proceed);
    expect(proceed).toHaveBeenCalledTimes(1);
  });
});
