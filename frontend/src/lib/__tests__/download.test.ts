import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadFromApi } from "@/lib/download";
import { ApiError, setApiToken } from "@/lib/api/client";

function mockOkResponse(body: string, headers: Record<string, string> = {}) {
  return {
    ok: true,
    status: 200,
    headers: { get: (name: string) => headers[name] ?? null },
    blob: async () => new Blob([body], { type: "text/csv" }),
  } as unknown as Response;
}

describe("downloadFromApi", () => {
  const createObjectURL = vi.fn(() => "blob:mock-url");
  const revokeObjectURL = vi.fn();
  const clickSpy = vi.fn<(href: string, name: string) => void>();

  beforeEach(() => {
    setApiToken(null);
    createObjectURL.mockClear();
    revokeObjectURL.mockClear();
    clickSpy.mockClear();
    // jsdom doesn't implement object URLs — stub them.
    (URL as unknown as { createObjectURL: unknown }).createObjectURL = createObjectURL;
    (URL as unknown as { revokeObjectURL: unknown }).revokeObjectURL = revokeObjectURL;
    // Intercept the synthetic anchor's click so no real navigation happens.
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clickSpy(this.href, this.download);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setApiToken(null);
  });

  it("fetches with the Authorization header when a token is configured", async () => {
    setApiToken("secret-token");
    const fetchMock = vi.fn(async () => mockOkResponse("a,b\n1,2\n"));
    vi.stubGlobal("fetch", fetchMock);

    await downloadFromApi("/runs/r1/output?node_id=n1", "output");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    // Bare endpoint path gets the /api prefix, and rides the fetch — not an anchor nav.
    expect(url).toBe("/api/runs/r1/output?node_id=n1");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer secret-token");
    vi.unstubAllGlobals();
  });

  it("sends no auth header on the no-token (localhost) path", async () => {
    const fetchMock = vi.fn(async () => mockOkResponse("x"));
    vi.stubGlobal("fetch", fetchMock);

    await downloadFromApi("/api/datasets/d1/versions/2/download", "d-v2");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    // Already /api-prefixed paths are used as-is (not double-prefixed).
    expect(url).toBe("/api/datasets/d1/versions/2/download");
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
    vi.unstubAllGlobals();
  });

  it("triggers a blob download via a synthetic anchor, never an /api navigation", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => mockOkResponse("payload")));

    await downloadFromApi("/runs/r1/output?node_id=n1", "output");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    // The anchor points at the blob URL, NOT at /api — proving no plain-anchor nav.
    expect(clickSpy).toHaveBeenCalledWith("blob:mock-url", "output");
    expect(clickSpy.mock.calls[0][0]).not.toContain("/api");
    // Object URL is released after the click.
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
    vi.unstubAllGlobals();
  });

  it("prefers the Content-Disposition filename over the fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockOkResponse("payload", {
          "Content-Disposition": 'attachment; filename="orders_v3.csv"',
        }),
      ),
    );

    await downloadFromApi("/runs/r1/output?node_id=n1", "fallback");

    expect(clickSpy).toHaveBeenCalledWith("blob:mock-url", "orders_v3.csv");
    vi.unstubAllGlobals();
  });

  it("throws an ApiError on a non-OK response and does not download", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 401,
        headers: { get: () => null },
        json: async () => ({ detail: "Not authenticated" }),
      })),
    );

    await expect(downloadFromApi("/runs/r1/output?node_id=n1", "output")).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(createObjectURL).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
