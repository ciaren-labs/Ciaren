import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ApiError } from "@/lib/api/client";
import { SecretRefField } from "../SecretRefField";
import { useKeyringAvailability, useStoreKeyringSecret } from "../../hooks";

vi.mock("../../hooks", () => ({
  useKeyringAvailability: vi.fn(() => ({ data: { available: true, backend: null, detail: null } })),
  useStoreKeyringSecret: vi.fn(() => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
  })),
}));

function renderField(onChange = vi.fn()) {
  render(
    <SecretRefField
      label="Password secret"
      value=""
      onChange={onChange}
      suggestedName="my connection"
    />,
  );
  return onChange;
}

describe("SecretRefField", () => {
  afterEach(() => {
    vi.mocked(useKeyringAvailability).mockReturnValue({
      data: { available: true, backend: null, detail: null },
    } as any);
  });

  it("does not render the keychain affordance when allowKeychain is false, even if available", () => {
    render(
      <SecretRefField
        label="Service account key"
        value=""
        onChange={vi.fn()}
        suggestedName="gcs"
        allowKeychain={false}
      />,
    );
    expect(screen.queryByText(/Store a value in the OS keychain/)).not.toBeInTheDocument();
  });

  it("slugifies the suggested name into a keychain entry name when opening the panel", () => {
    renderField();
    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    expect(screen.getByPlaceholderText("pg-main")).toHaveValue("my-connection");
  });

  it("clears the typed secret value on cancel without saving", () => {
    renderField();
    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    fireEvent.change(screen.getByPlaceholderText("the password / token"), {
      target: { value: "hunter2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByText("Store a secret in the OS keychain")).not.toBeInTheDocument();

    // Reopening starts from a blank value — the prior input wasn't retained.
    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    expect(screen.getByPlaceholderText("the password / token")).toHaveValue("");
  });

  it("shows a confirm prompt on a 409 name conflict and retries with overwrite=true on confirm", async () => {
    const mutateAsync = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('Entry "pg-main" already exists', 409))
      .mockResolvedValueOnce({ name: "pg-main", exists: true, reference: "keyring:pg-main" });
    vi.mocked(useStoreKeyringSecret).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync,
      reset: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: undefined,
    } as any);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChange = renderField();

    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    fireEvent.change(screen.getByPlaceholderText("the password / token"), {
      target: { value: "hunter2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save to keychain/i }));

    await screen.findByText(/Saved to the OS keychain/);
    expect(confirmSpy).toHaveBeenCalled();
    expect(mutateAsync).toHaveBeenCalledTimes(2);
    expect(mutateAsync).toHaveBeenNthCalledWith(2, {
      name: "my-connection",
      value: "hunter2",
      overwrite: true,
    });
    expect(onChange).toHaveBeenCalledWith("keyring:pg-main");

    confirmSpy.mockRestore();
  });

  it("does not retry on a 409 conflict when the user declines to overwrite", async () => {
    const mutateAsync = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('Entry "pg-main" already exists', 409));
    vi.mocked(useStoreKeyringSecret).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync,
      reset: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: undefined,
    } as any);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderField();

    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    fireEvent.change(screen.getByPlaceholderText("the password / token"), {
      target: { value: "hunter2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save to keychain/i }));

    await vi.waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    expect(mutateAsync).toHaveBeenCalledTimes(1);
    // The panel stays open — no "saved" confirmation appeared.
    expect(screen.queryByText(/Saved to the OS keychain/)).not.toBeInTheDocument();

    confirmSpy.mockRestore();
  });

  it("shows a generic error message for a non-409, non-ApiError failure", async () => {
    const mutateAsync = vi.fn().mockRejectedValueOnce(new Error("network down"));
    vi.mocked(useStoreKeyringSecret).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync,
      reset: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: undefined,
    } as any);
    renderField();

    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    fireEvent.change(screen.getByPlaceholderText("the password / token"), {
      target: { value: "hunter2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save to keychain/i }));

    expect(await screen.findByText("Could not save to the keychain.")).toBeInTheDocument();
  });
});
