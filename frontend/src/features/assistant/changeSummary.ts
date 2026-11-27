import type { GraphJson } from "@/features/flows/types";
import type { Delta, Fact } from "./api";

/** Change counts shared by the proposal review and the activity history. */
export interface ChangeCounts {
  added: number;
  removed: number;
  settings: number;
  connections: number;
}

/** Counts settings per changed field, which is how the server records activity. */
export function deltaCounts(delta: Delta, base: GraphJson): ChangeCounts {
  const settings = delta.changed.reduce((total, node) => {
    const before = base.nodes.find((n) => n.id === node.id)?.data.config ?? {};
    const after = node.data.config;
    const fields = new Set([...Object.keys(before), ...Object.keys(after)]);
    return (
      total +
      [...fields].filter(
        (f) => JSON.stringify(before[f]) !== JSON.stringify(after[f]),
      ).length
    );
  }, 0);
  return {
    added: delta.added.length,
    removed: 0,
    settings,
    connections: delta.connected.length + delta.disconnected.length,
  };
}

export function factCounts(facts: Fact[]): ChangeCounts {
  const count = (...actions: string[]) =>
    facts.filter((f) => actions.includes(f.action)).length;
  return {
    added: count("add_node"),
    removed: count("remove_node"),
    settings: count("edit_field"),
    connections: count("connect", "disconnect"),
  };
}

export function summaryParts(c: ChangeCounts) {
  const part = (n: number, word: string) =>
    n ? `${n} ${word}${n === 1 ? "" : "s"}` : "";
  return [
    part(c.added, "new node"),
    part(c.removed, "removed node"),
    part(c.settings, "updated setting"),
    part(c.connections, "connection"),
  ].filter(Boolean);
}

export const summarize = (c: ChangeCounts) =>
  summaryParts(c).join(" · ") || "No canvas changes";
