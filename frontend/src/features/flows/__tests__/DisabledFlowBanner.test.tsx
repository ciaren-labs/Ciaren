import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DisabledFlowBanner } from "../components/DisabledFlowBanner";

describe("DisabledFlowBanner", () => {
  it("explains the flow is read-only", () => {
    render(<DisabledFlowBanner onReEnable={vi.fn()} />);
    expect(screen.getByText(/read-only and cannot be run/)).toBeInTheDocument();
  });

  it("calls onReEnable when the Re-enable link is clicked", async () => {
    const onReEnable = vi.fn();
    render(<DisabledFlowBanner onReEnable={onReEnable} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Re-enable" }));
    expect(onReEnable).toHaveBeenCalledTimes(1);
  });
});
