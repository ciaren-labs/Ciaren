import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import { friendlyErrorMessage } from "@/lib/errors";

describe("friendlyErrorMessage", () => {
  it("passes through domain messages from the backend", () => {
    const err = new ApiError("Flow name already exists", 409);
    expect(friendlyErrorMessage(err)).toBe("Flow name already exists");
  });

  it("rescues bare status messages with the fallback", () => {
    const err = new ApiError("Request failed with status 400", 400);
    expect(friendlyErrorMessage(err, "Upload failed.")).toBe("Upload failed.");
  });

  it("explains auth failures by pointing at the real token mechanism", () => {
    const err = new ApiError("Request failed with status 401", 401);
    const msg = friendlyErrorMessage(err);
    expect(msg).toMatch(/API token/);
    // The token is supplied via the ?api_token= URL param, not a header menu.
    expect(msg).toMatch(/api_token/);
    expect(msg).not.toMatch(/header menu/i);
  });

  it("uses the same auth guidance for 403 as for 401", () => {
    const err = new ApiError("Request failed with status 403", 403);
    expect(friendlyErrorMessage(err)).not.toMatch(/header menu/i);
  });

  it("explains bare 404s as a stale reference", () => {
    const err = new ApiError("Request failed with status 404", 404);
    expect(friendlyErrorMessage(err)).toMatch(/no longer exists/);
  });

  it("keeps a server-provided message on 404", () => {
    const err = new ApiError("Dataset not found", 404);
    expect(friendlyErrorMessage(err)).toBe("Dataset not found");
  });

  it("explains bare 500s without exposing the status line", () => {
    const err = new ApiError("Request failed with status 500", 500);
    expect(friendlyErrorMessage(err)).toMatch(/server hit an unexpected error/i);
  });

  it("keeps a server-provided message on 500", () => {
    const err = new ApiError("Polars engine not installed", 500);
    expect(friendlyErrorMessage(err)).toBe("Polars engine not installed");
  });

  it("translates network failures into a reachability hint", () => {
    expect(friendlyErrorMessage(new TypeError("Failed to fetch"))).toMatch(
      /Can't reach the Ciaren server/,
    );
  });

  it("falls back for unknown values", () => {
    expect(friendlyErrorMessage(undefined)).toBe("Something went wrong.");
    expect(friendlyErrorMessage(null, "Nope.")).toBe("Nope.");
  });
});
