import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";

vi.mock("@/lib/api", () => ({
  datasetsApi: {
    remove: vi.fn(() => Promise.resolve()),
    patch: vi.fn((id: string, body: { is_disabled?: boolean }) =>
      Promise.resolve({ id, name: "sales.csv", is_disabled: !!body.is_disabled }),
    ),
  },
}));
vi.mock("@/stores/toastStore", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { useDeleteDataset, usePatchDataset } from "../hooks";

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidateSpy = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
  return { wrapper, invalidateSpy };
}

function invalidatedKeys(spy: ReturnType<typeof vi.spyOn>): string[][] {
  return spy.mock.calls.map(
    (c: [{ queryKey: string[] }, ...unknown[]]) => c[0].queryKey,
  );
}

describe("dataset cache invalidation", () => {
  beforeEach(() => vi.clearAllMocks());

  // Deleting a dataset cascades to disable dependent flows on the backend
  // (DELETE /datasets/{id} → disable_flows_for_dataset), so the flows list must
  // be invalidated or it keeps showing them enabled until the next refetch —
  // the same reasoning that already makes usePatchDataset invalidate flows.
  it("useDeleteDataset invalidates datasets, projects, AND flows", async () => {
    const { wrapper, invalidateSpy } = makeWrapper();
    const { result } = renderHook(() => useDeleteDataset(), { wrapper });

    result.current.mutate("d1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = invalidatedKeys(invalidateSpy);
    expect(keys).toContainEqual(["datasets"]);
    expect(keys).toContainEqual(["projects"]);
    expect(keys).toContainEqual(["flows"]);
  });

  // Guards the parity the fix above restores: the disable path (which triggers
  // the identical backend cascade) has always invalidated flows.
  it("usePatchDataset(disable) invalidates flows", async () => {
    const { wrapper, invalidateSpy } = makeWrapper();
    const { result } = renderHook(() => usePatchDataset(), { wrapper });

    result.current.mutate({ id: "d1", body: { is_disabled: true } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidatedKeys(invalidateSpy)).toContainEqual(["flows"]);
  });
});
