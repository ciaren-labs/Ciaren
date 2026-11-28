import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  BookOpen,
  Database,
  GitPullRequest,
  History,
  KeyRound,
  MessageSquare,
  ShieldCheck,
  Stethoscope,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { Dataset } from "@/features/datasets/types";
import type { Flow, GraphJson } from "@/features/flows/types";
import { graphToStore } from "@/features/flows/graphMapper";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { useMlEnabled } from "@/features/models/hooks";
import { request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  activityKey,
  activityUrl,
  applyDelta,
  confirmReversal,
  expiryOf,
  headingId,
  loadFlow,
  previewReversal,
  sameInstant,
  sendTurn,
  status,
  type ActivityPage,
  type ApplyResult,
  type Inputs,
  type Mode,
  type Suggestion,
  type Turn,
} from "./api";

import { useReactFlow } from "@xyflow/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { FlowValidation } from "@/features/flows/editor/flowValidation";
import { CanvasHelp } from "./CanvasHelp";
import { Activity } from "./Activity";
import { AssistantMark } from "./AssistantMark";
import { deltaCounts, summaryParts } from "./changeSummary";
import { suggestedPrompts } from "./suggestions";
import {
  AnswerCard,
  ChoiceCard,
  GuidanceCard,
  PromptChips,
  ProposalCard,
  StatusCard,
  Thinking,
} from "./ReplyCards";

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
  /** Saves the canvas through the editor; resolves with the new revision, or null when nothing was saved. */
  save: () => Promise<string | null>;
  /** Moves focus to the node palette for a manual edit. */
  focusPalette: () => void;
  /** Canvas element that hosts a floating launcher, so the assistant is easy to find. */
  floatingHost?: HTMLElement | null;
  /** Editor column the panel docks into beside the canvas; without it the panel floats at the right edge. */
  dockHost?: HTMLElement | null;
}
type Saved = { revision: string; graph: GraphJson; session: number };
type Toast = { saved?: Saved; message: string; busy?: boolean };

