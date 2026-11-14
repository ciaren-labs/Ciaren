import { describe, expect, it, vi } from "vitest";
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
    expect(screen.getByText("pip install ciaren[snowflake]")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Snowflake/ })).toBeDisabled();
  });

  it("copies the install command to the clipboard without triggering onSelect", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const onSelect = vi.fn();

    render(<ProviderSection label="Databases" providers={[UNAVAILABLE]} onSelect={onSelect} />);
    fireEvent.click(screen.getByTitle("Copy install command"));

    expect(writeText).toHaveBeenCalledWith("pip install ciaren[snowflake]");
    expect(onSelect).not.toHaveBeenCalled();
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

  it("keeps the available provider button enabled and skips the unavailable one when tabbing", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ProviderSection
        label="Databases"
        providers={[AVAILABLE, UNAVAILABLE]}
        onSelect={onSelect}
      />,
    );

    // The first Tab lands on the available provider button.
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: /PostgreSQL/ }),
    );

    // The next Tab skips the natively disabled unavailable provider button
    // in between and reaches the install-command copy button, which stays
    // usable without selecting the provider.
    await user.tab();
    expect(document.activeElement).toBe(screen.getByTitle("Copy install command"));
  });
});
