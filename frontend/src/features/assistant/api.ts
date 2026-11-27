import { request } from "@/lib/api/client";
import type { GraphEdge, GraphJson, GraphNode } from "@/features/flows/types";

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
