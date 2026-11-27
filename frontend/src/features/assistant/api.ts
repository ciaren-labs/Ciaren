import { request } from "@/lib/api/client";
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
}
export interface Reply {
  message: string;
  citation?: { title: string; url: string };
  proposal?: string;
  delta?: Delta;
  /** Seconds until the server forgets the proposal token. */
  expires_in?: number;
  /** Why no change was proposed, with what the assistant can do instead. */
  reason?: string;
  supported?: string[];
  suggestions?: string[];
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
  return {
    ...base,
    nodes: [
      ...base.nodes.map((n) => delta.changed.find((c) => c.id === n.id) ?? n),
      ...delta.added,
    ],
    edges: [
      ...base.edges.filter((e) => !delta.disconnected.includes(e.id)),
      ...delta.connected,
    ],
  };
}
