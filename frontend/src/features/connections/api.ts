import { request } from "@/lib/api/client";
import type { CsvDialect } from "@/lib/csvDialect";
import type {
  Connection,
  ConnectionCreate,
  ConnectionTestResult,
  ConnectionUpdate,
  KeyringAvailability,
  KeyringSecretStatus,
  KeyringSecretWrite,
  ProviderInfo,
  TableInfo,
} from "./types";

export const connectionsApi = {
  list: () => request<Connection[]>("/connections"),
  get: (id: string) => request<Connection>(`/connections/${id}`),
  providers: () => request<ProviderInfo[]>("/connections/providers"),
  create: (body: ConnectionCreate) =>
    request<Connection>("/connections", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: ConnectionUpdate) =>
    request<Connection>(`/connections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: string, force = false) =>
    request<void>(`/connections/${id}${force ? "?force=true" : ""}`, { method: "DELETE" }),
  test: (id: string) =>
    request<ConnectionTestResult>(`/connections/${id}/test`, { method: "POST" }),
  testConfig: (body: ConnectionCreate) =>
    request<ConnectionTestResult>("/connections/test-config", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  tables: (id: string) => request<TableInfo[]>(`/connections/${id}/tables`),
  objects: (id: string, prefix?: string) =>
    request<string[]>(`/connections/${id}/objects${prefix ? `?prefix=${encodeURIComponent(prefix)}` : ""}`),
  objectDialect: (id: string, path: string, format: "csv" | "tsv") =>
    request<CsvDialect>(
      `/connections/${id}/objects/dialect?path=${encodeURIComponent(path)}&format=${format}`,
    ),
  // OS keychain secrets: store a value once, keep only a keyring:NAME reference.
  keyringStatus: () => request<KeyringAvailability>("/connections/keyring"),
  keyringSecretStatus: (name: string) =>
    request<KeyringSecretStatus>(`/connections/keyring/${encodeURIComponent(name)}`),
  storeKeyringSecret: (body: KeyringSecretWrite) =>
    request<KeyringSecretStatus>("/connections/keyring", { method: "POST", body: JSON.stringify(body) }),
  deleteKeyringSecret: (name: string) =>
    request<void>(`/connections/keyring/${encodeURIComponent(name)}`, { method: "DELETE" }),
};
