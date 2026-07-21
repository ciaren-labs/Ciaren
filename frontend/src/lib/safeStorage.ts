// Guarded localStorage access. Reading or writing `window.localStorage` throws a
// SecurityError in storage-blocked or sandboxed contexts (private mode, embedded
// iframes with a strict `sandbox` attribute, disabled site data). These helpers
// swallow those failures so a preference read never crashes the app — mirroring
// the try/catch pattern in useLayoutPreference and lib/api/client.

/** Read a localStorage key, or `null` when the key is absent or storage is blocked. */
export function readLocalStorage(key: string): string | null {
  try {
    return typeof localStorage !== "undefined" ? localStorage.getItem(key) : null;
  } catch {
    return null;
  }
}

/** Write a localStorage key, silently ignoring quota / SecurityError failures. */
export function writeLocalStorage(key: string, value: string): void {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
  } catch {
    // ignore quota errors and blocked-storage SecurityError
  }
}
