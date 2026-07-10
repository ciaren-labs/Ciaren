import { authHeaders, BASE_URL, parseError, request } from "@/lib/api/client";
import type {
  LicenseStatus,
  MarketplaceCatalog,
  PluginDiagnostics,
  PluginInfo,
  PluginInstallResult,
  PluginUninstallResult,
} from "./types";

export const pluginsApi = {
  list: () => request<PluginInfo[]>("/plugins"),
  diagnostics: () => request<PluginDiagnostics>("/plugins/diagnostics"),
  enable: (id: string) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/enable`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  disable: (id: string) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/disable`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  grant: (id: string, permissions: string[] = []) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/grant`, {
      method: "POST",
      body: JSON.stringify({ permissions }),
    }),
  revoke: (id: string, permissions: string[]) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/revoke`, {
      method: "POST",
      body: JSON.stringify({ permissions }),
    }),
  install: async (file: File): Promise<PluginInstallResult> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/plugins/install`, {
      method: "POST",
      body: form,
      headers: authHeaders(),
    });
    if (!res.ok) {
      throw await parseError(res);
    }
    return (await res.json()) as PluginInstallResult;
  },
  license: (id: string) => request<LicenseStatus>(`/plugins/${encodeURIComponent(id)}/license`),
  /** Activate a license: send the pasted token JSON (marketplace wire format).
   *  The backend vets it against the trusted issuer keys before caching. */
  activateLicense: (id: string, token: unknown) =>
    request<LicenseStatus>(`/plugins/${encodeURIComponent(id)}/license`, {
      method: "POST",
      body: JSON.stringify(token),
    }),
  removeLicense: (id: string) =>
    request<LicenseStatus>(`/plugins/${encodeURIComponent(id)}/license`, { method: "DELETE" }),
  uninstall: (id: string) =>
    request<PluginUninstallResult>(`/plugins/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

// ---- Marketplace ("Explore" catalog) ---------------------------------------

export const marketplaceApi = {
  list: () => request<MarketplaceCatalog>("/marketplace"),
  install: (id: string) =>
    request<PluginInstallResult>(`/marketplace/${encodeURIComponent(id)}/install`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