const labels: Record<Mode, string> = {
  build: "Build",
  docs: "Guides",
  diagnose: "Diagnose",
};
const NARROW = "(max-width: 639px)";
const TOAST_MS = 12000;
/** A request held back because Build and Diagnose read the saved flow. */
type Held = { text: string; mode: Mode; inputs: Inputs; server?: boolean };

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
  save,
  focusPalette,
  floatingHost,
  dockHost,
}: Props) {
  const client = useQueryClient();
  const [tab, setTab] = useState("conversation");
  const [reversing, setReversing] = useState(false);
  const { fitView } = useReactFlow();
  const [open, setOpen] = useState(false);
  const [unseen, setUnseen] = useState(false);
  const [mode, setMode] = useState<Mode>("build");
  const [question, setQuestion] = useState("");
  const [held, setHeld] = useState<Held | null>(null);
  const dirty = useFlowEditorStore((s) => s.dirty);
  const nudgeSave = useFlowEditorStore((s) => s.nudgeSave);
  const [dataset, setDataset] = useState("");
  const [secondDataset, setSecondDataset] = useState("");
  const [lookup, setLookup] = useState("");
  const [target, setTarget] = useState("");
  const [shareNames, setShareNames] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [applying, setApplying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [toast, setToast] = useState<Toast>();
  const [toastPaused, setToastPaused] = useState(false);
  const mlEnabled = useMlEnabled();
  const empty = !current().nodes.length;
  const canvasInput = current().nodes.find((n) => n.type === "fileInput")?.data
    .config.dataset_id;
  const fact = datasets.find((d) => d.id === (empty ? dataset : canvasInput));
  const training = mode === "build" && !!lookup && empty;
  const abort = useRef<AbortController | null>(null);
  const openedFrom = useRef<"header" | "launcher">("header");
  const wasOpen = useRef(false);
  // Set when closing for a manual edit, so focus goes to the palette, not the opener.
  const toPalette = useRef(false);
  const composerFocused = useRef(false);
  const headerButton = useRef<HTMLButtonElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const cancelButton = useRef<HTMLButtonElement | null>(null);
  // Where focus goes after the next render: "composer", "cancel" or an element id.
  const focusNext = useRef<string | undefined>(undefined);
  const setFocusNext = (target: string) => {
    focusNext.current = target;
  };
  const latestRevision = useRef(revision);
  useEffect(() => {
    latestRevision.current = revision;
  }, [revision]);
  const pending = turns.some((t) => t.state === "pending");
  const busy = pending || applying || reversing || saving;
  const service = useQuery({
    queryKey: ["assistant-status", flowId],
    queryFn: status,
    enabled: open,
    retry: false,
    staleTime: 0,
  });
  const ready = service.data?.state === "configured";
  const live = [...turns]
    .reverse()
    .find((t) => t.reply?.proposal && t.reply.delta && !t.outcome);

  useEffect(
    () => () => {
      abort.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (!open || tab !== "conversation" || !live?.reply?.delta) return;
    // The highlight is presentational and disappears when the preview closes.
    // Keeping it outside the graph prevents it entering saves or undo history.
    const highlights = live.reply.delta.changed.flatMap((node) => {
      const el = document.querySelector<HTMLElement>(
        `.react-flow__node[data-id="${CSS.escape(node.id)}"]`,
      );
      if (!el) return [];
      el.classList.add("assistant-review-node");
      return [el];
    });
    return () =>
      highlights.forEach((el) => el.classList.remove("assistant-review-node"));
  }, [open, tab, live]);
  // Focus follows the conversation: the composer on open, Cancel while
  // waiting, the reply heading when it lands, and the opener on close.
  useEffect(() => {
    if (open && ready && !composerFocused.current) {
      composerFocused.current = true;
      textarea.current?.focus();
    }
    if (!open) composerFocused.current = false;
  }, [open, ready]);
  useEffect(() => {
    if (!open && wasOpen.current) {
      if (toPalette.current) focusPalette();
      else
        (openedFrom.current === "launcher" && launcher.current
          ? launcher.current
          : headerButton.current
        )?.focus();
      toPalette.current = false;
    }
    wasOpen.current = open;
  }, [open, focusPalette]);
  useEffect(() => {
    const next = focusNext.current;
    if (!open || !next) return;
    focusNext.current = undefined;
    if (next === "composer") textarea.current?.focus();
    else if (next === "cancel") cancelButton.current?.focus();
    else document.getElementById(next)?.focus();
  });
  useEffect(() => {
    if (!toast || toastPaused || toast.busy) return;
    const timer = setTimeout(() => setToast(undefined), TOAST_MS);
    return () => clearTimeout(timer);
  }, [toast, toastPaused]);

  // A click removes a hovered or focused toast without mouseleave or blur.
  function dismissToast() {
    setToast(undefined);
    setToastPaused(false);
  }
  function openPanel(from: "header" | "launcher") {
    openedFrom.current = from;
    setUnseen(false);
    setTab("conversation");
    setOpen(true);
  }
  function close() {
    if (applying || reversing) return;
    setOpen(false);
  }
  function update(id: string, patch: Partial<Turn>) {
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }
  function cancel() {
    abort.current?.abort();
  }
  function trainingVersions(inputs: Inputs) {
    const chosen = [inputs.dataset, inputs.secondDataset, inputs.lookup].map(
      (id) => datasets.find((d) => d.id === id),
    );
    return chosen.every((d) => d && d.latest_version > 0)
      ? chosen.map((d) => d!.latest_version)
      : null;
  }
  const composerInputs: Inputs = {
    dataset,
    secondDataset,
    lookup,
    target,
    shareNames,
  };
  const staleTraining = training && !trainingVersions(composerInputs);

  async function generate(text: string, turnMode: Mode, inputs: Inputs, at = revision) {
    if (!service.data || !text.trim() || pending) return;
    const snapshot = current();
    const asTraining =
      turnMode === "build" && !!inputs.lookup && !snapshot.nodes.length;
    const versions = asTraining ? trainingVersions(inputs) : null;
    if (asTraining && !versions) return;
    if (turnMode !== "docs" && useFlowEditorStore.getState().dirty) {
      // The server refuses a canvas that differs from the saved flow: keep the request in
      // the composer and point at Save instead of adding a card to the conversation.
      hold({ text, mode: turnMode, inputs });
      return;
    }
    setHeld(null);
    const controller = new AbortController();
    const requestId = crypto.randomUUID();
    const id = requestId;
    controller.signal.addEventListener(
      "abort",
      () => {
        update(id, { state: "cancelled" });
        setFocusNext("composer");
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
    const session = useFlowEditorStore.getState().sessionId;
    setTurns((all) => [
      ...all.map((t) =>
        t.reply?.proposal && !t.outcome
          ? { ...t, outcome: "superseded" as const }
          : t,
      ),
      {
        id,
        mode: turnMode,
        question: text,
        inputs,
        state: "pending",
        base: snapshot,
        session,
      },
    ]);
    setQuestion("");
    setShareNames(false);
    setAnnouncement("");
    setFocusNext("cancel");
    const sendsDataset = turnMode !== "docs" && !snapshot.nodes.length;
    try {
      const result = await sendTurn(
          flowId,
          {
            mode: turnMode,
            request_id: requestId,
            question: text,
            revision: at,
            provider: service.data.provider,
            // Lets the server refuse a canvas that differs from the saved flow.
            ...(turnMode !== "docs" && { graph: snapshot }),
            dataset_id: sendsDataset ? inputs.dataset || null : null,
            second_dataset_id:
              turnMode === "build" && !snapshot.nodes.length
                ? inputs.secondDataset || null
                : null,
            ...(asTraining && {
              training: {
                dataset_id: inputs.lookup,
                versions,
                target: inputs.target,
              },
            }),
            share_names: inputs.shareNames,
            ...(inputs.answers?.length && {
              clarifications: inputs.answers.map(({ question, answer }) => ({ question, answer })),
            }),
          },
          controller.signal,
        );
      if (controller.signal.aborted) return;
      if (result.reason === "unsaved_changes") {
        setTurns((all) => all.filter((t) => t.id !== id));
        hold({ text, mode: turnMode, inputs, server: true });
        return;
      }
      const proposal = !!(result.proposal && result.delta);
      update(id, {
        state: "reply",
        reply: result,
        expiresAt: proposal ? expiryOf(result) : undefined,
      });
      setAnnouncement(
        proposal
          ? `Proposal ready: ${summaryParts(deltaCounts(result.delta!, snapshot)).join(", ")}`
          : result.reason === "needs_choice"
            ? `The assistant asks: ${result.message}`
            : result.citation || turnMode === "docs"
              ? "Answer ready"
              : "No change proposed",
      );
      setFocusNext(headingId({ id }));
      if (!wasOpen.current) setUnseen(true);
    } catch (err) {
      if (controller.signal.aborted) return;
      update(id, {
        state: "error",
        error: err instanceof Error ? err.message : "Request failed.",
      });
      setFocusNext(headingId({ id }));
    } finally {
      if (abort.current === controller) abort.current = null;
    }
  }
  function hold(request: Held) {
    setHeld(request);
    setQuestion(request.text);
    nudgeSave();
    setFocusNext("composer");
  }
  async function saveAndSend() {
    if (!held) return;
    setSaving(true);
    try {
      const at = await save();
      if (at) void generate(question.trim() ? question : held.text, held.mode, held.inputs, at);
    } finally {
      setSaving(false);
    }
  }
  function submit() {
    if (!question.trim() || (training && (!target || !mlEnabled))) return;
    if (mode !== "docs" && disabled) return;
    void generate(question, mode, composerInputs);
  }
  function matchesBase(turn: Turn) {
    return (
      turn.session === useFlowEditorStore.getState().sessionId &&
      JSON.stringify(current()) === JSON.stringify(turn.base)
    );
  }
  async function confirm(turn: Turn) {
    const reply = turn.reply;
    if (!reply?.proposal || !reply.delta || !turn.base || disabled) return;
    if (!matchesBase(turn)) {
      update(turn.id, {
        outcome: "discarded",
        state: "error",
        error: "The canvas changed. Generate a fresh proposal.",
      });
      return;
    }
    setApplying(true);
    try {
      const result = await request<ApplyResult>(
        `/assistant/flows/${flowId}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ proposal: reply.proposal }),
          redirect: "error",
        },
      );
      void client.invalidateQueries({ queryKey: activityKey(projectId, flowId) });
      if (matchesBase(turn)) {
        // The server's saved graph is authoritative; the local delta covers servers that omit it.
        const graph = result.graph ?? applyDelta(turn.base, reply.delta);
        const next = graphToStore(graph);
        useFlowEditorStore.getState().acceptProposal(next.nodes, next.edges);
        saved(result.revision, graph);
        update(turn.id, { outcome: "applied" });
        setFocusNext("composer");
        setToast({
          message: "Proposal applied to the flow.",
          saved: {
            revision: result.revision,
            graph,
            session: useFlowEditorStore.getState().sessionId,
          },
        });
      } else {
        update(turn.id, { outcome: "applied" });
        setFocusNext("composer");
        setToast({
          message:
            "Saved on the server while the canvas changed. Reload to reconcile both versions.",
        });
      }
    } catch (err) {
      update(turn.id, {
        outcome: "discarded",
        state: "error",
        error:
          err instanceof Error
            ? err.message
            : "Confirmation failed. Reload before retrying.",
      });
    } finally {
      setApplying(false);
    }
  }
  /** Reverts the entry the apply just recorded, through the same API as Activity. */
  async function undo(change: Saved) {
    const unchanged = () =>
      !useFlowEditorStore.getState().dirty &&
      useFlowEditorStore.getState().sessionId === change.session &&
      JSON.stringify(current()) === JSON.stringify(change.graph);
    if (!unchanged()) {
      setToast({
        message: "The canvas changed after saving. Review the reversal in Activity.",
      });
      return;
    }
    setToast({ message: "Undoing…", busy: true });
    setReversing(true);
    let committed = false;
    try {
      const page = await request<ActivityPage>(activityUrl(flowId), {
        cache: "no-store",
      });
      const entry = page.entries.find(
        (e) => e.source !== "revert" && sameInstant(e.date, change.revision),
      );
      if (entry?.state !== "available") {
        setToast({
          message: "This change cannot be undone automatically. Review it in Activity.",
        });
        return;
      }
      const preview = await previewReversal(
        flowId,
        entry.id,
        latestRevision.current,
      );
      const result = await confirmReversal(flowId, entry.id, preview.confirmation);
      committed = true;
      const flow = await loadFlow(flowId);
      if (unchanged() && flow.updated_at === result.revision) {
        restored(flow);
        setToast({ message: "Change undone." });
      } else setToast({ message: "Undone. Reload when your local edits are safe." });
    } catch (err) {
      setToast({
        message: committed
          ? "Undone. Reload to see the latest flow."
          : err instanceof Error
            ? err.message
            : "Undo failed. Review the change in Activity.",
      });
    } finally {
      void client.invalidateQueries({ queryKey: activityKey(projectId, flowId) });
      setReversing(false);
    }
  }
  function inspectNode(id: string) {
    useFlowEditorStore.getState().selectNode(id);
    // The full-width sheet would hide the node; the conversation survives closing.
    if (window.matchMedia(NARROW).matches) close();
    void fitView({
      nodes: [{ id }],
      maxZoom: 1.2,
      padding: 0.35,
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 0
        : 180,
    });
  }
  function choose(prompt: string) {
    setQuestion(prompt);
    setFocusNext("composer");
  }
  async function act(turn: Turn, suggestion: Suggestion) {
    const again = (inputs = turn.inputs, at?: string) =>
      void generate(turn.question, turn.mode, inputs, at);
    switch (suggestion.action) {
      case "save": {
        setSaving(true);
        try {
          const at = await save();
          if (at) again(turn.inputs, at);
        } finally {
          setSaving(false);
        }
        return;
      }
      case "switch_mode":
        if (suggestion.target && Object.keys(labels).includes(suggestion.target)) {
          setMode(suggestion.target as Mode);
          choose(turn.question);
        }
        return;
      case "manual_edit":
        toPalette.current = true;
        close();
        return;
      case "share_names":
        return again({ ...turn.inputs, shareNames: true });
      case "retry":
        return again();
    }
  }
  function edit(turn: Turn) {
    setMode(turn.mode);
    setDataset(turn.inputs.dataset);
    setSecondDataset(turn.inputs.secondDataset);
    setLookup(turn.inputs.lookup);
    setTarget(turn.inputs.target);
    choose(turn.question);
  }

  const prompts = suggestedPrompts({
    mode,
    dataset: fact,
    target,
    training,
    joined: !!secondDataset && empty,
    ml: mlEnabled,
  });
  const canSubmit =
    ready &&
    !busy &&
    !!question.trim() &&
    !(training && (!target || !mlEnabled || staleTraining)) &&
    !(mode !== "docs" && disabled);
  const ModeIcon = { build: GitPullRequest, docs: BookOpen, diagnose: Stethoscope };

  const panel = (
    <section
      role="dialog"
      aria-labelledby="assistant-title"
      aria-describedby="assistant-flow"
      id="assistant-panel"
      onKeyDown={(e) => {
        if (e.key === "Escape" && !e.defaultPrevented) {
          e.preventDefault();
          close();
        }
      }}
      className={cn(
        "assistant-panel flex min-h-0 w-[26rem] min-[1280px]:max-[1456px]:w-[22rem] shrink-0 flex-col border-l border-border bg-background max-sm:fixed max-sm:inset-0 max-sm:z-50 max-sm:w-full max-sm:border-l-0",
        dockHost ? "h-full" : "fixed inset-y-0 right-0 z-40 shadow-xl",
      )}
    >
      <div className="assistant-mast flex items-center gap-3 px-4 py-3">
        <span className="assistant-mast__mark grid size-9 shrink-0 place-items-center rounded-xl">
          <AssistantMark className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="assistant-title" className="text-base font-semibold leading-tight">
            Flow assistant
          </h2>
          <p id="assistant-flow" className="assistant-mast__sub truncate text-xs">
            {flowName}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="assistant-mast__close size-9 px-0"
          aria-label="Close assistant"
          disabled={applying || reversing}
          onClick={close}
        >
          <X aria-hidden className="size-4" />
        </Button>
      </div>
      <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
        <TabsList
          aria-label="Assistant sections"
          className="mx-4 my-3 grid h-10 shrink-0 grid-cols-2"
        >
          <TabsTrigger value="conversation" disabled={reversing} className="min-h-8 motion-reduce:transition-none">
            <MessageSquare aria-hidden className="mr-2 size-4" />
            Conversation
          </TabsTrigger>
          <TabsTrigger value="activity" disabled={pending || applying} className="min-h-8 motion-reduce:transition-none">
            <History aria-hidden className="mr-2 size-4" />
            Activity
          </TabsTrigger>
        </TabsList>
        <TabsContent value="activity" className="mt-0 min-h-0 overflow-y-auto px-4 pb-5">
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
          <div className="grid min-h-0 flex-1 content-start gap-4 overflow-y-auto px-4 pb-4 pt-1">
            {!ready ? (
              <>
                <section
                  role="status"
                  className="assistant-card assistant-card--primary place-items-start"
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
                    className="inline-flex min-h-8 items-center rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground focus-visible:ring-2"
                  >
                    Open settings
                  </Link>
                </section>
                <CanvasHelp validation={validation} inspectNode={inspectNode} />
              </>
            ) : (
              !turns.length && (
                <section aria-label="Get started" className="grid gap-3">
                  <div>
                    <h3 className="text-base font-semibold">
                      {mode === "docs"
                        ? "Ask the Ciaren guides"
                        : mode === "diagnose"
                          ? "Diagnose this flow"
                          : empty
                            ? "Start this flow from a dataset"
                            : "Describe the next change"}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {mode === "docs"
                        ? "Answers cite the bundled guide they come from."
                        : mode === "diagnose"
                          ? "Explains the latest failed run. You review any fix before it is saved."
                          : "Describe the result in plain words: cleaning, joins, aggregations, features, models or charts. You review every node and connection before anything is saved."}
                    </p>
                  </div>
                  {mode !== "docs" && (
                    <p className="assistant-dataset-chip">
                      <Database aria-hidden className="size-3.5 text-primary" />
                      {fact ? (
                        <>
                          <span className="font-medium">{fact.name}</span>
                          <span className="text-muted-foreground">
                            · {fact.column_schema?.length ?? 0} columns
                          </span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">
                          {empty ? "Choose an input dataset below" : "Input from the canvas"}
                        </span>
                      )}
                    </p>
                  )}
                  {prompts.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Try
                      </p>
                      <PromptChips prompts={prompts} choose={choose} />
                    </div>
                  )}
                  <CanvasHelp validation={validation} inspectNode={inspectNode} />
                </section>
              )
            )}
            {turns.length > 0 && (
              <ol aria-label="Conversation" className="grid gap-3">
                {turns.flatMap((turn) => [
                  <li key={`${turn.id}-q`} className="assistant-request">
                    <span className="sr-only">You asked: </span>
                    {turn.question}
                    {turn.inputs.answers?.map((a, i) => (
                      <span key={i} className="assistant-request__answer">
                        <span className="sr-only">You chose: </span>
                        {a.label}
                      </span>
                    ))}
                  </li>,
                  <li key={`${turn.id}-a`}>
                    {turn.state === "pending" ? (
                      <Thinking
                        mode={turn.mode}
                        cancel={cancel}
                        cancelRef={(el) => {
                          cancelButton.current = el;
                        }}
                      />
                    ) : turn.state !== "reply" ? (
                      <StatusCard turn={turn} />
                    ) : turn.reply?.proposal && turn.reply.delta ? (
                      <ProposalCard
                        turn={turn}
                        latest={turn === live}
                        datasets={datasets}
                        disabled={disabled}
                        busy={busy}
                        inspectNode={inspectNode}
                        apply={() => void confirm(turn)}
                        discard={() => {
                          update(turn.id, { outcome: "discarded" });
                          setFocusNext("composer");
                        }}
                        edit={() => edit(turn)}
                        regenerate={() => void generate(turn.question, turn.mode, turn.inputs)}
                      />
                    ) : turn.reply?.reason === "needs_choice" && turn.reply.ask && turn.reply.choices?.length ? (
                      <ChoiceCard
                        turn={turn}
                        busy={busy || turn !== turns[turns.length - 1]}
                        choose={(choice) =>
                          void generate(turn.question, turn.mode, {
                            ...turn.inputs,
                            answers: [
                              ...(turn.inputs.answers ?? []),
                              // The raw question: the shown message can hold real names.
                              {
                                question: turn.reply!.ask!,
                                answer: choice.reply,
                                label: choice.label,
                              },
                            ],
                          })
                        }
                      />
                    ) : turn.mode === "docs" || turn.reply?.citation ? (
                      <AnswerCard turn={turn} />
                    ) : (
                      <GuidanceCard
                        turn={turn}
                        busy={busy}
                        act={(suggestion) => void act(turn, suggestion)}
                      />
                    )}
                  </li>,
                ])}
              </ol>
            )}
          </div>
          {ready && (
            <form
              className="assistant-composer grid max-h-[60%] shrink-0 gap-2 overflow-y-auto border-t border-border bg-card px-4 py-3"
              onSubmit={(e) => {
                e.preventDefault();
                submit();
              }}
            >
              <div role="group" aria-label="Task" className="grid grid-cols-3 gap-1.5">
                {(Object.keys(labels) as Mode[]).map((m) => {
                  const Icon = ModeIcon[m];
                  return (
                    <button
                      key={m}
                      type="button"
                      aria-pressed={m === mode}
                      disabled={busy}
                      className="assistant-mode flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-background px-2 text-sm font-semibold hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={() => setMode(m)}
                    >
                      <Icon aria-hidden className="size-4" />
                      {labels[m]}
                    </button>
                  );
                })}
              </div>
              {mode !== "docs" && empty && (
                <label className="grid gap-1 text-sm">
                  Input dataset
                  <Select
                    aria-label="Input dataset"
                    disabled={busy}
                    value={dataset}
                    onChange={(e) => {
                      setDataset(e.target.value);
                      setSecondDataset("");
                      setLookup("");
                      setTarget("");
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
                empty &&
                datasets.some((d) => d.id === dataset && d.source_type === "csv") && (
                  <label className="grid gap-1 text-sm">
                    Right input for Join (optional)
                    <Select
                      aria-label="Right input for Join"
                      value={secondDataset}
                      disabled={busy}
                      onChange={(e) => {
                        setSecondDataset(e.target.value);
                        setLookup("");
                        setTarget("");
                      }}
                    >
                      <option value="">Use one input</option>
                      {datasets
                        .filter(
                          (d) => !d.is_disabled && d.source_type === "csv" && d.id !== dataset,
                        )
                        .map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name}
                          </option>
                        ))}
                    </Select>
                    {secondDataset && !training && (
                      <span className="text-xs text-muted-foreground">
                        The first dataset is the left input. A left Join keeps every row from it.
                      </span>
                    )}
                  </label>
                )}
              {mlEnabled && secondDataset && mode === "build" && empty && (
                <label className="grid gap-1 text-sm">
                  Second lookup for regression (optional)
                  <Select
                    value={lookup}
                    disabled={busy}
                    onChange={(e) => {
                      setLookup(e.target.value);
                      setTarget("");
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
                  <Select value={target} disabled={busy} onChange={(e) => setTarget(e.target.value)}>
                    <option value="">Choose a numeric outcome</option>
                    {fact?.column_schema
                      ?.slice(0, 64)
                      .filter(
                        (c) =>
                          ["integer", "float"].includes(c.type) &&
                          ![secondDataset, lookup]
                            .map((id) => datasets.find((d) => d.id === id))
                            .some((d) => d?.column_schema?.some((other) => other.name === c.name)),
                      )
                      .map((c) => (
                        <option key={c.name}>{c.name}</option>
                      ))}
                  </Select>
                </label>
              )}
              {staleTraining && (
                <p className="text-xs text-muted-foreground">
                  A selected dataset is no longer available. Choose the inputs again.
                </p>
              )}
              <label className="grid gap-1 text-sm">
                <span className="sr-only">Request</span>
                <textarea
                  ref={textarea}
                  aria-label="Request"
                  aria-describedby="assistant-submit-hint"
                  className="min-h-20 rounded-xl border border-input bg-background p-3 placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-primary"
                  disabled={busy}
                  maxLength={1500}
                  placeholder={
                    mode === "docs"
                      ? "How do I export Polars code?"
                      : mode === "build"
                        ? training
                          ? "Predict shipping cost and evaluate on held-out orders"
                          : "Join orders with customers and aggregate revenue by month"
                        : "Why did this flow fail?"
                  }
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      if (canSubmit) submit();
                    }
                  }}
                />
              </label>
              {mode !== "docs" && disabled && (
                <p className="text-xs text-muted-foreground">
                  This flow is disabled. Re-enable it from the banner above the canvas to create or
                  apply proposals. Guides still work.
                </p>
              )}
              <details className="text-xs text-muted-foreground">
                <summary className="flex min-h-8 cursor-pointer items-center gap-1 font-medium text-foreground">
                  <ShieldCheck aria-hidden className="size-4 text-primary" />
                  Data shared with provider
                </summary>
                <div className="mt-1 space-y-2 leading-relaxed">
                  <p>
                    {mode === "docs"
                      ? "Sends your request and matching passages from the bundled guides."
                      : training
                        ? "Sends your request and temporary references for the joins, selected target and numeric predictors. Column names are optional. Files, rows and filenames stay out of the provider request."
                        : "Sends your request, node types and connections, column types and indexes. Join requests can include matching key indexes or the current Join mode. Diagnosis can include a failure category. Rows, filenames, raw errors and code stay local."}{" "}
                    Keep secrets out of your request.
                  </p>
                  {mode !== "docs" && (
                    <label className="flex min-h-8 items-center gap-2">
                      <input
                        type="checkbox"
                        checked={shareNames}
                        disabled={busy}
                        onChange={(e) => setShareNames(e.target.checked)}
                      />
                      Include column names in this request
                    </label>
                  )}
                </div>
              </details>
              {held && (held.server || dirty) && (
                <div role="status" className="assistant-save-hint">
                  <span className="mr-auto">
                    {held.server
                      ? "The saved flow differs from the canvas. Save it to continue."
                      : "Unsaved canvas changes. The assistant works from the saved flow."}
                  </span>
                  <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void saveAndSend()}>
                    Save and send
                  </Button>
                </div>
              )}
              <div className="flex items-center justify-end gap-2">
                <span id="assistant-submit-hint" className="mr-auto truncate text-xs text-muted-foreground">
                  {service.data?.model} · Ctrl+Enter to send
                </span>
                <Button type="submit" size="sm" disabled={!canSubmit}>
                  {mode === "build"
                    ? "Create proposal"
                    : mode === "diagnose"
                      ? "Diagnose flow"
                      : "Ask the guides"}
                </Button>
              </div>
            </form>
          )}
        </TabsContent>
      </Tabs>
    </section>
  );

  return (
    <>
      <Button
        ref={headerButton}
        size="sm"
        variant="outline"
        aria-expanded={open}
        aria-controls={open ? "assistant-panel" : undefined}
        className="relative shrink-0 border-primary/40 text-foreground"
        onClick={() => (open ? close() : openPanel("header"))}
      >
        <AssistantMark className="size-4 text-primary" />
        Assistant
        {unseen && !open && (
          <>
            <span data-unseen aria-hidden className="absolute -right-1 -top-1 size-2.5 rounded-full bg-primary ring-2 ring-background" />
            <span className="sr-only">, new reply</span>
          </>
        )}
      </Button>
      {floatingHost &&
        !open &&
        createPortal(
          <button
            ref={launcher}
            type="button"
            onClick={() => openPanel("launcher")}
            aria-label="Ask the flow assistant"
            className="assistant-launcher absolute bottom-4 left-1/2 z-10 flex min-h-10 -translate-x-1/2 items-center gap-2 rounded-full border border-primary/30 bg-background/95 py-1.5 pl-1.5 pr-4 text-sm font-medium text-foreground shadow-lg backdrop-blur transition hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none motion-reduce:hover:translate-y-0"
          >
            <span className="assistant-mast__mark grid size-7 place-items-center rounded-full">
              <AssistantMark className="size-4" />
            </span>
            Ask the assistant
          </button>,
          floatingHost,
        )}
      {open && createPortal(panel, dockHost ?? document.body)}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {toast &&
        createPortal(
          <div
            role="status"
            aria-labelledby="assistant-toast-title"
            onMouseEnter={() => setToastPaused(true)}
            onMouseLeave={() => setToastPaused(false)}
            onFocus={() => setToastPaused(true)}
            onBlur={() => setToastPaused(false)}
            className="assistant-toast"
          >
            <AssistantMark className="size-4 shrink-0 text-primary" />
            <p className="min-w-0 flex-1 text-sm">
              <span id="assistant-toast-title" className="font-semibold">
                {toast.saved ? "Saved" : "Assistant"}
              </span>
              <span className="text-muted-foreground"> · {toast.message}</span>
            </p>
            {toast.saved && (
              <Button
                size="sm"
                variant="outline"
                disabled={reversing}
                onClick={() => void undo(toast.saved!)}
              >
                Undo
              </Button>
            )}
            {!toast.busy && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  dismissToast();
                  openPanel(openedFrom.current);
                  setTab("activity");
                }}
              >
                View in Activity
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="size-9 px-0"
              aria-label="Dismiss"
              disabled={toast.busy}
              onClick={dismissToast}
            >
              <X aria-hidden className="size-4" />
            </Button>
          </div>,
          document.body,
        )}
    </>
  );
}
