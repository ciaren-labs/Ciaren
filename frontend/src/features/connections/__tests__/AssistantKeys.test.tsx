import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AssistantKey } from "@/features/assistant/api";
import { AssistantKeys } from "../components/AssistantKeys";

const api = vi.hoisted(() => ({
  providers: vi.fn(),
  keychain: vi.fn(),
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  activate: vi.fn(),
  remove: vi.fn(),
  status: vi.fn(),
}));

vi.mock("@/features/assistant/api", () => ({
  keys: {
    providers: api.providers,
    keychain: api.keychain,
    list: api.list,
    create: api.create,
    update: api.update,
    activate: api.activate,
    remove: api.remove,
  },
  status: api.status,
}));

const row = (over: Partial<AssistantKey>): AssistantKey => ({
  id: "k1",
  name: "Work",
  provider: "openai",
  model: "gpt-5",
  effort: "default",
  is_enabled: true,
  is_active: true,
  created_at: "2026-11-27T10:00:00",
  updated_at: "2026-11-27T10:00:00",
  ...over,
});

function setup(rows: AssistantKey[], keychain: { available: boolean; detail?: string } = { available: true }) {
  api.keychain.mockResolvedValue(keychain);
  api.providers.mockResolvedValue([
    { id: "openai", label: "OpenAI", models: ["gpt-5-mini", "gpt-5"], efforts: ["low", "high"] },
    { id: "opencode", label: "OpenCode Console", models: ["kimi-k2.6"], efforts: [] },
  ]);
  api.list.mockResolvedValue(rows);
  api.status.mockResolvedValue({ provider: "off" });
  for (const fn of [api.create, api.update, api.activate, api.remove]) fn.mockResolvedValue(rows[0]);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AssistantKeys />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("Assistant API keys", () => {
  it("uses one enabled key at a time and toggles keys on and off", async () => {
    setup([
      row({}),
      row({ id: "k2", name: "Personal", is_active: false, model: "gpt-6-preview" }),
      row({ id: "k3", name: "Old", is_active: false, is_enabled: false }),
    ]);
    const work = await screen.findByRole("radio", { name: /Work/ });
    expect(work).toBeChecked();
    expect(screen.getByRole("radio", { name: /Old/ })).toBeDisabled();
    expect(screen.getByText(/gpt-6-preview \(custom model\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Personal/ }));
    await waitFor(() => expect(api.activate).toHaveBeenCalledWith("k2", expect.anything()));
    fireEvent.click(screen.getAllByRole("switch", { name: "Enabled" })[0]);
    await waitFor(() => expect(api.update).toHaveBeenCalledWith("k1", { is_enabled: false }));
  });

  it("asks for the storage notice before saving a new key with a typed model", async () => {
    setup([]);
    const add = await screen.findByRole("button", { name: /add api key/i });
    await waitFor(() => expect(add).toBeEnabled());
    fireEvent.click(add);
    const dialog = await screen.findByRole("dialog", { name: "Add an assistant API key" });
    const form = within(dialog);
    fireEvent.change(form.getByLabelText("Name"), { target: { value: "Team" } });
    expect(within(form.getByLabelText("Model")).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "gpt-5-mini",
      "gpt-5",
      "Other model…",
    ]);
    fireEvent.change(form.getByLabelText("Model"), { target: { value: "__other" } });
    fireEvent.change(form.getByLabelText(/Model name/), { target: { value: "gpt-6" } });
    fireEvent.change(form.getByLabelText("API key"), { target: { value: "sk-synthetic" } });
    expect(form.getByRole("note")).toHaveTextContent("stored only on the computer that runs Ciaren");
    fireEvent.click(form.getByRole("button", { name: "Save key" }));
    expect(await form.findByRole("alert")).toHaveTextContent("Confirm the storage notice");
    expect(api.create).not.toHaveBeenCalled();
    fireEvent.click(form.getByRole("checkbox", { name: /I understand/ }));
    fireEvent.click(form.getByRole("button", { name: "Save key" }));
    await waitFor(() =>
      expect(api.create).toHaveBeenCalledWith({
        name: "Team",
        provider: "openai",
        model: "gpt-6",
        effort: "default",
        key: "sk-synthetic",
        acknowledged: true,
      }),
    );
    // The dialog, and the key typed into it, are gone after saving.
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("explains how to enable saving when the computer has no keychain support", async () => {
    setup([], { available: false, detail: "Install the OS keychain support with: pip install ciaren[keyring]" });
    const note = await screen.findByRole("note");
    expect(note).toHaveTextContent("pip install ciaren[keyring]");
    expect(screen.getByRole("button", { name: /add api key/i })).toBeDisabled();
  });

  it("edits a key without resending it and confirms removal", async () => {
    setup([row({})]);
    fireEvent.click(await screen.findByRole("button", { name: "Edit Work" }));
    const form = within(await screen.findByRole("dialog", { name: "Edit Work" }));
    expect(form.getByLabelText(/Provider/)).toBeDisabled();
    expect(form.queryByRole("note")).not.toBeInTheDocument();
    fireEvent.change(form.getByLabelText("Model"), { target: { value: "gpt-5-mini" } });
    fireEvent.change(form.getByLabelText("Reasoning effort"), { target: { value: "high" } });
    fireEvent.click(form.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(api.update).toHaveBeenCalledWith("k1", { name: "Work", model: "gpt-5-mini", effort: "high" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove Work" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove key" }));
    await waitFor(() => expect(api.remove).toHaveBeenCalledWith("k1"));
  });
});
