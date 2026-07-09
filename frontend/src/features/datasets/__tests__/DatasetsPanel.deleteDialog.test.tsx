import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const DATASET = {
  id: "d1",
  name: "sales.csv",
  source_type: "csv",
  dataset_kind: "input",
  project_id: "p-default",
  is_disabled: false,
  latest_version: 1,
  version_count: 1,
  column_schema: [],
  created_at: "2026-06-01T00:00:00+00:00",
  updated_at: "2026-06-01T00:00:00+00:00",
};
const DEFAULT_PROJECT = { id: "p-default", name: "Default", is_default: true, color: null };
const AFFECTED_FLOW = { id: "f1", name: "Nightly ETL" };

vi.mock("@/lib/api", () => ({
  datasetsApi: {
    list: vi.fn(() => Promise.resolve([DATASET])),
    flows: vi.fn(() => Promise.resolve([AFFECTED_FLOW])),
    remove: vi.fn(() => Promise.resolve()),
  },
  projectsApi: { list: vi.fn(() => Promise.resolve([DEFAULT_PROJECT])) },
}));

import { DatasetsPanel } from "../DatasetsPanel";

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DatasetsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DatasetsPanel delete dialog — soft-delete copy", () => {
  afterEach(() => vi.clearAllMocks());

  it("describes a restorable soft-delete and disabled (not failing) flows", async () => {
    const user = userEvent.setup();
    renderPanel();

    await screen.findByText("sales.csv");
    await user.click(screen.getByTitle("Delete dataset"));

    // The backend default DELETE is a soft-delete (row + files retained,
    // restorable). The dialog must not claim a permanent DB wipe...
    await screen.findByText(/soft-delete/i);
    expect(screen.getByText(/can be restored later/i)).toBeInTheDocument();
    expect(screen.queryByText(/permanently delete/i)).not.toBeInTheDocument();

    // ...and dependent flows are DISABLED by the cascade, not left to "fail to run".
    expect(screen.getByText(/will also be disabled/i)).toBeInTheDocument();
    expect(screen.getByText("Nightly ETL")).toBeInTheDocument();
    expect(screen.queryByText(/fail to run/i)).not.toBeInTheDocument();
  });
});
