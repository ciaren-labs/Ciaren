export type PluginStatus = "loaded" | "disabled" | "needs_permissions" | "needs_license";

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  publisher: string;
  description: string;
  source: string;
  status: PluginStatus;
  /** Human-readable context for a gated status (e.g. why the license is invalid). */
  status_detail: string;
  capabilities: string[];
  /** Permissions the plugin requests. */
  permissions: string[];
  /** Permissions the user has granted it. */
  granted_permissions: string[];
  /** Requested-but-not-yet-granted permissions (non-empty ⇒ needs approval). */
  missing_permissions: string[];
  /** How the package verified at install time: trusted | untrusted | unsigned | invalid | "". */
  signature: string;
  /** First-party: verified as trusted under a publisher key pinned into the app
   *  itself (not merely a user-added trusted key). Derived, never declared. */
  official: boolean;
  /** Node type ids this plugin contributes to the editor palette. */
  nodes: string[];
  /** Palette category/subgroup for each contributed node. */
  node_categories: Record<string, string>;
  /** Connector ids this plugin contributes (loaded plugins only). */
  connectors?: string[];
  /** Trainable model-type ids this plugin contributes to the ML catalog. */
  model_types?: string[];
  /** True when the plugin lives in the managed install dir and can be uninstalled
   *  via DELETE. False for dev-dir / entry-point plugins (disable-only). */
  uninstallable: boolean;
  /** Manifest license kind: community | commercial | "" (no manifest). */
  license: string;
  /** Declared marketplace trust tier: trusted | verified | community | "". */
  trust: string;
  /** PEP 440 specifier of compatible Ciaren versions (e.g. ">=0.1"). */
  ciaren_spec: string;
  /** pip requirements the plugin declares it needs. */
  dependencies: string[];
  /** Dotted entry point (module.path:ClassName) from the manifest. */
  entrypoint: string;
  /** Managed install directory on disk, "" when the plugin lives elsewhere. */
  install_path: string;
}

export interface LicenseStatus {
  plugin_id: string;
  valid: boolean;
  license_type: string | null;
  expires_at: string | null;
  reason: string | null;
}

export interface PluginErrorInfo {
  source: string;
  error: string;
}

export interface PluginDiagnostics {
  loaded: PluginInfo[];
  gated: PluginInfo[];
  errors: PluginErrorInfo[];
}

export interface PluginInstallResult {
  plugin: PluginInfo;
  /** Signature trust outcome: trusted | untrusted | unsigned | invalid. */
  outcome: string;
  reason: string;
}

export interface PluginUninstallResult {
  plugin_id: string;
  /** True if managed install files were deleted; false if there was nothing to
   *  remove (dev-dir / entry-point plugin) — its persisted state is still cleared. */
  removed: boolean;
}

export interface MarketplaceEntry {
  id: string;
  name: string;
  version: string;
  publisher: string;
  description: string;
  license: string;
  /** Derived by verifying the local artifact's signature:
   *  "official" (first-party pinned key) | "trusted" | "community". */
  trust: string;
  capabilities: string[];
  permissions: string[];
  /** PEP 440 specifier of compatible Ciaren versions ("" for older indexes). */
  ciaren_spec: string;
  /** pip requirements the plugin declares it needs (advisory). */
  dependencies: string[];
  /** Node type ids this catalog entry contributes after install + approval. */
  nodes: string[];
  /** Palette category/subgroup for each contributed node. */
  node_categories: Record<string, string>;
  license_required: boolean;
  /** A plugin with this id is already installed. */
  installed: boolean;
  /** The installed plugin's version ("" when not installed or unknown). */
  installed_version: string;
  /** The catalog offers a strictly newer version than the installed one. */
  update_available: boolean;
  /** The catalog has withdrawn this plugin (installing is refused). */
  revoked: boolean;
  /** The artifact is available locally for one-click install. */
  installable: boolean;
}

export interface MarketplaceCatalog {
  /** False when no index is configured (the UI explains how to enable it). */
  configured: boolean;
  plugins: MarketplaceEntry[];
  /** Installed plugin ids the catalog has revoked (may already be delisted). */
  revoked_installed: string[];
}
