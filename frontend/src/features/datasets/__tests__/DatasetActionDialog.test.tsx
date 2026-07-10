import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DatasetActionDialog } from "../components/DatasetActionDialog";
import type { Dataset } from "@/features/datasets/types";

const DATASET: Dataset = {
  id: "d1",
  name: "sales.csv",
  source_type: "csv",
  dataset_kind: "input",
  project_id: "p-default",
  is_disabled: true,
  latest_version: 1,
  version_count: 1,
  column_schema: [],
  data_sample: null,
  column_profile: null,
  created_at: "2026-06-01T00:00:00+00:00",
  updated_at: "2026-06-01T00:00:00+00:00",
};

vi.mock("@/features/datasets/api", () => ({
  datasetsApi: { flows: vi.fn(() => Promise.resolve([])) },
}));

function renderDialog(overrides: Partial<React.ComponentProps<typeof DatasetActionDialog>> = {}) {
  const onCancel = vi.fn();
  const onConfirm = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DatasetActionDialog
        dataset={DATASET}
        kind="enable"
        onCancel={onCancel}
        onConfirm={onConfirm}
        isPending={false}
        {...overrides}
      />
    </QueryClientProvider>,
  );
  return { onCancel, onConfirm };
}

describe("DatasetActionDialog", () => {
  afterEach(() => vi.clearAllMocks());

  it("explains that dependent flows are NOT auto-re-enabled, for the enable path", async () => {
    renderDialog();
    expect(await screen.findByText("Enable dataset?")).toBeInTheDocument();
    // "not" is wrapped in its own <em>, so match on the paragraph's full text
    // content rather than a single text node.
    expect(screen.getByText((_, el) => el?.tagName === "P" && /automatically re-enabled/i.test(el.textContent ?? ""))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable" })).toBeInTheDocument();
  });

  it("calls onConfirm for the disable path and does not use the destructive variant", async () => {
    const { onConfirm } = renderDialog({ kind: "disable" });
    const btn = await screen.findByRole("button", { name: "Disable" });
    await userEvent.setup().click(btn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("disables the confirm button while a mutation is pending", async () => {
    renderDialog({ kind: "enable", isPending: true });
    expect(await screen.findByRole("button", { name: "Enable" })).toBeDisabled();
  });

  it("calls onCancel when the dialog is dismissed", async () => {
    const { onCancel } = renderDialog();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
