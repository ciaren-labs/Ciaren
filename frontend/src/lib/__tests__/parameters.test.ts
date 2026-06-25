import { describe, expect, it } from "vitest";
import {
  coerceDefault,
  referencedParameters,
  specToRow,
  validateRows,
  type ParamRow,
} from "@/lib/parameters";

const row = (over: Partial<ParamRow> = {}): ParamRow => ({
  name: "p",
  type: "string",
  defaultText: "",
  description: "",
  ...over,
});

describe("coerceDefault", () => {
  it("treats empty text as no default (required)", () => {
    expect(coerceDefault("string", "")).toEqual({ ok: true, value: undefined });
    expect(coerceDefault("integer", "   ")).toEqual({ ok: true, value: undefined });
  });

  it("keeps strings verbatim (including whitespace)", () => {
    expect(coerceDefault("string", " a b ")).toEqual({ ok: true, value: " a b " });
  });

  it("parses integers and rejects non-integers", () => {
    expect(coerceDefault("integer", "42")).toEqual({ ok: true, value: 42 });
    expect(coerceDefault("integer", "-7")).toEqual({ ok: true, value: -7 });
    expect(coerceDefault("integer", "1.5")).toEqual({ ok: false });
    expect(coerceDefault("integer", "abc")).toEqual({ ok: false });
  });

  it("parses numbers and rejects garbage", () => {
    expect(coerceDefault("number", "2.5")).toEqual({ ok: true, value: 2.5 });
    expect(coerceDefault("number", "nope")).toEqual({ ok: false });
  });

  it("parses booleans from common tokens", () => {
    expect(coerceDefault("boolean", "true")).toEqual({ ok: true, value: true });
    expect(coerceDefault("boolean", "False")).toEqual({ ok: true, value: false });
    expect(coerceDefault("boolean", "maybe")).toEqual({ ok: false });
  });
});

describe("validateRows", () => {
  it("produces typed specs for valid rows", () => {
    const { errors, specs } = validateRows([
      row({ name: "keep", type: "integer", defaultText: "2", description: "rows" }),
      row({ name: "flag", type: "boolean", defaultText: "true" }),
    ]);
    expect(errors.size).toBe(0);
    expect(specs).toEqual([
      { name: "keep", type: "integer", default: 2, description: "rows" },
      { name: "flag", type: "boolean", default: true },
    ]);
  });

  it("omits default when none is given (required parameter)", () => {
    const { specs } = validateRows([row({ name: "x", type: "string" })]);
    expect(specs).toEqual([{ name: "x", type: "string" }]);
  });

  it("flags blank, malformed and duplicate names", () => {
    const { errors, specs } = validateRows([
      row({ name: "" }),
      row({ name: "1bad" }),
      row({ name: "ok" }),
      row({ name: "ok" }),
    ]);
    expect(specs).toBeNull();
    expect(errors.get(0)).toMatch(/required/i);
    expect(errors.get(1)).toMatch(/letters/i);
    expect(errors.get(3)).toMatch(/duplicate/i);
  });

  it("flags an uncoercible default", () => {
    const { errors, specs } = validateRows([row({ name: "n", type: "integer", defaultText: "x" })]);
    expect(specs).toBeNull();
    expect(errors.get(0)).toMatch(/valid integer/i);
  });
});

describe("specToRow", () => {
  it("renders default as text and null as empty", () => {
    expect(specToRow({ name: "n", type: "integer", default: 5 })).toMatchObject({ defaultText: "5" });
    expect(specToRow({ name: "n", type: "string", default: null })).toMatchObject({ defaultText: "" });
    expect(specToRow({ name: "n", type: "string" })).toMatchObject({ defaultText: "" });
  });
});

describe("referencedParameters", () => {
  it("collects {{ name }} references across nested config", () => {
    const refs = referencedParameters({
      a: "{{ keep }}",
      b: ["data/{{ date }}.csv", 3, true],
      c: { d: "no refs", e: "{{ keep }} and {{ extra }}" },
    });
    expect([...refs].sort()).toEqual(["date", "extra", "keep"]);
  });

  it("returns empty for configs without references", () => {
    expect(referencedParameters({ a: "x", b: 1 }).size).toBe(0);
  });
});
