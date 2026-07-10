import { ApiError } from "@/lib/api/client";

/**
 * Translate a thrown error into a message a person can act on.
 *
 * The backend already returns good messages for domain errors (validation,
 * conflicts); those pass through. This mainly rescues the cryptic cases —
 * network failures ("Failed to fetch") and bare 5xx statuses.
 */
export function friendlyErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof ApiError) {
    // A generic status line means the body had no message worth showing.
    const isBareStatus = error.message.startsWith("Request failed with status");
    switch (true) {
      case error.status === 401 || error.status === 403:
        return "You're not authorized for that. Check your API token in the header menu.";
      case error.status === 404 && isBareStatus:
        return "That item no longer exists — it may have been deleted. Refreshing the list should clear it up.";
      case error.status >= 500:
        return isBareStatus
          ? "The server hit an unexpected error. Try again, and check the backend logs if it keeps happening."
          : error.message;
      default:
        return isBareStatus ? fallback : error.message;
    }
  }
  // fetch() rejects with a TypeError when the server is unreachable.
  if (error instanceof TypeError) {
    return "Can't reach the Ciaren server. Check that the backend is running, then try again.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
