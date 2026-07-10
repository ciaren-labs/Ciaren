import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ConnectionCreate, ProviderInfo } from "@/features/connections/types";
import { StorageFields } from "../StorageFields";

vi.mock("../../hooks", () => ({
  useKeyringAvailability: () => ({ data: { available: true, backend: null, detail: null } }),
  useStoreKeyringSecret: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
  }),
}));

const EMPTY: ConnectionCreate = {
  name: "",
  provider: "s3",
  host: "",
  port: null,
  database: "",
  username: "",
  password_env: "",
  options: null,
};

function provider(name: string, kind = "storage"): ProviderInfo {
  return {
    name,
    label: name,
    kind,
    available: true,
    driver_module: null,
    extra: null,
    default_port: null,
    needs_host: false,
    needs_auth: true,
    supports_query: false,
    needs_bucket: true,
    needs_region: false,
    needs_endpoint: false,
  };
}

function Harness({ provider: p }: { provider: ProviderInfo }) {
  const [form, setForm] = useState<ConnectionCreate>({ ...EMPTY, provider: p.name });
  const set = (patch: Partial<ConnectionCreate>) => setForm((f) => ({ ...f, ...patch }));
  const setOption = (key: string, value: string) =>
    setForm((f) => ({ ...f, options: { ...(f.options ?? {}), [key]: value || undefined } }));
  return (
    <TooltipProvider>
      <StorageFields form={form} provider={p} set={set} setOption={setOption} />
    </TooltipProvider>
  );
}

describe("StorageFields", () => {
  it("renders a single folder-path field for the local provider", () => {
    render(<Harness provider={provider("local")} />);
    expect(screen.getByText("Folder path")).toBeInTheDocument();
    // No secret / access-key fields for local storage.
    expect(screen.queryByText("Access Key ID")).not.toBeInTheDocument();
  });

  it("renders bucket, access key, secret, and optional region/endpoint for s3", () => {
    render(<Harness provider={provider("s3")} />);
    expect(screen.getByText("Bucket")).toBeInTheDocument();
    expect(screen.getByText("Access Key ID")).toBeInTheDocument();
    expect(screen.getByText("Secret Access Key")).toBeInTheDocument();
    expect(screen.getByText("Region")).toBeInTheDocument();
    expect(screen.getByText("Endpoint URL")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("us-east-1"), { target: { value: "eu-west-1" } });
    expect(screen.getByPlaceholderText("us-east-1")).toHaveValue("eu-west-1");
  });

  it("renders a project-id field and disables the keychain affordance for gcs", () => {
    render(<Harness provider={provider("gcs")} />);
    expect(screen.getByText("Bucket")).toBeInTheDocument();
    expect(screen.getByText("Project ID")).toBeInTheDocument();
    expect(screen.getByText("Service account key")).toBeInTheDocument();
    // gcs holds a credentials-file path, not a raw secret, so allowKeychain=false.
    expect(screen.queryByText(/Store a value in the OS keychain/)).not.toBeInTheDocument();
  });

  it("returns null for an unrecognized storage provider name", () => {
    const { container } = render(<Harness provider={provider("unknown_storage")} />);
    expect(container).toBeEmptyDOMElement();
  });
});
