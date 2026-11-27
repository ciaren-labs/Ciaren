import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { Dataset } from "@/features/datasets/types";
import type { GraphJson } from "@/features/flows/types";
import { graphToStore } from "@/features/flows/graphMapper";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { request } from "@/lib/api/client";
import { ProposalReview } from "./ProposalReview";
import { applyDelta, status, type Mode, type Reply } from "./api";

interface Props {
  flowId: string;
  revision: string;
  disabled: boolean;
  datasets: Dataset[];
  current: () => GraphJson;
  saved: (revision: string, graph: GraphJson) => void;
}
export function AssistantPanel({
  flowId,
  revision,
  disabled,
  datasets,
  current,
  saved,
}: Props) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("build");
  const [question, setQuestion] = useState("");
  const [dataset, setDataset] = useState("");
  const [shareNames, setShareNames] = useState(false);
  const [reply, setReply] = useState<Reply>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"generate" | "apply">();
  const [base, setBase] = useState<GraphJson | null>(null);
  const abort = useRef<AbortController | null>(null);
  const session = useRef(0);
  const service = useQuery({
    queryKey: ["assistant-status", flowId],
    queryFn: status,
    enabled: open,
    retry: false,
    staleTime: 0,
  });
  useEffect(
    () => () => {
      abort.current?.abort();
    },
    [],
  );
  function cancel() {
    abort.current?.abort();
    abort.current = null;
    setBusy(undefined);
    setReply(undefined);
    setError("Request cancelled.");
  }
  function changeOpen(value: boolean) {
    if (busy === "apply") return;
    if (!value) {
      cancel();
      setQuestion("");
      setShareNames(false);
    }
    setError("");
    setOpen(value);
  }
  async function generate() {
    if (!service.data || !question.trim()) return;
    const controller = new AbortController();
    const requestId = crypto.randomUUID();
    controller.signal.addEventListener(
      "abort",
      () => {
        void request<void>(`/assistant/flows/${flowId}/turns/${requestId}`, {
          method: "DELETE",
          keepalive: true,
        }).catch(() => {
          // A disconnected browser also closes the turn socket. The provider has a hard deadline.
        });
      },
      { once: true },
    );
    abort.current = controller;
    setBusy("generate");
    setReply(undefined);
    setError("");
    const snapshot = current();
    setBase(snapshot);
    setShareNames(false);
    session.current = useFlowEditorStore.getState().sessionId;
    try {
      const result = await request<Reply>(`/assistant/flows/${flowId}/turn`, {
        method: "POST",
        signal: controller.signal,
        redirect: "error",
        body: JSON.stringify({
          mode,
          request_id: requestId,
          question,
          revision,
          provider: service.data.provider,
          graph: mode === "docs" ? {} : snapshot,
          dataset_id: dataset || null,
          share_names: shareNames,
        }),
      });
      if (!controller.signal.aborted) setReply(result);
    } catch (err) {
      if (!controller.signal.aborted)
        setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      if (abort.current === controller) {
        abort.current = null;
        setBusy(undefined);
      }
    }
  }
  function matchesBase() {
    return (
      session.current === useFlowEditorStore.getState().sessionId &&
      JSON.stringify(current()) === JSON.stringify(base)
    );
  }
  async function confirm() {
    if (!reply?.proposal || !reply.delta || !base || disabled) return;
    if (!matchesBase()) {
      setError("The canvas changed. Generate a fresh proposal.");
      setReply(undefined);
      return;
    }
    setBusy("apply");
    setError("");
    try {
      const result = await request<{ revision: string }>(
        `/assistant/flows/${flowId}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ proposal: reply.proposal }),
          redirect: "error",
        },
      );
      if (matchesBase()) {
        const graph = applyDelta(base, reply.delta);
        const next = graphToStore(graph);
        useFlowEditorStore.getState().acceptProposal(next.nodes, next.edges);
        saved(result.revision, graph);
        setOpen(false);
        setQuestion("");
      } else {
        setError(
          "The proposal was saved while the canvas changed. Reload to reconcile both versions.",
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Confirmation failed. Reload before retrying.",
      );
    } finally {
      setReply(undefined);
      setBusy(undefined);
    }
  }
  const ready = service.data?.state === "configured";
  const labels: Record<Mode, string> = {
    build: "Build or modify a flow",
    docs: "Ask the Ciaren guides",
    diagnose: "Diagnose a failure",
  };
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Sparkles aria-hidden="true" className="h-4 w-4" />
          Assistant
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90dvh] w-[min(96vw,38rem)] max-w-none overflow-y-auto">
        <DialogTitle>Flow assistant</DialogTitle>
        <DialogDescription>
          {service.data?.model
            ? `${service.data.provider} · ${service.data.model}`
            : "Bring your own API key"}
        </DialogDescription>
        {!ready && (
          <p role="status">
            {service.isLoading
              ? "Checking configuration…"
              : "Choose a provider and configure its key in Settings."}{" "}
            <Link to="/settings" className="underline">
              Open settings
            </Link>
          </p>
        )}
        {reply?.proposal ? (
          <p className="text-sm text-muted-foreground">{question}</p>
        ) : (
          <>
            <label className="grid gap-1 text-sm">
              Task
              <Select
                aria-label="Task"
                value={mode}
                disabled={!!busy}
                onChange={(e) => {
                  setMode(e.target.value as Mode);
                  setReply(undefined);
                  setError("");
                }}
              >
                {(Object.keys(labels) as Mode[]).map((m) => (
                  <option key={m} value={m}>
                    {labels[m]}
                  </option>
                ))}
              </Select>
            </label>
            {mode !== "docs" && !current().nodes.length && (
              <label className="grid gap-1 text-sm">
                Input dataset
                <Select
                  aria-label="Input dataset"
                  disabled={!!busy}
                  value={dataset}
                  onChange={(e) => {
                    setDataset(e.target.value);
                    setReply(undefined);
                  }}
                >
                  <option value="">Choose a project dataset</option>
                  {datasets
                    .filter((d) => !d.is_disabled)
                    .map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                </Select>
              </label>
            )}
            <label className="grid gap-1 text-sm">
              Request
              <textarea
                aria-label="Request"
                className="min-h-20 rounded-md border border-border bg-background p-2"
                disabled={!!busy}
                maxLength={1500}
                placeholder={
                  mode === "docs"
                    ? "How do I export Polars code?"
                    : mode === "build"
                      ? "Keep the first 100 rows"
                      : "Why did this flow fail?"
                }
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  setReply(undefined);
                }}
              />
            </label>
            <div className="space-y-2 text-xs text-muted-foreground">
              <p>
                {mode === "docs"
                  ? "Sends your request and matching passages from the bundled guides."
                  : "Sends your request, node types and connections, column types and indexes, and a failure category for diagnosis. Rows, filenames, raw errors and code stay local."}{" "}
                Keep secrets out of your request.
              </p>
              {mode !== "docs" && (
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={shareNames}
                    disabled={!!busy}
                    onChange={(e) => {
                      setShareNames(e.target.checked);
                      setReply(undefined);
                    }}
                  />
                  Include column names in this request
                </label>
              )}
            </div>
          </>
        )}
        <div role="status" aria-live="polite">
          {busy === "generate"
            ? "Waiting for provider…"
            : busy === "apply"
              ? "Saving proposal…"
              : reply?.message
                  .replace(/\*\*([^*]+)\*\*/g, "$1")
                  .replace(/`([^`]+)`/g, "$1")}
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {reply?.citation && (
          <a
            className="text-sm underline"
            href={reply.citation.url}
            target="_blank"
            rel="noreferrer"
          >
            {reply.citation.title}
          </a>
        )}
        {reply?.delta && base && (
          <ProposalReview delta={reply.delta} base={base} datasets={datasets} />
        )}
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="outline"
            disabled={busy === "apply"}
            onClick={() => (busy ? cancel() : changeOpen(false))}
          >
            {busy === "generate" ? "Cancel request" : "Close"}
          </Button>
          {reply?.proposal && (
            <Button
              disabled={!!busy || disabled}
              onClick={() => void confirm()}
            >
              Apply and save
            </Button>
          )}
          {!reply?.proposal && (
            <Button
              disabled={
                !!busy ||
                !ready ||
                !question.trim() ||
                (mode !== "docs" && disabled)
              }
              onClick={() => void generate()}
            >
              Send request
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
