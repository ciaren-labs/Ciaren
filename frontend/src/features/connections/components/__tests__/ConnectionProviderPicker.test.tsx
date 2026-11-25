import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ProviderInfo } from "@/features/connections/types";
import { ProviderSection } from "../ConnectionProviderPicker";

const AVAILABLE: ProviderInfo = {
  name: "postgresql",
  label: "PostgreSQL",
  kind: "sql",
  available: true,
  driver_module: "psycopg",
  extra: "postgres",
  default_port: 5432,
  needs_host: true,
  needs_auth: true,
  supports_query: true,
  needs_bucket: false,
  needs_region: false,
  needs_endpoint: false,
};

const UNAVAILABLE: ProviderInfo = {
  ...AVAILABLE,
  name: "snowflake",
  label: "Snowflake",
  available: false,
  extra: "snowflake",
};

describe("ProviderSection", () => {
  const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");

  afterEach(() => {
    if (originalClipboard) {
      Object.defineProperty(navigator, "clipboard", originalClipboard);
    } else {
      delete (navigator as { clipboard?: Clipboard }).clipboard;
    }
  });

  it("renders nothing when the provider list is empty", () => {
    const { container } = render(
      <ProviderSection label="Databases" providers={[]} onSelect={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("calls onSelect when an available provider card is clicked", () => {
    const onSelect = vi.fn();
    render(<ProviderSection label="Databases" providers={[AVAILABLE]} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("PostgreSQL"));
    expect(onSelect).toHaveBeenCalledWith(AVAILABLE);
  });

  it("does not call onSelect for an unavailable provider, and shows the install hint", () => {
    const onSelect = vi.fn();
    render(<ProviderSection label="Databases" providers={[UNAVAILABLE]} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Snowflake"));
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Snowflake/ })).toBeDisabled();
    expect(screen.getByText("pip install ciaren[snowflake]")).toBeInTheDocument();
  });

  it("copies the install command to the clipboard without triggering onSelect", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    // defineProperty also replaces the getter-only stub that userEvent.setup()
    // installs, so this test does not depend on test execution order.
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const onSelect = vi.fn();

    render(<ProviderSection label="Databases" providers={[UNAVAILABLE]} onSelect={onSelect} />);
    fireEvent.click(screen.getByTitle("Copy install command"));

    expect(writeText).toHaveBeenCalledWith("pip install ciaren[snowflake]");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("skips the unavailable provider button when tabbing, but reaches the copy button", async () => {
    const user = userEvent.setup();
    render(<ProviderSection label="Databases" providers={[UNAVAILABLE]} onSelect={vi.fn()} />);

    await user.tab();

    expect(screen.getByRole("button", { name: /Snowflake/ })).not.toHaveFocus();
    expect(screen.getByTitle("Copy install command")).toHaveFocus();
  });

  it("does not render an install hint for an unavailable provider with no extra", () => {
    render(
      <ProviderSection
        label="Databases"
        providers={[{ ...UNAVAILABLE, extra: null }]}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.queryByTitle("Copy install command")).not.toBeInTheDocument();
  });
});
