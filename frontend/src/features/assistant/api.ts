import { ApiError, authHeaders, BASE_URL, parseError, request } from "@/lib/api/client";
import type { Flow, GraphEdge, GraphJson, GraphNode } from "@/features/flows/types";

export type Mode = "build" | "docs" | "diagnose";
export interface AssistantStatus {
  provider: string;
  model?: string;
  state?: "configured" | "missing" | "unavailable";
  source?: "keyring" | "env" | "file";
}
export interface Delta {
  added: GraphNode[];
  changed: GraphNode[];
  connected: GraphEdge[];
  disconnected: string[];
  /** Ids of base nodes the proposal deletes, with every edge that touches them. */
  removed?: string[];
}
/** Why a turn proposed nothing. */
export type Reason =
  | "unsupported_node"
  | "locked_node"
  | "unsaved_changes"
  | "multiple_inputs"
  | "no_dataset"
  | "ml_disabled"
  | "no_failed_run"
  | "budget_exhausted"
  | "provider_no_tools"
  | "abstained"
  | "no_change"
  | "validation_failed"
  | "step_limit"
  | "timeout"
  | "canvas_limit";
/** Reasons the server sends as a 409 conflict instead of a reply. */
export type Conflict = "unsaved_changes" | "disabled_flow";
export interface Suggestion {
  label: string;
  action:
    | "save"
    | "switch_mode"
    | "open_docs"
    | "enable_ml"
    | "manual_edit"
    | "share_names"
    | "retry";
  target?: string;
}
export interface Reply {
  message: string;
  citation?: { title: string; url: string };
  proposal?: string;
  delta?: Delta;
  usage?: { calls: number; input_tokens: number; output_tokens: number };
  steps?: { tool: string; ok: boolean }[];
  /** Seconds until the server forgets the proposal token. */
  expires_in?: number;
  /** Why no change was proposed. `disabled_flow` only comes from a conflict. */
  reason?: Reason | Conflict;
  supported?: string[];
  suggestions?: Suggestion[];
}
/** Apply response: the saved revision and the graph the server stored. */
export interface ApplyResult {
  revision: string;
  graph?: GraphJson;
}
/** One request and its reply in the panel's conversation. */
export interface Turn {
  id: string;
  mode: Mode;
  question: string;
  inputs: Inputs;
  state: "pending" | "reply" | "error" | "cancelled";
  reply?: Reply;
  error?: string;
  base?: GraphJson;
  session?: number;
  expiresAt?: number;
  outcome?: "applied" | "discarded" | "superseded";
}
export interface Inputs {
  dataset: string;
  secondDataset: string;
  lookup: string;
  target: string;
  shareNames: boolean;
}

/** Id of a reply heading, which receives focus when the reply lands. */
export const headingId = (turn: Pick<Turn, "id">) => `assistant-turn-${turn.id}`;
/** The server keeps a proposal for this long when the reply does not say. */
export const DEFAULT_PROPOSAL_TTL = 180;
export const expiryOf = (reply: Reply) =>
  Date.now() + (reply.expires_in ?? DEFAULT_PROPOSAL_TTL) * 1000;

export type Fact = {
  action: string;
  kind?: string;
  field?: string;
  before?: unknown;
  after?: unknown;
  from?: string;
  to?: string;
  port?: string;
  source_port?: string;
};
export type ActivityEntry = {
  id: string;
  date: string;
  source: "build" | "diagnose" | "revert";
  state: "available" | "recorded" | "reverted";
  reverses: string | null;
  details: Fact[];
};
export type ActivityPage = { entries: ActivityEntry[]; next: string | null };
export type ReversalPreview = { confirmation: string; details: Fact[] };

export const activityKey = (projectId: string | null, flowId: string) => [
  "assistant-activity",
  projectId,
  flowId,
];
export const activityUrl = (flowId: string) =>
  `/assistant/flows/${flowId}/activity`;
export const previewReversal = (flowId: string, id: string, revision: string) =>
  request<ReversalPreview>(`${activityUrl(flowId)}/${id}/preview`, {
    method: "POST",
    body: JSON.stringify({ revision }),
  });
export const confirmReversal = (flowId: string, id: string, confirmation: string) =>
  request<{ revision: string }>(`${activityUrl(flowId)}/${id}/revert`, {
    method: "POST",
    body: JSON.stringify({ proposal: confirmation }),
  });
export const loadFlow = (flowId: string) =>
  request<Flow>(`/flows/${flowId}`, { cache: "no-store" });

/** Compares server timestamps that may omit the UTC designator. */
export function sameInstant(a: string, b: string) {
  const parse = (s: string) =>
    Date.parse(/(?:[zZ]|[+-]\d\d:?\d\d)$/.test(s) ? s : `${s}Z`);
  return parse(a) === parse(b);
}
export const status = () =>
  request<AssistantStatus>("/assistant/status", { cache: "no-store" });
export function updateCredential(provider: string, value?: string) {
  return request<void>(`/assistant/credentials/${provider}`, {
    method: value === undefined ? "DELETE" : "PUT",
    redirect: "error",
    cache: "no-store",
    body: value === undefined ? undefined : JSON.stringify({ key: value }),
  });
}
export function applyDelta(base: GraphJson, delta: Delta): GraphJson {
  const removed = new Set(delta.removed);
  return {
    ...base,
    nodes: [
      ...base.nodes
        .filter((n) => !removed.has(n.id))
        .map((n) => delta.changed.find((c) => c.id === n.id) ?? n),
      ...delta.added,
    ],
    edges: [
      ...base.edges.filter(
        (e) =>
          !delta.disconnected.includes(e.id) &&
          !removed.has(e.source) &&
          !removed.has(e.target),
      ),
      ...delta.connected,
    ],
  };
}

const CONFLICTS: readonly string[] = ["unsaved_changes", "disabled_flow"] satisfies Conflict[];

/**
 * Posts a turn. A conflict the editor can resolve (unsaved canvas, disabled
 * flow) resolves as a reply with its reason; the shared `request` would drop
 * the top-level `reason` of the 409 body.
 */
export async function sendTurn(
  flowId: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
): Promise<Reply> {
  const res = await fetch(`${BASE_URL}/assistant/flows/${flowId}/turn`, {
    method: "POST",
    signal,
    redirect: "error",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", ...authHeaders() },
  });
  if (res.status !== 409) {
    if (!res.ok) throw await parseError(res);
    return (await res.json()) as Reply;
  }
  const conflict = (await res.json().catch(() => null)) as {
    detail?: unknown;
    reason?: unknown;
  } | null;
  const detail = typeof conflict?.detail === "string" ? conflict.detail : "";
  if (typeof conflict?.reason === "string" && CONFLICTS.includes(conflict.reason))
    return { message: detail, reason: conflict.reason as Conflict };
  throw new ApiError(detail || "Request failed with status 409", 409, conflict?.detail);
}
