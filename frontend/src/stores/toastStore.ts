import { create } from "zustand";

export type ToastVariant = "success" | "error" | "info" | "warning";

export type ToastAction =
  | { label: string; to: string; onClick?: never }
  | { label: string; onClick: () => void; to?: never };

export interface Toast {
  id: number;
  variant: ToastVariant;
  title: string;
  /** Optional second line with more detail (e.g. the server's error message). */
  description?: string;
  /**
   * Optional inline action: either a navigation link (e.g. "View run" →
   * /runs/:id) or a callback (e.g. "Undo"). Exactly one of `to`/`onClick`.
   */
  action?: ToastAction;
  /** ms before auto-dismiss; errors linger longer than confirmations. */
  duration: number;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id" | "duration"> & { duration?: number }) => number;
  dismiss: (id: number) => void;
}

let nextId = 1;

const DEFAULT_DURATION: Record<ToastVariant, number> = {
  success: 4000,
  info: 5000,
  warning: 6000,
  error: 8000,
};

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = nextId++;
    const duration = toast.duration ?? DEFAULT_DURATION[toast.variant];
    set((s) => ({
      // Cap the stack so a burst of failures doesn't wallpaper the screen.
      toasts: [...s.toasts.slice(-3), { ...toast, id, duration }],
    }));
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

type ToastOptions = Pick<Toast, "description" | "action"> & { duration?: number };

/**
 * Imperative toast helpers, callable from anywhere (hooks, the query client,
 * plain event handlers) — no React context required.
 */
export const toast = {
  success: (title: string, opts?: ToastOptions) =>
    useToastStore.getState().push({ variant: "success", title, ...opts }),
  error: (title: string, opts?: ToastOptions) =>
    useToastStore.getState().push({ variant: "error", title, ...opts }),
  info: (title: string, opts?: ToastOptions) =>
    useToastStore.getState().push({ variant: "info", title, ...opts }),
  warning: (title: string, opts?: ToastOptions) =>
    useToastStore.getState().push({ variant: "warning", title, ...opts }),
};
