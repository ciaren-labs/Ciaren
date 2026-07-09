import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function makeDataset(id: string, name: string, projectId: string) {
  return {
    id,
    name,
    source_type: "csv",
    dataset_kind: "input",
    project_id: projectId,
    is_disabled: false,
    latest_version: 1,
    version_count: 1,
    column_schema: [],
    created_at: "2026-06-01T00:00:00+00:00",
    updated_at: "2026-06-01T00:00:00+00:00",
  };
}

const DEFAULT_PROJECT = { id: "p-default", name: "Default", is_default: true, color: null };
const ANALYTICS_PROJECT = { id: "p-analytics", name: "Analytics", is_default: false, color: "blue" };

// A dataset named "sales.csv" already exists, but only in the Analytics
// project — the Default project has no dataset with that name.
const EXISTING_IN_ANALYTICS = makeDataset("d1", "sales.csv", "p-analytics");

let uploadSpy: (...args: unknown[]) => unknown;

vi.mock("@/lib/api", () => ({
  datasetsApi: {
    list: vi.fn(() => Promise.resolve([EXISTING_IN_ANALYTICS])),
    upload: (...args: unknown[]) => uploadSpy(...args),
  },
  projectsApi: { list: vi.fn(() => Promise.resolve([DEFAULT_PROJECT, ANALYTICS_PROJECT])) },
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

function fileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

describe("DatasetsPanel upload — project-scoped version detection", () => {
  it("does NOT warn about versioning when the name collides with a dataset in a different project", async () => {
    uploadSpy = vi.fn(() => new Promise(() => {})); // never resolves; we only check it was called
    const user = userEvent.setup();
    renderPanel();

    await screen.findByText(/Upload to project/);
    // Target stays the Default project (nothing selected) — "sales.csv" only
    // exists in Analytics, so this must go straight to upload, no warning.
    const file = new File(["a,b\n1,2"], "sales.csv", { type: "text/csv" });
    await user.upload(fileInput(), file);

    expect(screen.queryByText("Add new version?")).not.toBeInTheDocument();
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));
  });

  it("DOES warn about versioning when the name collides within the same (targeted) project", async () => {
    uploadSpy = vi.fn(() => new Promise(() => {}));
    const user = userEvent.setup();
    renderPanel();

    await screen.findByText(/Upload to project/);
    // Switch the upload target to Analytics, where "sales.csv" already exists.
    // "Analytics" also appears as the dataset-group section title further down
    // the page, so scope to the dropdown's own option (rendered first in the
    // DOM, since the upload row comes before the grouped dataset list).
    await user.click(screen.getByText("Default project"));
    const analyticsOption = (await screen.findAllByText("Analytics"))[0];
    await user.click(analyticsOption);

    const file = new File(["a,b\n1,2"], "sales.csv", { type: "text/csv" });
    await user.upload(fileInput(), file);

    expect(await screen.findByText("Add new version?")).toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });
});
