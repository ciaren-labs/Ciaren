// Shared HTTP transport for the Ciaren API client. Domain-specific request
// builders live in each feature's own api.ts (e.g. features/flows/api.ts) and
// import `request`/`ApiError`/`queryString` from here — this file only grows
// when the transport itself changes, not when an endpoint is added.

/** Build a `?a=b&c=d` query string from defined values only. */
export function queryString(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  const usp = new URLSearchParams();
  for (const [k, v] of entries) usp.set(k, String(v));
  return `?${usp.toString()}`;
}

export const BASE_URL = "/api";

// ---- API token (optional; matches backend CIAREN_API_TOKEN) --------------
// When the backend is started with CIAREN_API_TOKEN set, every /api request
// must carry a bearer token. It is held in memory and mirrored to
// sessionStorage so a reload keeps you signed in — but deliberately NOT in
// localStorage: the token must not outlive the browser session or be inherited
// by the next user of a shared machine, and a session-scoped copy shrinks the
// window an XSS payload has to exfiltrate it. The token stays a request *header*
// (not a cookie) on purpose — that header is the backend's CSRF defense (a
// cross-site request can't attach it without a preflight; see app/core/csrf.py).
// It can be seeded once via a `?api_token=…` query param (handy for a bookmarked
// URL), which is then stripped from the address bar.
const API_TOKEN_STORAGE_KEY = "ciaren_api_token";

let memoryToken: string | null = null;

/** sessionStorage, or null when unavailable (SSR, sandboxed/blocked contexts). */
function sessionStore(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

function captureTokenFromUrl(): void {
  if (typeof window === "undefined") return;
  // One-time migration: earlier builds persisted the token in localStorage.
  // Move it to the session-scoped store and purge the durable copy so it no
  // longer lingers on disk / across browser restarts.
  try {
    const legacy = window.localStorage.getItem(API_TOKEN_STORAGE_KEY);
    if (legacy) {
      window.localStorage.removeItem(API_TOKEN_STORAGE_KEY);
      if (!sessionStore()?.getItem(API_TOKEN_STORAGE_KEY)) setApiToken(legacy);
    }
  } catch {
    // ignore storage access errors
  }
  const url = new URL(window.location.href);
  const token = url.searchParams.get("api_token");
  if (token) {
    setApiToken(token);
    url.searchParams.delete("api_token");
    window.history.replaceState({}, "", url.toString());
  }
}

export function getApiToken(): string | null {
  if (memoryToken !== null) return memoryToken;
  memoryToken = sessionStore()?.getItem(API_TOKEN_STORAGE_KEY) ?? null;
  return memoryToken;
}

export function setApiToken(token: string | null): void {
  memoryToken = token;
  const store = sessionStore();
  if (!store) return;
  if (token) store.setItem(API_TOKEN_STORAGE_KEY, token);
  else store.removeItem(API_TOKEN_STORAGE_KEY);
}

captureTokenFromUrl();

/** Authorization header for the current token, or empty when none is stored.
 * Safe to spread into a FormData request (it sets no Content-Type). */
export function authHeaders(): Record<string, string> {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export async function parseError(res: Response): Promise<ApiError> {
  let message = `Request failed with status ${res.status}`;
  let details: unknown;
  try {
    const body = await res.json();
    // Backend may return { error: { message } } or FastAPI { detail }.
    if (body?.error?.message) {
      message = body.error.message;
      details = body.error.details;
    } else if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (body?.detail) {
      message = JSON.stringify(body.detail);
      details = body.detail;
    }
  } catch {
    // ignore non-JSON bodies
  }
  return new ApiError(message, res.status, details);
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  // `...options` first, `headers` last: the other way round, any caller
  // passing options.headers would replace the merged object wholesale and
  // silently drop Content-Type / auth headers.
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
