import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { queryKeys } from "@/lib/queryClient";

vi.mock("@/lib/api", () => ({
  connectionsApi: {
    objects: vi.fn((id: string, prefix?: string) => Promise.resolve([`${id}:${prefix ?? ""}`])),
  },
}));

import { useConnectionObjects } from "../hooks";

function wrapperFor(client: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
}

describe("useConnectionObjects prefix", () => {
  it("varies the query key by prefix", () => {
    expect(queryKeys.connectionObjects("c1", "a")).not.toEqual(
      queryKeys.connectionObjects("c1", "b"),
    );
    // No prefix is equivalent to the empty prefix (root listing).
    expect(queryKeys.connectionObjects("c1")).toEqual(queryKeys.connectionObjects("c1", ""));
  });

  it("passes the prefix to the API and caches each prefix separately", async () => {
    const { connectionsApi } = await import("@/lib/api");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = wrapperFor(client);

    const a = renderHook(() => useConnectionObjects("c1", "folderA/"), { wrapper });
    const b = renderHook(() => useConnectionObjects("c1", "folderB/"), { wrapper });

    await waitFor(() =>
      expect(a.result.current.isSuccess && b.result.current.isSuccess).toBe(true),
    );

    expect(connectionsApi.objects).toHaveBeenCalledWith("c1", "folderA/");
    expect(connectionsApi.objects).toHaveBeenCalledWith("c1", "folderB/");
    // Distinct cache entries: no cross-prefix bleed.
    expect(a.result.current.data).not.toEqual(b.result.current.data);
  });
});
