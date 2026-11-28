import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Ban, Check, CircleAlert, Clock, Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Dataset } from "@/features/datasets/types";
import { cn } from "@/lib/utils";
import { headingId, type Conflict, type Mode, type Reason, type Suggestion, type Turn } from "./api";
import { ProposalReview } from "./ProposalReview";

const count = (n: number, word: string) =>
  `${n.toLocaleString("en-US")} ${word}${n === 1 ? "" : "s"}`;
const plain = (text: string) =>
  text.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1");

function Card({
  turn,
  tone = "primary",
  icon,
  title,
  children,
}: {
  turn: Turn;
  tone?: "primary" | "muted" | "destructive";
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <article
      aria-labelledby={headingId(turn)}
      className={cn("assistant-card", `assistant-card--${tone}`)}
    >
      <h3
        id={headingId(turn)}
        tabIndex={-1}
        className="flex items-center gap-2 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {icon}
        {title}
      </h3>
      {children}
    </article>
  );
}

const STEPS: Record<Mode, string[]> = {
  build: ["Reading schema", "Planning", "Validating"],
  diagnose: ["Reading schema", "Planning", "Validating"],
  docs: ["Searching guides", "Writing answer"],
};

/** Paced locally: the server reports no progress, so the last step stays current until the reply. */
export function Thinking({
  mode,
  cancel,
  cancelRef,
}: {
  mode: Mode;
  cancel: () => void;
  cancelRef: (el: HTMLButtonElement | null) => void;
}) {
  const steps = STEPS[mode];
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timers = [2500, 6000].map((ms, i) =>
      setTimeout(() => setStep((s) => Math.max(s, Math.min(i + 1, steps.length - 1))), ms),
    );
    return () => timers.forEach(clearTimeout);
  }, [steps.length]);
  return (
    <div className="assistant-card assistant-card--muted">
      <ol aria-label="Assistant progress" className="assistant-steps">
        {steps.map((label, i) => (
          <li
            key={label}
            aria-current={i === step ? "step" : undefined}
            data-done={i < step || undefined}
          >
            <span aria-hidden className="assistant-steps__dot" />
            {label}
          </li>
        ))}
      </ol>
      <Button ref={cancelRef} variant="outline" size="sm" onClick={cancel}>
        Cancel request
      </Button>
    </div>
  );
}

function useSecondsLeft(expiresAt: number | undefined, active: boolean) {
  const left = () =>
    expiresAt === undefined ? 0 : Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
  const [seconds, setSeconds] = useState(left);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setSeconds(left()), 1000);
    return () => clearInterval(timer);
    // `left` only reads expiresAt.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAt, active]);
  return seconds;
}

