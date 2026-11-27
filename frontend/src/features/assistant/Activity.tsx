import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Check, History, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Flow, GraphJson } from "@/features/flows/types";
import { getNodeTypeDef } from "@/features/flows/editor/nodeCatalog";
import { request } from "@/lib/api/client";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import {
  activityKey,
  activityUrl,
  confirmReversal,
  loadFlow,
  previewReversal,
  type ActivityEntry,
  type ActivityPage,
  type Fact,
  type ReversalPreview,
} from "./api";
import { factCounts, summarize } from "./changeSummary";

type Preview = ReversalPreview;
const label = (kind?: string) =>
  (kind && getNodeTypeDef(kind)?.label) || kind || "node";
const kicker = {
  build: "Proposal saved",
  diagnose: "Repair saved",
  revert: "Reversal",
};

function Details({ facts }: { facts: Fact[] }) {
  return (
    <ul className="space-y-1.5 border-l-2 border-border pl-3 text-sm">
      {facts.map((f, i) => {
        if (f.action === "edit_field")
          return (
            <li key={i}>
              {label(f.kind)} · {f.field}
              {f.before !== undefined && f.after !== undefined ? (
                <span className="ml-2 inline-flex items-center gap-1.5 font-mono text-xs">
                  <span className="rounded bg-muted px-1.5 py-0.5 line-through">
                    {String(f.before)}
                  </span>
                  {" → "}
                  <span className="rounded bg-accent px-1.5 py-0.5 font-semibold text-accent-foreground">
                    {String(f.after)}
                  </span>
                </span>
              ) : (
                <span className="text-muted-foreground">
                  {" "}
                  · setting changed
                </span>
              )}
            </li>
          );
        if (f.kind)
          return (
            <li key={i}>
              {f.action === "add_node" ? "Add" : "Remove"} {label(f.kind)}
            </li>
          );
        return (
          <li key={i}>
            {f.action === "connect" ? "Connect" : "Disconnect"} {label(f.from)}{" "}
            → {label(f.to)}
            {f.source_port && ` · ${f.source_port} output`}
            {f.port && f.port !== "in" ? ` · ${f.port} input` : ""}
          </li>
        );
      })}
    </ul>
  );
}

