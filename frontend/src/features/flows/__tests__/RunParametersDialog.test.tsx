import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunParametersDialog } from "../RunParametersDialog";
import type { ParameterSpec } from "@/lib/types/shared";

const SPECS: ParameterSpec[] = [
  { name: "keep", type: "integer", default: 2, description: "rows kept" },
  { name: "label", type: "string" }, // required (no default)
];

function renderDialog(specs = SPECS, extra = {}) {
  const onSubmit = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <RunParametersDialog
      open
      specs={specs}
      onSubmit={onSubmit}
      onOpenChange={onOpenChange}
      {...extra}
    />,
  );
  return { onSubmit, onOpenChange };
}

describe("RunParametersDialog", () => {
  it("pre-fills defaults and blocks run until required fields are filled", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog();

    expect(screen.getByLabelText("value-keep")).toHaveValue("2");
    expect(screen.getByLabelText("value-label")).toHaveValue("");

    const run = screen.getByRole("button", { name: /run/i });
    expect(run).toBeDisabled(); // required `label` is empty

    await user.type(screen.getByLabelText("value-label"), "june");
    expect(run).toBeEnabled();
    await user.click(run);
    expect(onSubmit).toHaveBeenCalledWith({ keep: 2, label: "june" });
  });

  it("omits a blank optional field so its default is used", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog([{ name: "keep", type: "integer", default: 2 }]);

    await user.clear(screen.getByLabelText("value-keep"));
    await user.click(screen.getByRole("button", { name: /run/i }));
    // keep left blank → omitted → backend falls back to the default.
    expect(onSubmit).toHaveBeenCalledWith({});
  });

  it("blocks run on an invalid typed value", async () => {
    const user = userEvent.setup();
    renderDialog([{ name: "keep", type: "integer", default: 2 }]);

    await user.clear(screen.getByLabelText("value-keep"));
    await user.type(screen.getByLabelText("value-keep"), "1.5");
    expect(screen.getByText(/valid integer/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run/i })).toBeDisabled();
  });

  it("pre-fills supplied override values over defaults", () => {
    renderDialog([{ name: "keep", type: "integer", default: 2 }], {
      initialValues: { keep: 9 },
      submitLabel: "Save",
    });
    expect(screen.getByLabelText("value-keep")).toHaveValue("9");
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });
});
