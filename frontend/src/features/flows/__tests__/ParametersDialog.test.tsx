import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ParametersDialog } from "../ParametersDialog";
import type { ParameterSpec } from "@/lib/types";

function renderDialog(value: ParameterSpec[] = []) {
  const onChange = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <ParametersDialog open value={value} onChange={onChange} onOpenChange={onOpenChange} />,
  );
  return { onChange, onOpenChange };
}

describe("ParametersDialog", () => {
  it("loads existing specs as editable rows", () => {
    renderDialog([{ name: "keep", type: "integer", default: 2 }]);
    expect(screen.getByLabelText("parameter-name-0")).toHaveValue("keep");
    expect(screen.getByLabelText("parameter-type-0")).toHaveValue("integer");
    expect(screen.getByLabelText("parameter-default-0")).toHaveValue("2");
  });

  it("adds a parameter and saves it with a typed default", async () => {
    const user = userEvent.setup();
    const { onChange, onOpenChange } = renderDialog([]);

    await user.click(screen.getByRole("button", { name: /add parameter/i }));
    await user.type(screen.getByLabelText("parameter-name-0"), "keep");
    await user.selectOptions(screen.getByLabelText("parameter-type-0"), "integer");
    await user.type(screen.getByLabelText("parameter-default-0"), "5");
    await user.click(screen.getByRole("button", { name: /save parameters/i }));

    expect(onChange).toHaveBeenCalledWith([{ name: "keep", type: "integer", default: 5 }]);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("blocks save and shows an error for an invalid name", async () => {
    const user = userEvent.setup();
    const { onChange } = renderDialog([]);

    await user.click(screen.getByRole("button", { name: /add parameter/i }));
    await user.type(screen.getByLabelText("parameter-name-0"), "1bad");

    expect(screen.getByText(/letters, digits, underscores/i)).toBeInTheDocument();
    const save = screen.getByRole("button", { name: /save parameters/i });
    expect(save).toBeDisabled();
    await user.click(save);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("blocks save for an uncoercible default", async () => {
    const user = userEvent.setup();
    renderDialog([]);
    await user.click(screen.getByRole("button", { name: /add parameter/i }));
    await user.type(screen.getByLabelText("parameter-name-0"), "n");
    await user.selectOptions(screen.getByLabelText("parameter-type-0"), "integer");
    await user.type(screen.getByLabelText("parameter-default-0"), "abc");

    expect(screen.getByText(/valid integer/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save parameters/i })).toBeDisabled();
  });

  it("removes a parameter row", async () => {
    const user = userEvent.setup();
    renderDialog([{ name: "keep", type: "integer", default: 2 }]);
    await user.click(screen.getByRole("button", { name: "remove-parameter-0" }));
    expect(screen.queryByLabelText("parameter-name-0")).not.toBeInTheDocument();
  });
});
