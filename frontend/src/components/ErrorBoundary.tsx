import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Remount the boundary when this value changes (e.g. the route path) so a
   *  navigation after an error clears the fallback. */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

/**
 * Catches render/runtime errors in the subtree and shows a recoverable message
 * instead of unmounting the whole app to a blank page. Without this, a single
 * throw in any component (e.g. a dialog reading an unexpected API shape) blanks
 * the entire UI.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface in the console for debugging; the UI shows a friendly message.
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto flex max-w-lg flex-col items-center gap-3 p-10 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="text-sm text-muted-foreground">
            This view hit an unexpected error. Try again, and if it persists reload the page.
          </p>
          <pre className="max-w-full overflow-auto rounded-md bg-muted px-3 py-2 text-left text-xs text-muted-foreground">
            {this.state.error.message}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            className="rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
