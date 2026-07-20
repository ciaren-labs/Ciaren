import { afterEach, describe, expect, it, vi } from "vitest";
import { readLocalStorage, writeLocalStorage } from "@/lib/safeStorage";

describe("safeStorage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("round-trips a value through localStorage", () => {
    writeLocalStorage("ciaren_test_key", "42");
    expect(readLocalStorage("ciaren_test_key")).toBe("42");
  });

  it("returns null for an absent key", () => {
    expect(readLocalStorage("ciaren_missing_key")).toBeNull();
  });

  it("returns null instead of throwing when getItem throws (storage blocked)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    expect(() => readLocalStorage("ciaren_any")).not.toThrow();
    expect(readLocalStorage("ciaren_any")).toBeNull();
  });

  it("swallows setItem failures (quota / SecurityError)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    expect(() => writeLocalStorage("ciaren_any", "value")).not.toThrow();
  });
});
