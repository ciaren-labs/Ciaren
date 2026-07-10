// Schema-driven config forms: the field dialect plugins declare renders real,
// typed controls, and defaults inferred from a node's default config keep every
// plugin node configurable even without a config_schema.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { SchemaConfigFields, fieldsFromDefaults } from "../SchemaConfigFields";
import type { ConfigField } from "@/lib/types/shared";

const FIELDS: ConfigField[] = [
  { key: "base_url", label: "Base URL", type: "string", required: true, placeholder: "https://…" },
  { key: "page_size", type: "integer", min: 1 },
  { key: "verify_tls", type: "boolean", default: true },
  { key: "auth_style", type: "select", options: ["none", "bearer"] },
  { key: "columns", type: "string_list" },
  { key: "token_env", type: "string", secret: true },
];

describe("SchemaConfigFields", () => {
  it("renders a control per field with labels and required markers", () => {
    render(<SchemaConfigFields fields={FIELDS} config={{}} onChange={() => {}} />);
    expect(screen.getByText("Base URL *")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("https://…")).toBeInTheDocument();
    expect(screen.getByText("page_size")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toBeChecked(); // verify_tls default
    expect(screen.getByRole("combobox")).toBeInTheDocument(); // auth_style select
  });

  it("emits typed values on change", () => {
    const onChange = vi.fn();
    render(<SchemaConfigFields fields={FIELDS} config={{}} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("https://…"), {
      target: { value: "https://api.example.com" },
    });
    expect(onChange).toHaveBeenCalledWith("base_url", "https://api.example.com");

    fireEvent.change(screen.getByText("page_size").closest("div")!.parentElement!.querySelector("input")!, {
      target: { value: "25" },
    });
    expect(onChange).toHaveBeenCalledWith("page_size", 25);

    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith("verify_tls", false);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "bearer" } });
    expect(onChange).toHaveBeenCalledWith("auth_style", "bearer");
  });

  it("prefers the saved config value over the field default", () => {
    render(
      <SchemaConfigFields
        fields={[{ key: "verify_tls", type: "boolean", default: true }]}
        config={{ verify_tls: false }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("masks secret fields", () => {
    const { container } = render(
      <SchemaConfigFields
        fields={[{ key: "token_env", type: "string", secret: true }]}
        config={{}}
        onChange={() => {}}
      />,
    );
    expect(container.querySelector('input[type="password"]')).toBeTruthy();
  });

  it("shows field errors", () => {
    render(
      <SchemaConfigFields
        fields={[{ key: "base_url", label: "Base URL" }]}
        config={{}}
        errors={{ base_url: "Required" }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText("Required")).toBeInTheDocument();
  });
});

describe("fieldsFromDefaults", () => {
  it("infers field kinds from default values", () => {
    const fields = fieldsFromDefaults({
      name: "world",
      max_iter: 200,
      stratify: true,
      feature_columns: [],
    });
    expect(fields).toEqual([
      { key: "name", type: "string", default: "world" },
      { key: "max_iter", type: "number", default: 200 },
      { key: "stratify", type: "boolean", default: true },
      { key: "feature_columns", type: "string_list", default: [] },
    ]);
  });
});