export function ProposalCard({
  turn,
  latest,
  datasets,
  disabled,
  busy,
  inspectNode,
  apply,
  discard,
  edit,
  regenerate,
}: {
  turn: Turn;
  latest: boolean;
  datasets: Dataset[];
  disabled: boolean;
  busy: boolean;
  inspectNode: (id: string) => void;
  apply: () => void;
  discard: () => void;
  edit: () => void;
  regenerate: () => void;
}) {
  const reply = turn.reply!;
  const live = latest && !turn.outcome;
  const seconds = useSecondsLeft(turn.expiresAt, live);
  const expired = live && seconds === 0;
  const status = turn.outcome
    ? { applied: "Saved", discarded: "Discarded", superseded: "Replaced by a newer request" }[
        turn.outcome
      ]
    : expired
      ? "Proposal expired"
      : `Expires in ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <article
      aria-labelledby={headingId(turn)}
      className="assistant-card assistant-card--primary"
    >
      {turn.mode === "diagnose" && reply.message && (
        <p className="text-sm">{plain(reply.message)}</p>
      )}
      <ProposalReview
        headingId={headingId(turn)}
        delta={reply.delta!}
        base={turn.base!}
        datasets={datasets}
        inspectNode={inspectNode}
        compact={!live}
      />
      {!!reply.steps?.length && (
        <details className="text-xs text-muted-foreground">
          <summary className="flex min-h-8 cursor-pointer items-center font-medium">
            Steps ({reply.steps.length})
          </summary>
          <ol className="mt-1 space-y-1">
            {reply.steps.map((step, i) => (
              <li key={i} className="flex items-center gap-1.5">
                {step.ok ? (
                  <Check aria-hidden className="size-3.5 text-success" />
                ) : (
                  <CircleAlert aria-hidden className="size-3.5 text-warning" />
                )}
                <code>{step.tool}</code>
                <span>· {step.ok ? "ok" : "failed"}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
      {reply.usage && (
        <p className="text-xs text-muted-foreground">
          {[
            count(reply.usage.calls, "call"),
            count(reply.usage.input_tokens, "input token"),
            count(reply.usage.output_tokens, "output token"),
          ].join(" · ")}
        </p>
      )}
      <p
        className={cn(
          "flex items-center gap-1.5 text-xs font-medium",
          expired ? "font-semibold text-foreground" : "text-muted-foreground",
        )}
      >
        {turn.outcome === "applied" ? (
          <Check aria-hidden className="size-3.5 text-success" />
        ) : (
          <Clock aria-hidden className={cn("size-3.5", expired && "text-warning")} />
        )}
        <span aria-live={expired ? "polite" : "off"}>{status}</span>
      </p>
      {live && (
        <>
          {disabled && (
            <p className="text-xs text-muted-foreground">
              This flow is disabled. Re-enable it to apply the proposal.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {!expired && (
              <Button size="sm" disabled={busy || disabled} onClick={apply}>
                Apply and save
              </Button>
            )}
            <Button
              size="sm"
              variant={expired ? "default" : "outline"}
              disabled={busy}
              onClick={regenerate}
            >
              Regenerate
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={edit}>
              Edit request
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={discard}>
              Discard
            </Button>
          </div>
        </>
      )}
    </article>
  );
}

const REASONS: Record<Reason | Conflict, { title: string; text: string }> = {
  unsupported_node: {
    title: "This step is not available yet",
    text: "The assistant cannot build this kind of node, so add it from the node palette.",
  },
  locked_node: {
    title: "This node is locked",
    text: "The assistant leaves this node as it is, so change it on the canvas instead.",
  },
  unsaved_changes: {
    title: "Save your changes first",
    text: "The assistant works from the saved flow, so save your canvas edits before asking.",
  },
  disabled_flow: {
    title: "This flow is disabled",
    text: "Re-enable the flow from the banner above the canvas before asking for changes.",
  },
  multiple_inputs: {
    title: "Several inputs on the canvas",
    text: "The assistant needs to know which input to work from, so name it in the request.",
  },
  no_dataset: {
    title: "Choose a dataset first",
    text: "Pick a project dataset or add a file input so the assistant knows the columns.",
  },
  ml_disabled: {
    title: "Machine learning is turned off",
    text: "Training and model nodes need machine learning to be enabled in Settings.",
  },
  no_failed_run: {
    title: "No failed run to diagnose",
    text: "Diagnosis explains the latest failed run, and this flow has none.",
  },
  budget_exhausted: {
    title: "Request budget used up",
    text: "The assistant reached its call or token limit before it finished the proposal.",
  },
  provider_no_tools: {
    title: "This model cannot edit flows",
    text: "The selected model does not support the tools the assistant needs to build flows.",
  },
  abstained: {
    title: "The assistant was not confident",
    text: "The assistant stopped rather than guess, so add detail to the request and try again.",
  },
  no_change: {
    title: "Nothing to change",
    text: "The flow already does what the request asks for.",
  },
  validation_failed: {
    title: "The proposal did not pass checks",
    text: "The assistant drafted a change that failed validation, so nothing was proposed.",
  },
  step_limit: {
    title: "Too many steps for one request",
    text: "Split the request into smaller changes and apply them one at a time.",
  },
  timeout: {
    title: "The request took too long",
    text: "The provider did not finish in time; retry, or ask for a smaller change.",
  },
};

const ASSISTANT_GUIDE = "https://ciaren.com/docs/latest/guide/flow-assistant";
const docsUrl = (target?: string) =>
  target && /^https:\/\//.test(target) ? target : ASSISTANT_GUIDE;

/** Shown when the reply proposes nothing: explain why and offer next actions. */
export function GuidanceCard({
  turn,
  busy,
  act,
}: {
  turn: Turn;
  busy: boolean;
  act: (suggestion: Suggestion) => void;
}) {
  const reply = turn.reply!;
  const reason = reply.reason ? REASONS[reply.reason] : undefined;
  return (
    <Card
      turn={turn}
      icon={<Compass aria-hidden className="size-4 text-primary" />}
      title={reason?.title ?? "No change proposed"}
    >
      {reason && (
        <p data-testid="guidance-explanation" className="text-sm">
          {reason.text}
        </p>
      )}
      {reply.message && (
        <p className={cn("text-sm", reason && "text-muted-foreground")}>{plain(reply.message)}</p>
      )}
      {!!reply.supported?.length && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Supported
          </p>
          <ul className="mt-1 flex flex-wrap gap-1.5 text-xs">
            {reply.supported.map((s) => (
              <li key={s} className="rounded-md bg-muted px-2 py-1">
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!!reply.suggestions?.length && (
        <div className="flex flex-wrap gap-2">
          {reply.suggestions.map((s, i) =>
            s.action === "open_docs" ? (
              <a
                key={i}
                href={docsUrl(s.target)}
                target="_blank"
                rel="noreferrer"
                className="assistant-chip inline-flex items-center"
              >
                {s.label}
              </a>
            ) : s.action === "enable_ml" ? (
              <Link key={i} to="/settings" className="assistant-chip inline-flex items-center">
                {s.label}
              </Link>
            ) : (
              <Button
                key={i}
                size="sm"
                variant={i === 0 ? "default" : "outline"}
                disabled={busy}
                onClick={() => act(s)}
              >
                {s.label}
              </Button>
            ),
          )}
        </div>
      )}
    </Card>
  );
}

export function PromptChips({ prompts, choose }: { prompts: string[]; choose: (p: string) => void }) {
  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {prompts.map((p) => (
        <button key={p} type="button" className="assistant-chip" onClick={() => choose(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}

export function AnswerCard({ turn }: { turn: Turn }) {
  const reply = turn.reply!;
  return (
    <Card
      turn={turn}
      icon={<Check aria-hidden className="size-4 text-primary" />}
      title={turn.mode === "docs" ? "From the guides" : "Assistant"}
    >
      <p className="whitespace-pre-line text-sm">{plain(reply.message)}</p>
      {reply.citation && (
        <a
          className="inline-flex min-h-8 items-center text-sm font-medium text-primary underline"
          href={reply.citation.url}
          target="_blank"
          rel="noreferrer"
        >
          {reply.citation.title}
        </a>
      )}
    </Card>
  );
}

export function StatusCard({ turn }: { turn: Turn }) {
  if (turn.state === "cancelled")
    return (
      <Card turn={turn} tone="muted" icon={<Ban aria-hidden className="size-4" />} title="Request cancelled">
        <p className="text-sm text-muted-foreground">
          The canvas is unchanged. A provider can still bill work it already started.
        </p>
      </Card>
    );
  return (
    <Card
      turn={turn}
      tone="destructive"
      icon={<CircleAlert aria-hidden className="size-4 text-destructive" />}
      title="Request failed"
    >
      <p role="alert" className="text-sm">
        {turn.error}
      </p>
    </Card>
  );
}
