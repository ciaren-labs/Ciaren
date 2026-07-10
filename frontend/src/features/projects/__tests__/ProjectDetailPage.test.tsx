import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const PROJECT = {
  id: "p1",
  name: "Demo",
  description: null,
  color: "emerald",
  is_default: false,
  is_disabled: false,
  dataset_count: 0,
  flow_count: 0,
  created_at: "2026-06-01T00:00:00+00:00",
  updated_at: "2026-06-01T00:00:00+00:00",
};

let createFlowSpy: (...args: unknown[]) => unknown;

vi.mock("@/features/projects/api", () => ({
  projectsApi: { list: vi.fn(() => Promise.resolve([PROJECT])) },
}));
vi.mock("@/features/flows/api", () => ({
  flowsApi: {
    list: vi.fn(() => Promise.resolve([])),
    create: (...args: unknown[]) => createFlowSpy(...args),
  },
}));
vi.mock("@/features/datasets/api", () => ({
  datasetsApi: { list: vi.fn(() => Promise.resolve([])) },
}));

import { ProjectDetailPage } from "../ProjectDetailPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/projects/p1"]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProjectDetailPage flow creation", () => {
  it("ignores a rapid second Enter press while the first create is still pending", async () => {
    createFlowSpy = vi.fn(() => new Promise(() => {})); // never resolves
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("tab", { name: /Flows/i });
    await user.click(screen.getByRole("tab", { name: /Flows/i }));

    const input = screen.getByPlaceholderText("New flow name…");
    await user.type(input, "My Flow");
    await user.keyboard("{Enter}");
    // A second Enter before the first request settles must not fire again —
    // the "New flow" button disabling on isPending doesn't protect a raw
    // keydown handler on the text input, which has no disabled state of its own.
    await user.keyboard("{Enter}");

    expect(createFlowSpy).toHaveBeenCalledTimes(1);
  });
});
