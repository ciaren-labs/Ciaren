import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  BookOpen,
  GitPullRequest,
  History,
  KeyRound,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  X,
} from "lucide-react";
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
import type { Flow, GraphJson } from "@/features/flows/types";
import { graphToStore } from "@/features/flows/graphMapper";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { useMlEnabled } from "@/features/models/hooks";
import { request } from "@/lib/api/client";
import { ProposalReview } from "./ProposalReview";
import { applyDelta, status, type Mode, type Reply } from "./api";

import { useReactFlow } from "@xyflow/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { FlowValidation } from "@/features/flows/editor/flowValidation";
import { CanvasHelp } from "./CanvasHelp";
import { Activity } from "./Activity";

interface Props {
  flowName: string;
  validation: FlowValidation;
  restored: (flow: Flow) => void;
  flowId: string;
  projectId: string | null;
  revision: string;
  disabled: boolean;
  datasets: Dataset[];
  current: () => GraphJson;
  saved: (revision: string, graph: GraphJson) => void;
}
export function AssistantPanel({
  flowId,
  flowName,
  projectId,
  validation,
  restored,
  revision,
  disabled,
  datasets,
  current,
  saved,
}: Props) {
  const [tab, setTab] = useState("conversation");
  const [reversing, setReversing] = useState(false);
  const focusTarget = useRef<string | undefined>(undefined);
  const { fitView } = useReactFlow();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("build");
  const [question, setQuestion] = useState("");
  const [dataset, setDataset] = useState("");
  const [secondDataset, setSecondDataset] = useState("");
  const [lookup, setLookup] = useState("");
  const [target, setTarget] = useState("");
  const mlEnabled = useMlEnabled();
  const fact = datasets.find((d) => d.id === dataset);
  const selectedInputs = [dataset, secondDataset, lookup].map((id) =>
    datasets.find((d) => d.id === id),
  );
  const training = mode === "build" && !!lookup && !current().nodes.length;
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
  useEffect(() => {
    if (!open || tab !== "conversation" || !reply?.delta) return;
    // The highlight is presentational and disappears when the preview closes.
    // Keeping it outside the graph prevents it entering saves or undo history.
    const highlights = reply.delta.changed.flatMap((node) => {
      const el = document.querySelector<HTMLElement>(
        `.react-flow__node[data-id="${CSS.escape(node.id)}"]`,
      );
      if (!el) return [];
      el.classList.add("assistant-review-node");
      return [el];
    });
    return () =>
      highlights.forEach((el) => el.classList.remove("assistant-review-node"));
  }, [open, tab, reply]);
  function cancel() {
    abort.current?.abort();
    abort.current = null;
    setBusy(undefined);
    setReply(undefined);
    setError("Request cancelled.");
  }
  function changeOpen(value: boolean) {
    if (busy === "apply" || reversing) return;
    if (!value) {
      cancel();
      setQuestion("");
      setShareNames(false);
    }
    setError("");
    if (value) setTab("conversation");
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
          dataset_id:
            mode === "build" && !snapshot.nodes.length ? dataset || null : null,
          second_dataset_id:
            mode === "build" && !snapshot.nodes.length
              ? secondDataset || null
              : null,
          ...(training && {
            training: {
              dataset_id: lookup,
              versions: selectedInputs.map((d) => d?.latest_version ?? 0),
              target,
            },
          }),
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
  function inspectNode(id: string) {
    focusTarget.current = id;
    useFlowEditorStore.getState().selectNode(id);
    changeOpen(false);
    void fitView({
      nodes: [{ id }],
      maxZoom: 1.2,
      padding: 0.35,
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 0
        : 180,
    });
  }
  const ready = service.data?.state === "configured";
  const labels: Record<Mode, string> = {
    build: "Build",
    docs: "Guides",
    diagnose: "Diagnose",
  };
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className="shrink-0 border-primary/40 text-foreground"
        >
          <Sparkles aria-hidden="true" className="h-4 w-4" />
          Assistant
        </Button>
      </DialogTrigger>
      <DialogContent
        overlayClassName="bg-foreground/10"
        onCloseAutoFocus={(e) => {
          if (focusTarget.current) {
            const el = document.querySelector<HTMLElement>(
              `.react-flow__node[data-id="${CSS.escape(focusTarget.current)}"]`,
            );
            if (el) {
              e.preventDefault();
              el.focus();
            }
            focusTarget.current = undefined;
          }
        }}
        className="assistant-panel top-2 bottom-2 left-auto right-2 flex h-auto max-h-none w-[min(32rem,calc(100vw-1rem))] max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-2xl p-0 shadow-xl"
      >
        <div className="assistant-mast flex items-center gap-3 px-5 py-4 text-white">
          <div className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/35 bg-white/15 text-white">
            <Sparkles aria-hidden className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <DialogTitle className="text-lg">Flow assistant</DialogTitle>
            <DialogDescription className="truncate text-violet-100">
              {flowName}
            </DialogDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-white hover:bg-white/15 hover:text-white"
            aria-label="Close"
            disabled={busy === "apply" || reversing}
            onClick={() => changeOpen(false)}
          >
            <X aria-hidden className="size-4" />
          </Button>
        </div>
        <Tabs
          value={tab}
          onValueChange={setTab}
          className="flex min-h-0 flex-1 flex-col"
        >
          <TabsList
            aria-label="Assistant sections"
            className="mx-5 my-3 grid shrink-0 grid-cols-2"
          >
            <TabsTrigger
              value="conversation"
              disabled={reversing}
              className="motion-reduce:transition-none"
            >
              <MessageSquare aria-hidden className="mr-2 size-4" />
              Conversation
            </TabsTrigger>
            <TabsTrigger
              value="activity"
              disabled={!!busy}
              className="motion-reduce:transition-none"
            >
              <History aria-hidden className="mr-2 size-4" />
              Activity
            </TabsTrigger>
          </TabsList>
          <TabsContent
            value="activity"
            className="mt-0 min-h-0 overflow-y-auto px-5 pb-5"
          >
            <Activity
              flowId={flowId}
              projectId={projectId}
              revision={revision}
              disabled={disabled}
              current={current}
              restored={restored}
              locking={setReversing}
            />
          </TabsContent>
          <TabsContent
            value="conversation"
            className="mt-0 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
          >
            <div className="grid min-h-0 content-start gap-4 overflow-y-auto px-5 pb-5 pt-1">
              {!ready && (
                <section
                  role="status"
                  className="grid place-items-start gap-3 rounded-2xl border border-primary/20 bg-gradient-to-br from-accent to-card p-5"
                >
                  <span className="grid size-10 place-items-center rounded-xl border border-border bg-card text-primary">
                    <KeyRound aria-hidden className="size-5" />
                  </span>
                  <div>
                    <h3 className="font-semibold">
                      {service.isLoading
                        ? "Checking configuration…"
                        : service.isError
                          ? "Configuration unavailable"
                          : "Connect a provider"}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {service.isError
                        ? "Retry in Settings. Canvas tools are available here."
                        : "Choose an API key to build flows and ask the guides."}
                    </p>
                  </div>
                  <Link
                    to="/settings#assistant"
                    className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground focus-visible:ring-2"
                  >
                    Open settings
                  </Link>
                </section>
              )}
              {reply?.proposal ? (
                <div className="ml-8 rounded-xl rounded-tr-sm bg-primary/10 px-4 py-3 text-sm">
                  {question}
                </div>
              ) : ready ? (
                <>
                  <div
                    role="group"
                    aria-label="Task"
                    className="grid grid-cols-3 gap-2"
                  >
                    {(Object.keys(labels) as Mode[]).map((m) => {
                      const Icon = {
                        build: GitPullRequest,
                        docs: BookOpen,
                        diagnose: Stethoscope,
                      }[m];
                      return (
                        <button
                          key={m}
                          aria-pressed={m === mode}
                          disabled={!!busy}
                          className="assistant-mode flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-2 py-3 text-sm font-semibold hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={() => {
                            setMode(m);
                            setReply(undefined);
                            setError("");
                          }}
                        >
                          <Icon aria-hidden className="size-4" />
                          {labels[m]}
                        </button>
                      );
                    })}
                  </div>
                  {mode !== "docs" && !current().nodes.length && (
                    <label className="grid gap-1 text-sm">
                      Input dataset
                      <Select
                        aria-label="Input dataset"
                        disabled={!!busy}
                        value={dataset}
                        onChange={(e) => {
                          setDataset(e.target.value);
                          setSecondDataset("");
                          setLookup("");
                          setTarget("");
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
                  {mode === "build" &&
                    !current().nodes.length &&
                    datasets.some(
                      (d) => d.id === dataset && d.source_type === "csv",
                    ) && (
                      <label className="grid gap-1 text-sm">
                        Right input for Join (optional)
                        <Select
                          aria-label="Right input for Join"
                          value={secondDataset}
                          disabled={!!busy}
                          onChange={(e) => {
                            setSecondDataset(e.target.value);
                            setLookup("");
                            setTarget("");
                            setReply(undefined);
                          }}
                        >
                          <option value="">Use one input</option>
                          {datasets
                            .filter(
                              (d) =>
                                !d.is_disabled &&
                                d.source_type === "csv" &&
                                d.id !== dataset,
                            )
                            .map((d) => (
                              <option key={d.id} value={d.id}>
                                {d.name}
                              </option>
                            ))}
                        </Select>
                        {secondDataset && !training && (
                          <span className="text-xs text-muted-foreground">
                            The first dataset is the left input. A left Join
                            keeps every row from it.
                          </span>
                        )}
                      </label>
                    )}
                  {mlEnabled &&
                    secondDataset &&
                    mode === "build" &&
                    !current().nodes.length && (
                      <label className="grid gap-1 text-sm">
                        Second lookup for regression (optional)
                        <Select
                          value={lookup}
                          disabled={!!busy}
                          onChange={(e) => {
                            setLookup(e.target.value);
                            setTarget("");
                            setReply(undefined);
                          }}
                        >
                          <option value="">Use one Join</option>
                          {datasets
                            .filter(
                              (d) =>
                                !d.is_disabled &&
                                d.source_type === "csv" &&
                                d.id !== dataset &&
                                d.id !== secondDataset,
                            )
                            .map((d) => (
                              <option key={d.id} value={d.id}>
                                {d.name}
                              </option>
                            ))}
                        </Select>
                      </label>
                    )}
                  {training && (
                    <label className="grid gap-1 text-sm">
                      Regression target
                      <Select
                        value={target}
                        disabled={!!busy}
                        onChange={(e) => {
                          setTarget(e.target.value);
                          setReply(undefined);
                        }}
                      >
                        <option value="">Choose a numeric outcome</option>
                        {fact?.column_schema
                          ?.slice(0, 64)
                          .filter(
                            (c) =>
                              ["integer", "float"].includes(c.type) &&
                              !selectedInputs
                                .slice(1)
                                .some((d) =>
                                  d?.column_schema?.some(
                                    (other) => other.name === c.name,
                                  ),
                                ),
                          )
                          .map((c) => (
                            <option key={c.name}>{c.name}</option>
                          ))}
                      </Select>
                    </label>
                  )}
                  {ready && !question && mode !== "docs" && !training && (
                    <button
                      className="justify-self-start rounded-full border border-border px-3 py-1 text-xs font-medium hover:bg-muted focus-visible:ring-2"
                      onClick={() =>
                        setQuestion(
                          mode === "diagnose"
                            ? "Check the most recent failure"
                            : secondDataset
                              ? "Keep all rows from the left input"
                              : "Keep the first 10 rows",
                        )
                      }
                    >
                      {mode === "diagnose"
                        ? "Check the last failure"
                        : secondDataset
                          ? "Keep all left rows"
                          : "Keep the first 10 rows"}
                    </button>
                  )}
                  <label className="grid gap-1 text-sm">
                    Request
                    <textarea
                      aria-label="Request"
                      className="min-h-20 rounded-xl border border-input bg-card p-3 placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-primary"
                      disabled={!!busy}
                      maxLength={1500}
                      placeholder={
                        mode === "docs"
                          ? "How do I export Polars code?"
                          : mode === "build"
                            ? training
                              ? "Predict shipping cost and evaluate on held-out orders"
                              : "Keep the first 100 rows"
                            : "Why did this flow fail?"
                      }
                      value={question}
                      onChange={(e) => {
                        setQuestion(e.target.value);
                        setReply(undefined);
                      }}
                    />
                  </label>
                  <details className="text-xs text-muted-foreground">
                    <summary className="cursor-pointer font-medium text-foreground">
                      <ShieldCheck
                        aria-hidden
                        className="mr-1 inline size-4 text-primary"
                      />
                      Data shared with provider
                    </summary>
                    <div className="mt-2 space-y-2 leading-relaxed">
                      <p>
                        {mode === "docs"
                          ? "Sends your request and matching passages from the bundled guides."
                          : training
                            ? "Sends your request and temporary references for the joins, selected target and numeric predictors. Column names are optional. Files, rows and filenames stay out of the provider request."
                            : "Sends your request, node types and connections, column types and indexes. Join requests can include matching key indexes or the current Join mode. Diagnosis can include a failure category. Rows, filenames, raw errors and code stay local."}{" "}
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
                  </details>
                  <CanvasHelp
                    validation={validation}
                    inspectNode={inspectNode}
                  />
                </>
              ) : (
                <CanvasHelp validation={validation} inspectNode={inspectNode} />
              )}
              <div role="status" aria-live="polite">
                {busy === "generate"
                  ? "Waiting for provider…"
                  : busy === "apply"
                    ? "Saving proposal…"
                    : reply?.proposal && mode !== "diagnose"
                      ? null
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
                <ProposalReview
                  delta={reply.delta}
                  base={base}
                  datasets={datasets}
                  inspectNode={inspectNode}
                />
              )}
            </div>
            <div className="mt-auto flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-border bg-card px-5 py-3">
              <span className="mr-auto text-xs text-muted-foreground">
                {service.data?.model ?? "Local workspace"}
              </span>
              {busy === "generate" && (
                <Button variant="outline" onClick={cancel}>
                  Cancel request
                </Button>
              )}
              {reply?.proposal && (
                <Button
                  className="hover:bg-primary"
                  disabled={!!busy || disabled}
                  onClick={() => void confirm()}
                >
                  Apply and save
                </Button>
              )}
              {ready && !reply?.proposal && (
                <Button
                  disabled={
                    !!busy ||
                    !ready ||
                    !question.trim() ||
                    (training && (!target || !mlEnabled)) ||
                    (mode !== "docs" && disabled)
                  }
                  onClick={() => void generate()}
                >
                  {mode === "build"
                    ? "Create proposal"
                    : mode === "diagnose"
                      ? "Diagnose flow"
                      : "Ask the guides"}
                </Button>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