export function Activity({
  flowId,
  projectId,
  revision,
  disabled,
  current,
  restored,
  locking,
}: {
  flowId: string;
  projectId: string | null;
  revision: string;
  disabled: boolean;
  current: () => GraphJson;
  restored: (flow: Flow) => void;
  locking: (busy: boolean) => void;
}) {
  const client = useQueryClient();
  const queryKey = activityKey(projectId, flowId);
  const url = activityUrl(flowId);
  const feed = useInfiniteQuery({
    queryKey,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      request<ActivityPage>(
        url + (pageParam ? `?cursor=${encodeURIComponent(pageParam)}` : ""),
        { cache: "no-store" },
      ),
    getNextPageParam: (last) => last.next,
    staleTime: 0,
  });
  const dirty = useFlowEditorStore((s) => s.dirty);
  const [preview, setPreview] = useState<
    Preview & {
      id: string;
      revision: string;
      snapshot: string;
      session: number;
    }
  >();
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const status = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (preview) reviewHeading.current?.focus();
  }, [preview]);
  useEffect(() => {
    if (notice) status.current?.focus();
  }, [notice]);
  async function review(id: string) {
    if (useFlowEditorStore.getState().dirty || disabled || pending) return;
    const session = useFlowEditorStore.getState().sessionId;
    const snapshot = JSON.stringify(current());
    setError("");
    setNotice("");
    setPending(true);
    try {
      const response = await previewReversal(flowId, id, revision);
      if (alive.current)
        setPreview({ ...response, id, revision, snapshot, session });
    } catch (e) {
      if (alive.current)
        setError(e instanceof Error ? e.message : "Preview failed.");
    } finally {
      if (alive.current) setPending(false);
    }
  }
  async function confirm() {
    if (!preview || pending || disabled) return;
    const unchanged = () =>
      alive.current &&
      !useFlowEditorStore.getState().dirty &&
      useFlowEditorStore.getState().sessionId === preview.session &&
      JSON.stringify(current()) === preview.snapshot;
    if (!unchanged() || preview.revision !== revision) {
      setPreview(undefined);
      setError(
        "The canvas changed. Save or discard local edits before previewing again.",
      );
      return;
    }
    setPending(true);
    locking(true);
    setError("");
    let committed = false;
    try {
      const result = await confirmReversal(
        flowId,
        preview.id,
        preview.confirmation,
      );
      committed = true;
      const flow = await loadFlow(flowId);
      if (unchanged() && flow.updated_at === result.revision) {
        restored(flow);
        setNotice("Reversal saved to activity.");
      } else if (alive.current)
        setNotice("Reversal saved. Reload when your local edits are safe.");
    } catch (e) {
      if (alive.current)
        setError(
          committed
            ? "Reversal saved. Reload to see the latest flow."
            : e instanceof Error
              ? e.message
              : "Confirmation failed. Refresh activity before retrying.",
        );
    } finally {
      void client.invalidateQueries({ queryKey });
      if (alive.current) {
        setPreview(undefined);
        setPending(false);
        locking(false);
      }
    }
  }
  const rows = feed.data?.pages.flatMap((p) => p.entries) ?? [];
  const reversed = (entry: ActivityEntry) => {
    const target = rows.find((r) => r.id === entry.reverses);
    return target
      ? `Reverses “${summarize(factCounts(target.details))}” from ${new Date(target.date).toLocaleString()}`
      : "Reverses an earlier change";
  };
  return (
    <div className="grid gap-4">
      <div>
        <h3 className="text-lg font-semibold">Saved changes</h3>
      </div>
      {dirty && (
        <p
          role="status"
          className="rounded-lg border border-border p-3 text-sm"
        >
          Save or discard your pending canvas edits before reverting a saved
          change.
        </p>
      )}
      {notice && (
        <p
          ref={status}
          tabIndex={-1}
          role="status"
          className="text-sm font-medium"
        >
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {preview ? (
        <section
          aria-label="Reversal preview"
          className="space-y-4 rounded-xl border border-primary/40 bg-gradient-to-b from-accent/60 to-card p-4 shadow-sm"
        >
          <h4 ref={reviewHeading} tabIndex={-1} className="font-semibold">
            <RotateCcw
              aria-hidden
              className="mr-2 inline size-4 text-primary"
            />
            Review reversal
          </h4>
          <Details facts={preview.details} />
          <p className="text-sm text-muted-foreground">
            Adds a reversal to this flow’s activity.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={pending || dirty || disabled}
              onClick={() => void confirm()}
            >
              Confirm reversal
            </Button>
            <Button
              variant="outline"
              disabled={pending}
              onClick={() => setPreview(undefined)}
            >
              Cancel reversal
            </Button>
          </div>
        </section>
      ) : (
        <>
          {feed.isPending ? (
            <p role="status">Loading activity…</p>
          ) : feed.isError ? (
            <div role="alert">
              Activity could not be loaded.{" "}
              <Button variant="outline" onClick={() => void feed.refetch()}>
                Retry
              </Button>
            </div>
          ) : !rows.length ? (
            <div className="rounded-xl border border-dashed border-border p-6 text-center">
              <History
                aria-hidden
                className="mx-auto mb-2 size-6 text-muted-foreground"
              />
              <p className="font-medium">No saved changes yet</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Review and save a proposal to start this flow’s history.
              </p>
            </div>
          ) : (
            <ol className="ml-2 space-y-4 border-l-2 border-primary/25 pl-4">
              {rows.map((entry) => (
                <li
                  key={entry.id}
                  className="assistant-event relative rounded-xl border border-border bg-card p-4 shadow-sm"
                >
                  <div className="flex items-start gap-3">
                    {entry.source === "revert" ? (
                      <RotateCcw
                        aria-hidden
                        className="mt-1 size-4 text-primary"
                      />
                    ) : (
                      <Check aria-hidden className="mt-1 size-4 text-primary" />
                    )}
                    <div className="min-w-0">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {kicker[entry.source]} ·{" "}
                        <time dateTime={entry.date}>
                          {new Date(entry.date).toLocaleString()}
                        </time>
                      </p>
                      <h4 className="font-semibold">
                        {summarize(factCounts(entry.details))}
                      </h4>
                      {entry.source === "revert" && (
                        <p className="text-xs text-muted-foreground">
                          {reversed(entry)}
                        </p>
                      )}
                    </div>
                  </div>
                  <details className="my-3 text-sm">
                    <summary className="flex min-h-8 cursor-pointer items-center font-medium">
                      Show details
                    </summary>
                    <div className="mt-2">
                      <Details facts={entry.details} />
                    </div>
                  </details>
                  {entry.state === "available" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={pending || dirty || disabled}
                      onClick={() => void review(entry.id)}
                    >
                      <RotateCcw aria-hidden className="size-3.5" />
                      Preview reversal
                    </Button>
                  ) : entry.state === "reverted" ? (
                    <p className="text-xs text-muted-foreground">
                      Already reverted
                    </p>
                  ) : (
                    entry.source !== "revert" && (
                      <p className="text-xs text-muted-foreground">
                        Restore the earlier configuration manually.
                      </p>
                    )
                  )}
                </li>
              ))}
            </ol>
          )}
          {feed.hasNextPage && (
            <Button
              variant="outline"
              disabled={feed.isFetchingNextPage}
              onClick={() => void feed.fetchNextPage()}
            >
              Load older changes
            </Button>
          )}
        </>
      )}
    </div>
  );
}
