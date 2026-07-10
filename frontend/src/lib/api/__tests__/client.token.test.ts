import { beforeEach, describe, expect, it, vi } from "vitest";

const KEY = "ciaren_api_token";

describe("api token storage", () => {
  beforeEach(() => {
    vi.resetModules(); // fresh module → fresh in-memory token + re-run of capture
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("persists to sessionStorage, never localStorage, and clears on null", async () => {
    const { setApiToken, getApiToken } = await import("../client");

    setApiToken("secret-123");
    expect(getApiToken()).toBe("secret-123");
    expect(window.sessionStorage.getItem(KEY)).toBe("secret-123");
    // The whole point: nothing durable is written.
    expect(window.localStorage.getItem(KEY)).toBeNull();

    setApiToken(null);
    expect(getApiToken()).toBeNull();
    expect(window.sessionStorage.getItem(KEY)).toBeNull();
  });

  it("migrates a legacy localStorage token into sessionStorage on load", async () => {
    window.localStorage.setItem(KEY, "legacy-xyz");

    const { getApiToken } = await import("../client"); // captureTokenFromUrl runs on import

    expect(getApiToken()).toBe("legacy-xyz");
    expect(window.sessionStorage.getItem(KEY)).toBe("legacy-xyz");
    // The insecure durable copy is purged.
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("captures a ?api_token= URL param into sessionStorage and strips it from the URL", async () => {
    window.history.replaceState({}, "", "/?api_token=url-tok&x=1");

    const { getApiToken } = await import("../client");

    expect(getApiToken()).toBe("url-tok");
    expect(window.sessionStorage.getItem(KEY)).toBe("url-tok");
    expect(window.location.search).not.toContain("api_token");
    // Unrelated params survive the strip.
    expect(window.location.search).toContain("x=1");
  });
});
