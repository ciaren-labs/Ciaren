// Node types most recently placed from the node palette (click-to-add or a
// palette drag dropped on the canvas), most recent first. Paste, duplicate and
// flow loads do not count: they reuse existing nodes rather than picking a type.
//
// Persisted through safeStorage and re-read on every snapshot, so storage is the
// single source of truth: when it is blocked the list stays empty and the palette
// hides the section. The stored value is untrusted and sanitized on read; callers
// still filter the result against the live catalog (uninstalled plugin nodes).
import { useSyncExternalStore } from "react";
import { readLocalStorage, writeLocalStorage } from "@/lib/safeStorage";

export const RECENT_NODES_KEY = "ciaren_recent_nodes";
export const RECENT_NODES_LIMIT = 5;

/** Keep at most RECENT_NODES_LIMIT distinct non-empty strings, in order; anything else is dropped. */
export function sanitizeRecentNodeTypes(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const types: string[] = [];
  for (const item of value) {
    if (types.length === RECENT_NODES_LIMIT) break;
    if (typeof item === "string" && item !== "" && !types.includes(item)) types.push(item);
  }
  return types;
}

/** Put `type` first, dropping its previous position and anything past the limit. */
export function pushRecentNodeType(types: readonly string[], type: string): string[] {
  return [type, ...types.filter((t) => t !== type)].slice(0, RECENT_NODES_LIMIT);
}

function parseRecentNodeTypes(raw: string | null): string[] {
  if (raw === null) return [];
  try {
    return sanitizeRecentNodeTypes(JSON.parse(raw));
  } catch {
    // JSON.parse only throws SyntaxError: a corrupt value reads as "no history".
    return [];
  }
}

// Snapshot cache keyed by the raw stored string, so useSyncExternalStore gets a
// stable array until the stored value actually changes.
let cachedRaw: string | null = null;
let cachedTypes: string[] = [];
const listeners = new Set<() => void>();

/** The sanitized recent list currently in storage (empty when storage is blocked). */
export function readRecentNodeTypes(): string[] {
  const raw = readLocalStorage(RECENT_NODES_KEY);
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedTypes = parseRecentNodeTypes(raw);
  }
  return cachedTypes;
}

/** Record a node type placed from the palette and notify mounted palettes. */
export function recordRecentNodeType(type: string): void {
  writeLocalStorage(
    RECENT_NODES_KEY,
    JSON.stringify(pushRecentNodeType(readRecentNodeTypes(), type)),
  );
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useRecentNodeTypes(): string[] {
  return useSyncExternalStore(subscribe, readRecentNodeTypes);
}
