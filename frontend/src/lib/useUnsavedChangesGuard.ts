import { useCallback, useEffect, useRef } from "react";

const DEFAULT_MESSAGE = "You have unsaved changes. Leave without saving?";

/**
 * Warn before losing unsaved work.
 *
 * While `when` is true this registers a `beforeunload` listener so the browser
 * prompts on tab close, reload, or navigation to an external URL. It also returns
 * a `confirmNavigation` guard for in-app (React Router) navigations: wrap a
 * navigate call with it and the user is asked to confirm first.
 *
 * (React Router's `useBlocker` would block every in-app navigation automatically,
 * but it requires a data router — this app mounts a plain `<BrowserRouter>`, where
 * `useBlocker` throws. `confirmNavigation` is the supported fallback for that
 * setup; callers apply it to the editor's own "leave" affordances.)
 */
export function useUnsavedChangesGuard(when: boolean, message: string = DEFAULT_MESSAGE) {
  // Keep the latest `when` in a ref so `confirmNavigation` stays referentially
  // stable while still reading the current dirty state at call time.
  const whenRef = useRef(when);
  useEffect(() => {
    whenRef.current = when;
  }, [when]);

  useEffect(() => {
    if (!when) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Legacy browsers only show the native prompt when returnValue is set.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [when]);

  /** Run `proceed` immediately when clean, or after the user confirms leaving. */
  const confirmNavigation = useCallback(
    (proceed: () => void) => {
      if (!whenRef.current || window.confirm(message)) proceed();
    },
    [message],
  );

  return confirmNavigation;
}
