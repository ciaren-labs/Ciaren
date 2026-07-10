import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsPage } from "../SettingsPage";
import type { AppSetting } from "@/features/settings/types";

const SETTINGS: AppSetting[] = [
  {
    key: "DEFAULT_ENGINE",
    env_var: "CIAREN_DEFAULT_ENGINE",
    label: "Default engine",
    description: "Dataframe engine used for runs that don't request one explicitly.",
    category: "Execution",
    value_type: "select",
    choices: ["pandas", "polars"],
    min_value: null,
    max_value: null,
    restart_required: false,
    value: "polars",
    source: "default",
    default_value: "polars",
    env_value: "polars",
  },
  {
    key: "MAX_UPLOAD_SIZE_MB",
    env_var: "CIAREN_MAX_UPLOAD_SIZE_MB",
    label: "Max upload size (MB)",
    description: "Largest dataset file the upload endpoint accepts.",
    category: "Datasets",
    value_type: "integer",
    choices: null,
    min_value: 1,
    max_value: 10240,
    restart_required: false,
    value: 250,
    source: "override",
    default_value: 100,
    env_value: 100,
  },
  {
    key: "SCHEDULER_MAX_CONCURRENT_RUNS",
    env_var: "CIAREN_SCHEDULER_MAX_CONCURRENT_RUNS",
    label: "Max concurrent scheduled runs",
    description: "Cap on simultaneous scheduled runs.",
    category: "Scheduler",
    value_type: "integer",
    choices: null,
    min_value: 1,
    max_value: 64,
    restart_required: true,
    value: 2,
    source: "env",
    default_value: 1,
    env_value: 2,
  },
];

type FetchCall = { url: string; method: string; body: unknown };
let calls: FetchCall[];

function stubFetch(overrides?: { putStatus?: number; putBody?: unknown }) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ url: String(url), method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (method === "GET") {
        return { ok: true, status: 200, json: async () => SETTINGS };
      }
      if (method === "PUT" && overrides?.putStatus && overrides.putStatus >= 400) {
        return {
          ok: false,
          status: overrides.putStatus,
          json: async () => overrides.putBody ?? { detail: "invalid value" },
        };
      }
      // PUT/DELETE echo the updated setting.
      const key = String(url).split("/").pop();
      const base = SETTINGS.find((s) => s.key === key)!;
      const updated =
        method === "DELETE"
          ? { ...base, value: base.env_value, source: "default" }
          : { ...base, value: (init?.body ? JSON.parse(String(init.body)) : {}).value, source: "override" };
      return { ok: true, status: 200, json: async () => updated };
    }),
  );
}

beforeEach(() => stubFetch());
afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe("SettingsPage", () => {
  it("renders settings grouped by category with source badges", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Execution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Datasets" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scheduler" })).toBeInTheDocument();

    expect(screen.getByLabelText("setting-DEFAULT_ENGINE")).toHaveValue("polars");
    expect(screen.getByLabelText("setting-MAX_UPLOAD_SIZE_MB")).toHaveValue(250);

    // Overridden setting shows the Custom badge + reset; env-sourced shows its badge.
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.getByText("From environment")).toBeInTheDocument();
    expect(screen.getByLabelText("reset-MAX_UPLOAD_SIZE_MB")).toBeInTheDocument();
    // Non-overridden settings offer no reset.
    expect(screen.queryByLabelText("reset-DEFAULT_ENGINE")).not.toBeInTheDocument();

    // Every row names its env var, and ONLY the overridden row warns that
    // the variable is being shadowed by the page's value.
    expect(screen.getByText("CIAREN_DEFAULT_ENGINE")).toBeInTheDocument();
    expect(screen.getByText("CIAREN_MAX_UPLOAD_SIZE_MB")).toBeInTheDocument();
    const shadowNotes = screen.getAllByText(/are ignored until you press Reset/i);
    expect(shadowNotes).toHaveLength(1);
    expect(shadowNotes[0]).toHaveTextContent("CIAREN_MAX_UPLOAD_SIZE_MB");
  });

  it("flags restart-required settings", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Scheduler" });
    expect(screen.getByText(/after the server restarts/i)).toBeInTheDocument();
  });

  it("saves an edited select via PUT and shows the new state", async () => {
    renderPage();
    const select = await screen.findByLabelText("setting-DEFAULT_ENGINE");
    await userEvent.selectOptions(select, "pandas");
    await userEvent.click(screen.getByLabelText("save-DEFAULT_ENGINE"));

    await waitFor(() => {
      const put = calls.find((c) => c.method === "PUT");
      expect(put).toBeDefined();
      expect(put!.url).toContain("/api/settings/DEFAULT_ENGINE");
      expect(put!.body).toEqual({ value: "pandas" });
    });
    // After the save the row reflects the override too (a second Custom badge,
    // next to the one MAX_UPLOAD_SIZE_MB already had).
    await waitFor(() => expect(screen.getAllByText("Custom")).toHaveLength(2));
  });

  it("sends integers as numbers, not strings", async () => {
    renderPage();
    const input = await screen.findByLabelText("setting-MAX_UPLOAD_SIZE_MB");
    await userEvent.clear(input);
    await userEvent.type(input, "500");
    await userEvent.click(screen.getByLabelText("save-MAX_UPLOAD_SIZE_MB"));
    await waitFor(() => {
      const put = calls.find((c) => c.method === "PUT");
      expect(put!.body).toEqual({ value: 500 });
    });
  });

  it("blocks out-of-range values client-side", async () => {
    renderPage();
    const input = await screen.findByLabelText("setting-MAX_UPLOAD_SIZE_MB");
    await userEvent.clear(input);
    await userEvent.type(input, "999999");
    expect(await screen.findByRole("alert")).toHaveTextContent("Must be at most 10240.");
    expect(screen.getByLabelText("save-MAX_UPLOAD_SIZE_MB")).toBeDisabled();
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("keeps the old value when the server rejects the write", async () => {
    stubFetch({ putStatus: 400, putBody: { detail: "MAX_UPLOAD_SIZE_MB must be at most 10240." } });
    renderPage();
    const input = await screen.findByLabelText("setting-MAX_UPLOAD_SIZE_MB");
    await userEvent.clear(input);
    await userEvent.type(input, "300");
    await userEvent.click(screen.getByLabelText("save-MAX_UPLOAD_SIZE_MB"));

    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    // The cached list is untouched on failure — the badge state stays as served.
    expect(screen.getByLabelText("setting-DEFAULT_ENGINE")).toHaveValue("polars");
  });

  it("resets an override via DELETE and shows the fallback value", async () => {
    renderPage();
    const reset = await screen.findByLabelText("reset-MAX_UPLOAD_SIZE_MB");
    await userEvent.click(reset);

    await waitFor(() => {
      const del = calls.find((c) => c.method === "DELETE");
      expect(del).toBeDefined();
      expect(del!.url).toContain("/api/settings/MAX_UPLOAD_SIZE_MB");
    });
    // Value falls back to the env/default value returned by the server.
    await waitFor(() => expect(screen.getByLabelText("setting-MAX_UPLOAD_SIZE_MB")).toHaveValue(100));
    expect(screen.queryByLabelText("reset-MAX_UPLOAD_SIZE_MB")).not.toBeInTheDocument();
  });

  it("shows the error state when the list fails to load", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 500, json: async () => ({ detail: "boom" }) })),
    );
    renderPage();
    expect(await screen.findByText("Couldn't load settings")).toBeInTheDocument();
  });
});
