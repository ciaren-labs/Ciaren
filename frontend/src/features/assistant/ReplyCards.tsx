import { useEffect, useState, type ReactNode } from "react";
import { Ban, Check, CircleAlert, Clock, Compass, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Dataset } from "@/features/datasets/types";
import { cn } from "@/lib/utils";
import { headingId, type Mode, type Turn } from "./api";
import { ProposalReview } from "./ProposalReview";
import { SUPPORTED } from "./suggestions";

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

/** Shown when the reply proposes nothing: explain why and offer prompts that can work. */
export function GuidanceCard({ turn, choose }: { turn: Turn; choose: (prompt: string) => void }) {
  const reply = turn.reply!;
  const supported = reply.supported?.length ? reply.supported : SUPPORTED;
  return (
    <Card turn={turn} icon={<Compass aria-hidden className="size-4 text-primary" />} title="No change proposed">
      <p className="text-sm">{plain(reply.reason ?? reply.message)}</p>
      {!reply.reason && (
        <p className="text-sm text-muted-foreground">
          The assistant edits file flows with the steps below. Rephrase the request around one of
          them, or build the step manually from the node palette.
        </p>
      )}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Supported
        </p>
        <ul className="mt-1 flex flex-wrap gap-1.5 text-xs">
          {supported.map((s) => (
            <li key={s} className="rounded-md bg-muted px-2 py-1">
              {s}
            </li>
          ))}
        </ul>
      </div>
      {!!reply.suggestions?.length && (
        <div>
          <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Lightbulb aria-hidden className="size-3.5" />
            Try
          </p>
          <PromptChips prompts={reply.suggestions} choose={choose} />
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
