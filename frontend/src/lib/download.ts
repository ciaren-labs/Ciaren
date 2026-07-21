import { authHeaders, BASE_URL, parseError } from "@/lib/api/client";

/** Pull a filename out of a Content-Disposition header, if present. */
function filenameFromContentDisposition(header: string | null): string | null {
  if (!header) return null;
  // RFC 5987 `filename*=UTF-8''…` is preferred (it can carry non-ASCII names);
  // fall back to the plain `filename="…"` form.
  const extended = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header);
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim().replace(/^["']|["']$/g, ""));
    } catch {
      // malformed percent-encoding — fall through to the plain form
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain?.[1]?.trim() ?? null;
}

/**
 * Download a file from an authorized `/api` endpoint.
 *
 * A plain `<a href download>` navigation can't carry the `Authorization: Bearer`
 * header, so whenever a CIAREN_API_TOKEN is configured those links 401 and the
 * download is unusable. Instead we fetch the bytes here — attaching the token via
 * `authHeaders()` — and hand the browser a Blob URL to save. With no token
 * configured the fetch simply carries no auth header, so the localhost path keeps
 * working exactly as before.
 *
 * `path` may be a bare endpoint path ("/runs/…"), an already-`/api`-prefixed path
 * (as `downloadVersionUrl` returns), or an absolute URL. `fallbackName` is used
 * when the response carries no Content-Disposition filename. Throws an ApiError
 * on a non-OK response so callers can surface it through the app's error handling.
 */
export async function downloadFromApi(path: string, fallbackName: string): Promise<void> {
  const url = /^https?:\/\//.test(path) || path.startsWith(BASE_URL) ? path : `${BASE_URL}${path}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const filename =
    filenameFromContentDisposition(res.headers.get("Content-Disposition")) ?? fallbackName;
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    // The click has already handed the blob to the browser's download manager,
    // so releasing the object URL now is safe and avoids leaking it.
    URL.revokeObjectURL(objectUrl);
  }
}
