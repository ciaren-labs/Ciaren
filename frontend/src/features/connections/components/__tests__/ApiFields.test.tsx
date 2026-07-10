import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ConnectionCreate } from "@/features/connections/types";
import { ApiFields } from "../ApiFields";

vi.mock("../../hooks", () => ({
  useKeyringAvailability: () => ({ data: { available: true, backend: null, detail: null } }),
  useStoreKeyringSecret: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
  }),
}));

const EMPTY: ConnectionCreate = {
  name: "",
  provider: "rest_api",
  host: "",
  port: null,
  database: "",
  username: "",
  password_env: "",
  options: null,
};

function Harness() {
  const [form, setForm] = useState<ConnectionCreate>(EMPTY);
  const set = (patch: Partial<ConnectionCreate>) => setForm((f) => ({ ...f, ...patch }));
  const setOptionValue = (key: string, value: unknown) =>
    setForm((f) => ({ ...f, options: { ...(f.options ?? {}), [key]: value === "" ? undefined : value } }));
  return <ApiFields form={form} set={set} setOptionValue={setOptionValue} />;
}

describe("ApiFields", () => {
  it("splits, trims, and drops empty entries when parsing the endpoints list", () => {
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText("users, orders, invoices"), {
      target: { value: " users ,, orders ,  " },
    });
    // Re-rendered from the harness's own state — the input reflects the parsed list.
    expect(screen.getByPlaceholderText("users, orders, invoices")).toHaveValue("users, orders");
  });

  it("does not show the secret field until an auth method other than none is picked", () => {
    render(<Harness />);
    expect(screen.queryByText("Secret", { selector: "label" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "bearer" } });
    expect(screen.getByText("Secret", { selector: "label" })).toBeInTheDocument();
    // Bearer doesn't need a username field (only "basic" does).
    expect(screen.queryByText("Username", { selector: "label" })).not.toBeInTheDocument();
  });

  it("shows a username field only for basic auth", () => {
    render(<Harness />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "basic" } });
    expect(screen.getByText("Username", { selector: "label" })).toBeInTheDocument();
  });

  it("keeps advanced options collapsed until the toggle is clicked", () => {
    render(<Harness />);
    expect(screen.queryByText("Custom headers")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Advanced options/));
    expect(screen.getByText("Custom headers")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Hide advanced options"));
    expect(screen.queryByText("Custom headers")).not.toBeInTheDocument();
  });

  it("round-trips custom headers between the key:value textarea and options", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText(/Advanced options/));
    fireEvent.change(screen.getByPlaceholderText(/X-Tenant: acme/), {
      target: { value: "X-Tenant: acme\nAccept-Language: en" },
    });
    expect(screen.getByPlaceholderText(/X-Tenant: acme/)).toHaveValue(
      "X-Tenant: acme\nAccept-Language: en",
    );
  });

  it("verify TLS checkbox stays checked by default and unchecks to store false", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText(/Advanced options/));
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
  });
});
